"""Policy configuration integrity, modality coverage and evidence confidence.

Sixth audit round: the ten policies shared an audit framework but not a common set of
safety invariants. These tests pin the invariants that are now enforced for every
policy, not only for the PEAD one.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import pead_engine
from src.pead_engine import assess, load_policies
from src.policy_config import validate_policies


def observation(oid, tag, modality="speech"):
    return {"id": oid, "tag": tag, "modality": modality, "event_id": "EVT_1",
            "start_ms": 1000, "end_ms": 2000, "source_refs": ["src:" + oid],
            "time_confidence": "HIGH", "referent_key": "EVT_1"}


ALL_FULL = {"visual": "FULL", "speech": "FULL", "screen_text": "FULL", "sound": "FULL"}


class PolicyConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(
            (Path(pead_engine.__file__).resolve().parents[1] / "config" / "policies_v03.json")
            .read_text(encoding="utf-8"))

    def test_emptying_a_policys_tags_is_rejected(self):
        """A plain JSON edit must not be able to remove a risk recognition path."""
        broken = copy.deepcopy(self.document)
        broken["policies"]["R_SELF_HARM"]["action_tags"] = []
        with self.assertRaises(Exception):
            validate_policies(broken)

    def test_dropping_one_of_two_required_tags_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken["policies"]["R_SELF_HARM"]["action_tags"].remove("self_harm_instruction")
        with self.assertRaises(Exception):
            validate_policies(broken)

    def test_weakening_a_high_severity_disposition_is_rejected(self):
        for policy_id in ("R_SELF_HARM", "R_SEXUAL_CONTENT", "R_MINORS_PROTECTION"):
            with self.subTest(policy=policy_id):
                broken = copy.deepcopy(self.document)
                broken["policies"][policy_id]["disposition"] = "NONE"
                with self.assertRaises(Exception):
                    validate_policies(broken)

    def test_removing_a_policy_entirely_is_rejected(self):
        broken = copy.deepcopy(self.document)
        del broken["policies"]["R_CONTROLLED_GOODS"]
        with self.assertRaises(Exception):
            validate_policies(broken)

    def test_adding_evidence_tags_is_still_allowed(self):
        """Tightening is allowed; only removing a path is refused."""
        extra = copy.deepcopy(self.document)
        extra["policies"]["R_SELF_HARM"]["action_tags"].append("minor_risk")
        validated = validate_policies(extra)
        self.assertIn("minor_risk", validated["R_SELF_HARM"]["action_tags"])

    def test_the_shipped_configuration_loads(self):
        self.assertEqual(len(load_policies()["policies"]), 10)


class ModalityCoverageTests(unittest.TestCase):
    def test_unreadable_channel_is_not_reported_as_nothing_found(self):
        """Video-level FULL does not mean every channel was read."""
        observations = [observation("E01", "unrelated_tag")] if False else []
        data = {"coverage": "FULL", "observations": observations,
                "modalities": {**ALL_FULL, "speech": "UNKNOWN"}}
        finding = next(item for item in assess(data, 30_000)["findings"]
                       if item["policy_id"] == "R_FRAUD_SCAM")
        self.assertEqual((finding["judgement"], finding["disposition"]),
                         ("UNKNOWN", "RECHECK"))
        self.assertEqual(finding["reason_code"], "INCOMPLETE_OBSERVATION")

    def test_fully_observed_channels_still_allow_a_clean_result(self):
        data = {"coverage": "FULL", "observations": [], "modalities": dict(ALL_FULL)}
        finding = next(item for item in assess(data, 30_000)["findings"]
                       if item["policy_id"] == "R_FRAUD_SCAM")
        self.assertEqual((finding["judgement"], finding["disposition"]),
                         ("NOT_SUPPORTED", "NONE"))

    def test_a_detected_cue_is_reported_even_when_another_channel_is_partial(self):
        cue = observation("E01", "self_harm_instruction")
        data = {"coverage": "FULL", "observations": [cue],
                "modalities": {**ALL_FULL, "screen_text": "PARTIAL"}}
        finding = next(item for item in assess(data, 30_000)["findings"]
                       if item["policy_id"] == "R_SELF_HARM")
        self.assertEqual(finding["disposition"], "FLAG")


class EvidenceConfidenceTests(unittest.TestCase):
    def test_low_confidence_cue_keeps_severity_but_records_the_uncertainty(self):
        """A risky cue at 0.81 may still justify a strong action — but not silently."""
        cue = observation("E01", "self_harm_instruction")
        cue["needs_human_review"] = True
        data = {"coverage": "FULL", "observations": [cue], "modalities": dict(ALL_FULL)}
        finding = next(item for item in assess(data, 30_000)["findings"]
                       if item["policy_id"] == "R_SELF_HARM")
        self.assertEqual(finding["disposition"], "FLAG")
        self.assertEqual(finding["evidence_confidence"], "LOW")
        self.assertTrue(finding["needs_human_review"])

    def test_confident_cue_is_marked_high(self):
        cue = observation("E01", "self_harm_instruction")
        data = {"coverage": "FULL", "observations": [cue], "modalities": dict(ALL_FULL)}
        finding = next(item for item in assess(data, 30_000)["findings"]
                       if item["policy_id"] == "R_SELF_HARM")
        self.assertEqual(finding["evidence_confidence"], "HIGH")
        self.assertFalse(finding["needs_human_review"])


class RelationContractTests(unittest.TestCase):
    def test_the_shipped_schema_matches_the_runtime_adapter(self):
        from fixtures import prompt_contract

        entries = [row for row in prompt_contract.check_relation()
                   if row["check"].startswith("schema")]
        self.assertTrue(entries)
        self.assertTrue(entries[0]["passed"], entries[0]["note"])

    def test_a_legacy_decisions_schema_fails_the_check(self):
        """The check must fail on the old contract instead of reporting success."""
        from fixtures import prompt_contract

        legacy = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                  "type": "object", "required": ["schema_version", "decisions"],
                  "properties": {"schema_version": {"const": "videoguard_relation_check_v1"},
                                 "decisions": {"type": "array"}}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "relation_check_schema_v1.json").write_text(
                json.dumps(legacy), encoding="utf-8")
            (root / "relation_check_system.md").write_text(
                "encourages_same warns_same unrelated insufficient", encoding="utf-8")
            with patch.object(prompt_contract, "PROMPTS", root):
                entries = [row for row in prompt_contract.check_relation()
                           if row["check"].startswith("schema")]
        self.assertFalse(entries[0]["passed"])
        self.assertIn("decisions", entries[0]["note"])


class UniformConfidenceTests(unittest.TestCase):
    """Every policy derives evidence certainty from the cues it rests on."""

    def _finding(self, observations, policy_id):
        data = {"coverage": "FULL", "observations": observations,
                "modalities": dict(ALL_FULL)}
        return next(item for item in assess(data, 30_000)["findings"]
                    if item["policy_id"] == policy_id)

    def test_all_four_special_branches_inherit_low_confidence(self):
        cases = [("violence", "visual", "R_VIOLENCE"),
                 ("pii_candidate", "screen_text", "R_PRIVACY_EXPOSURE"),
                 ("credential_claim", "speech", "R_MARKETING_CLAIM")]
        for tag, modality, policy_id in cases:
            with self.subTest(policy=policy_id):
                cue = observation("E01", tag, modality)
                cue["needs_human_review"] = True
                finding = self._finding([cue], policy_id)
                self.assertEqual(finding["evidence_confidence"], "LOW")
                self.assertTrue(finding["needs_human_review"])

    def test_pead_policy_inherits_it_too(self):
        action = observation("E01", "danger_action", "visual")
        stance = observation("E02", "encouragement", "speech")
        for cue in (action, stance):
            cue["needs_human_review"] = True
        finding = self._finding([action, stance], "R_DANGER_PROMOTION")
        self.assertEqual(finding["evidence_confidence"], "LOW")
        self.assertTrue(finding["needs_human_review"])

    def test_low_confidence_counter_lowers_the_finding_confidence(self):
        """A counter that changed the outcome is part of the evidence reliability.

        Here the violence cue is confident but the news context that turned FLAG into
        REVIEW is not, so reporting HIGH would overstate the support.
        """
        act = observation("E01", "violence", "visual")
        context = observation("E02", "news_context", "speech")
        context["needs_human_review"] = True
        finding = self._finding([act, context], "R_VIOLENCE")
        self.assertEqual(finding["disposition"], "REVIEW")
        self.assertEqual(finding["counter_ids"], ["E02"])
        self.assertEqual(finding["evidence_confidence"], "LOW")
        self.assertTrue(finding["needs_human_review"])

    def test_confident_cues_stay_high(self):
        finding = self._finding([observation("E01", "self_harm_instruction")],
                                "R_SELF_HARM")
        self.assertEqual(finding["evidence_confidence"], "HIGH")
        self.assertFalse(finding["needs_human_review"])


class ReportCarriesUncertaintyTests(unittest.TestCase):
    """The exported report must state that the cue itself is unconfirmed."""

    def _case(self):
        from fixtures.compare_pead import load_input
        from pipeline import clean_issue_locator, clean_video_parse
        from src.audit_report import build_fallback_audit_report

        raw = load_input("self_harm_cue")
        parsed = clean_video_parse(raw["video_parse"], raw["duration_ms"])
        located = clean_issue_locator(raw["issue_locator"], parsed)
        findings = assess(located, raw["duration_ms"])["findings"]
        report = build_fallback_audit_report(located, findings, raw["duration_ms"])
        return located, findings, report

    def test_fallback_binds_the_note_to_the_evidence(self):
        from src.audit_report import validate_audit_report

        located, findings, report = self._case()
        notes = [note for plan in report["revision_plan"] for issue in plan["issues"]
                 for note in issue["uncertainties"]]
        self.assertTrue(any("置信度不足" in note for note in notes), notes)
        self.assertTrue(any("E01" in note for note in notes), notes)
        self.assertIsNotNone(validate_audit_report(report, located, findings, 25_000))

    def test_report_without_the_structured_flag_is_rejected(self):
        import copy as copy_module

        from src.audit_report import validate_audit_report

        located, findings, report = self._case()
        tampered = copy_module.deepcopy(report)
        for plan in tampered["revision_plan"]:
            for issue in plan["issues"]:
                issue["low_confidence_evidence"] = []
        self.assertIsNone(validate_audit_report(tampered, located, findings, 25_000))

    def test_prose_containing_only_an_evidence_id_is_rejected(self):
        """uncertainties: ["E01"] must not satisfy a caveat requirement."""
        import copy as copy_module

        from src.audit_report import validate_audit_report

        located, findings, report = self._case()
        tampered = copy_module.deepcopy(report)
        for plan in tampered["revision_plan"]:
            for issue in plan["issues"]:
                issue["uncertainties"] = ["E01"]
                issue["low_confidence_evidence"] = []
        self.assertIsNone(validate_audit_report(tampered, located, findings, 25_000))

    def test_exported_html_shows_the_note(self):
        from report import render_html

        located, findings, report = self._case()
        html = render_html({"id": "T1", "status": "DONE", "mode": "DEMO",
                            "video_name": "x", "created_at": "t",
                            "result": {"coverage": located["coverage"],
                                        "findings": findings,
                                        "audit_report": report}})
        self.assertIn("线索置信度不足", html)
        self.assertIn("E01", html)



if __name__ == "__main__":
    unittest.main()
