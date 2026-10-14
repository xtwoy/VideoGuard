"""Tests for the shared relation-parameter module.

The point of ``src/config.py`` is that the relation time window used to select
candidate pairs, the window used to judge them in PEAD, and the policy file value
are all the same number — and that a disagreement fails loudly rather than
silently making the two halves of the pipeline disagree.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src import config, pead_engine, relation_client


class RelationParameterTests(unittest.TestCase):
    def test_policy_file_agrees_with_the_code_default(self):
        policies = pead_engine.load_policies()["policies"]
        self.assertEqual(config.assert_policy_gap_agrees(policies),
                         config.DEFAULT_RELATION_GAP_MS)

    def test_selecting_and_judging_share_one_window(self):
        """The adapter and the engine must read the same value, not two copies."""
        self.assertEqual(relation_client.select_pairs.__defaults__[1], None,
                         "select_pairs 应在调用时解析窗口，而不是在导入时固化")
        policies = pead_engine.load_policies()["policies"]
        self.assertEqual(pead_engine.relation_gap_ms(),
                         config.assert_policy_gap_agrees(policies))

    def test_divergent_policy_value_fails_loudly(self):
        policies = dict(pead_engine.load_policies()["policies"])
        policies["R_DANGER_PROMOTION"] = dict(policies["R_DANGER_PROMOTION"],
                                              max_relation_gap_ms=9_999)
        with self.assertRaises(ValueError) as caught:
            config.assert_policy_gap_agrees(policies)
        self.assertIn("不一致", str(caught.exception))

    def test_environment_override_that_diverges_also_fails(self):
        """An override is only usable if the policy file is updated with it."""
        with patch.dict(os.environ, {"RELATION_GAP_MS": "8000"}):
            self.assertEqual(config.relation_gap_ms(), 8000)
            with self.assertRaises(ValueError):
                config.assert_policy_gap_agrees(
                    pead_engine.load_policies()["policies"])

    def test_environment_override_consistent_with_policy_is_accepted(self):
        policies = dict(pead_engine.load_policies()["policies"])
        policies["R_DANGER_PROMOTION"] = dict(policies["R_DANGER_PROMOTION"],
                                              max_relation_gap_ms=8_000)
        with patch.dict(os.environ, {"RELATION_GAP_MS": "8000"}):
            self.assertEqual(config.assert_policy_gap_agrees(policies), 8000)

    def test_invalid_parameter_values_are_rejected(self):
        for name, bad in (("RELATION_GAP_MS", "abc"),
                          ("RELATION_GAP_MS", "-5"),
                          ("RELATION_MIN_CHOICE_CONFIDENCE", "1.5"),
                          ("RELATION_MAX_REVIEW_PROBABILITY", "not-a-number")):
            with self.subTest(name=name, value=bad):
                with patch.dict(os.environ, {name: bad}):
                    with self.assertRaises(ValueError):
                        config.describe()

    def test_confidence_gate_reads_the_shared_threshold(self):
        """Raising the threshold must actually route a confident answer to review."""
        row = {"status": "VALID", "choice": "encourages_same", "confidence": 0.90,
               "needs_review_probability": 0.10}
        self.assertEqual(relation_client.semantic_gate(row), "encourages_same")
        with patch.dict(os.environ, {"RELATION_MIN_CHOICE_CONFIDENCE": "0.95"}):
            self.assertEqual(relation_client.semantic_gate(row), "REVIEW")

    def test_describe_records_where_each_value_came_from(self):
        described = config.describe()
        for key in ("relation_gap_ms", "min_choice_confidence",
                    "max_review_probability"):
            with self.subTest(parameter=key):
                self.assertIn("value", described[key])
                self.assertIn("source", described[key])
        with patch.dict(os.environ, {"RELATION_GAP_MS": "15000"}):
            self.assertIn("环境变量", config.describe()["relation_gap_ms"]["source"])


class CounterEvidenceProvenanceTests(unittest.TestCase):
    """An empty counter list must say whether anyone looked.

    ``counter_ids == []`` is ambiguous on its own. These tests pin the field that
    removes the ambiguity, so a report can distinguish an examined absence from an
    unexamined one.
    """

    def _findings(self, case_name: str) -> dict:
        from fixtures import cases as case_defs
        from pipeline import clean_issue_locator, clean_video_parse
        from src.pead_engine import assess

        case = case_defs.CASES[case_name]()
        located = clean_issue_locator(
            case["issue_locator"],
            clean_video_parse(case["video_parse"], case_defs.DURATION_MS))
        return {f["policy_id"]: f for f in assess(located, case_defs.DURATION_MS)["findings"]}

    def test_every_finding_carries_provenance(self):
        for policy_id, finding in self._findings("danger_promotion").items():
            with self.subTest(policy=policy_id):
                block = finding.get("counter_evidence")
                self.assertIsInstance(block, dict)
                for key in ("checked", "source", "found", "relation_checked"):
                    self.assertIn(key, block)

    def test_policies_that_search_for_counter_evidence_say_so(self):
        findings = self._findings("danger_promotion")
        self.assertEqual(
            findings["R_DANGER_PROMOTION"]["counter_evidence"],
            {"checked": True, "source": "COUNTER_CONTEXT_TAGS",
             "found": False, "relation_checked": True})
        self.assertEqual(findings["R_VIOLENCE"]["counter_evidence"]["source"],
                         "CONTEXT_TAGS")

    def test_policies_without_a_counter_notion_are_marked_not_applicable(self):
        findings = self._findings("danger_promotion")
        block = findings["R_PRIVACY_EXPOSURE"]["counter_evidence"]
        self.assertFalse(block["checked"])
        self.assertEqual(block["source"], "NOT_APPLICABLE")

    def test_found_flag_matches_the_counter_id_list(self):
        """The flag is derived from the ids, so the two can never disagree."""
        for case_name in ("danger_promotion", "warning_context", "counter_context_tagging"):
            for policy_id, finding in self._findings(case_name).items():
                with self.subTest(case=case_name, policy=policy_id):
                    self.assertEqual(finding["counter_evidence"]["found"],
                                     bool(finding["counter_ids"]))


if __name__ == "__main__":
    unittest.main()
