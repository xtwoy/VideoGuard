"""Regression tests for the audit-report defects the fixture pack uncovered.

Each test pins one behaviour that was broken, so the fix cannot silently regress.
They build their inputs directly from the protocol shapes rather than from
fixture files, so they stay independent of the curated sample pack.

1. ``build_fallback_audit_report`` raised for any finding with a non-NONE
   disposition that had no event of its own, which made the degraded path crash
   exactly when coverage was incomplete.
2. A parent dimension could report a better score/status than its own children.
3. A dimension that was never evaluated was reported as a pass with a high score,
   contradicting the rule that every score must follow from that dimension's
   evidence.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.audit_report import (
    UNEVALUATED_SCORE, UNEVALUATED_STATUS, build_fallback_audit_report,
    validate_audit_report,
)

ROOT = Path(__file__).resolve().parents[1]
DURATION_MS = 25_000


def _parse() -> dict:
    return json.loads(
        (ROOT / "fixtures/demo_video_parse_response.json").read_text(encoding="utf-8"))


def _locator() -> dict:
    return json.loads(
        (ROOT / "fixtures/demo_issue_locator_response.json").read_text(encoding="utf-8"))


def _located():
    from pipeline import clean_issue_locator, clean_video_parse
    parsed = clean_video_parse(_parse(), DURATION_MS)
    return clean_issue_locator(_locator(), parsed)


def _finding(policy_id: str, judgement: str, disposition: str, reason_code: str,
             supporting=(), counter=()) -> dict:
    return {"policy_id": policy_id, "id": policy_id, "judgement": judgement,
            "disposition": disposition, "reason_code": reason_code,
            "supporting_ids": list(supporting), "counter_ids": list(counter)}


class ReportWithoutEventBoundEvidenceTests(unittest.TestCase):
    """Defect 1: findings with no event of their own must still produce a report."""

    def test_finding_with_no_evidence_or_event_still_reports(self):
        located = _located()
        findings = [_finding("R_DANGER_PROMOTION", "INSUFFICIENT", "REVIEW",
                             "MISSING_SEMANTIC_RELATION")]
        report = build_fallback_audit_report(located, findings, DURATION_MS)
        self.assertIsNotNone(report)
        self.assertTrue(report["revision_plan"])

    def test_every_issue_carries_evidence(self):
        """The contract rejects an issue with no supporting evidence."""
        located = _located()
        findings = [_finding("R_DANGER_PROMOTION", "INSUFFICIENT", "REVIEW",
                             "MISSING_SEMANTIC_RELATION")]
        report = build_fallback_audit_report(located, findings, DURATION_MS)
        for plan in report["revision_plan"]:
            for issue in plan["issues"]:
                self.assertTrue(issue["supporting_evidence"],
                                f"{issue['id']} has no supporting evidence")

    def test_incomplete_coverage_reports_instead_of_crashing(self):
        """Partial coverage flags all ten policies; that must not raise."""
        located = _located()
        located["coverage"] = "PARTIAL"
        findings = [_finding(policy, "UNKNOWN", "RECHECK", "INCOMPLETE_OBSERVATION")
                    for policy in (
                        "R_DANGER_PROMOTION", "R_VIOLENCE", "R_PRIVACY_EXPOSURE",
                        "R_MARKETING_CLAIM", "R_SELF_HARM", "R_SEXUAL_CONTENT",
                        "R_HATE_HARASSMENT", "R_FRAUD_SCAM", "R_CONTROLLED_GOODS",
                        "R_MINORS_PROTECTION")]
        report = build_fallback_audit_report(located, findings, DURATION_MS)
        self.assertIsNotNone(report)
        # Incomplete observation must never be reported as a clean result.
        self.assertNotEqual(report["overall_verdict"], "PUBLISHABLE")

    def test_report_is_still_protocol_valid(self):
        located = _located()
        findings = [_finding("R_DANGER_PROMOTION", "INSUFFICIENT", "REVIEW",
                             "MISSING_SEMANTIC_RELATION")]
        report = build_fallback_audit_report(located, findings, DURATION_MS)
        self.assertIsNotNone(
            validate_audit_report(report, located, findings, DURATION_MS))


class DimensionRollUpTests(unittest.TestCase):
    """Defect 2: a parent dimension must not look healthier than its children."""

    def test_parent_score_is_the_worst_child_score(self):
        report = build_fallback_audit_report(_located(), [], DURATION_MS)
        for key, dimension in report["dimension_scores"].items():
            scores = [item["score"] for item in dimension["items"]]
            self.assertEqual(
                dimension["score"], min(scores),
                f"{key} parent score {dimension['score']} is better than its "
                f"worst child {min(scores)}")

    def test_parent_is_not_pass_when_a_child_is_not(self):
        report = build_fallback_audit_report(_located(), [], DURATION_MS)
        for key, dimension in report["dimension_scores"].items():
            child_statuses = {item["status"] for item in dimension["items"]}
            if "FAIL" in child_statuses:
                self.assertEqual(dimension["status"], "FAIL", key)
            if UNEVALUATED_STATUS in child_statuses and "FAIL" not in child_statuses:
                self.assertEqual(dimension["status"], UNEVALUATED_STATUS, key)


class UnevaluatedDimensionTests(unittest.TestCase):
    """Defect 3: no evidence must not be reported as a confident pass."""

    def test_unobserved_modality_is_not_scored_as_a_pass(self):
        """A modality the parse did not fully observe cannot be scored."""
        located = _located()
        located["observation_detail"]["coverage"]["modalities"]["sound"] = "UNKNOWN"
        report = build_fallback_audit_report(located, [], DURATION_MS)
        sound = next(item for item in report["dimension_scores"]["audit_coverage"]["items"]
                     if item["key"] == "sound")
        self.assertEqual(sound["status"], UNEVALUATED_STATUS)
        self.assertEqual(sound["score"], UNEVALUATED_SCORE)

    def test_fully_observed_modality_without_facts_is_a_pass(self):
        """Examined and nothing found is a real result, not an unknown."""
        located = _located()
        for shot in located["observation_detail"]["timeline"]["shots"]:
            shot["screen_text"] = []
        located["observation_detail"]["coverage"]["modalities"]["screen_text"] = "FULL"
        report = build_fallback_audit_report(located, [], DURATION_MS)
        screen = next(item for item in report["dimension_scores"]["audit_coverage"]["items"]
                      if item["key"] == "screen_text")
        self.assertEqual(screen["status"], "PASS")
        self.assertEqual(screen["score"], 100)

    def test_unevaluated_dimension_blocks_a_publishable_verdict(self):
        located = _located()
        located["observation_detail"]["coverage"]["modalities"]["sound"] = "UNKNOWN"
        report = build_fallback_audit_report(located, [], DURATION_MS)
        self.assertNotEqual(report["overall_verdict"], "PUBLISHABLE")

    def test_fully_observed_video_can_still_be_publishable(self):
        """The guard must not turn every clean video into manual review."""
        located = _located()
        located["observation_detail"]["coverage"]["modalities"] = {
            "visual": "FULL", "speech": "FULL",
            "screen_text": "FULL", "sound": "FULL"}
        for shot in located["observation_detail"]["timeline"]["shots"]:
            shot["screen_text"] = []
            shot["audio_observations"] = []
        report = build_fallback_audit_report(located, [], DURATION_MS)
        self.assertEqual(report["overall_verdict"], "PUBLISHABLE")


if __name__ == "__main__":
    unittest.main()
