"""Mock failure cases: incomplete observations must never become clean results."""
from __future__ import annotations

import copy
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import clean_issue_locator, clean_video_parse, _run_models, run_live
from src.issue_locator_client import adapt_jev_response, build_jev_request, locate_issues

ROOT = Path(__file__).resolve().parents[1]
PARSE = json.loads((ROOT / "fixtures/demo_video_parse_response.json").read_text())
LOCATOR = json.loads((ROOT / "fixtures/demo_issue_locator_response.json").read_text())


class LocatorFailureTests(unittest.TestCase):
    def setUp(self):
        self.parsed = clean_video_parse(copy.deepcopy(PARSE), 25_000)
        self.request = build_jev_request(self.parsed["observation_detail"])
        self.answers = {name: {"type": "noul", "noul": 0.0}
                        for name in self.request["questions"]}

    def adapt(self, answers):
        return adapt_jev_response(self.request, {"answers": answers})

    def test_missing_or_malformed_envelopes_are_rejected(self):
        for raw in (None, [], "invalid", {}, {"answers": None}, {"answers": []},
                    {"answers": {}}, {"answers": {"unknown": {"type": "noul", "noul": 1}}}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                adapt_jev_response(self.request, raw)

    def test_one_missing_answer_invalidates_the_response(self):
        answers = copy.deepcopy(self.answers)
        answers.pop(next(iter(answers)))
        with self.assertRaises(ValueError):
            self.adapt(answers)

    def test_extra_answer_is_not_silently_ignored(self):
        answers = {**self.answers, "unknown": {"type": "noul", "noul": 0.0}}
        with self.assertRaises(ValueError):
            self.adapt(answers)

    def test_invalid_answer_shapes_are_rejected(self):
        for invalid in (None, [], "bad", {}, {"type": "choice", "noul": 0.9},
                        {"type": "noul"}):
            answers = copy.deepcopy(self.answers)
            answers[next(iter(answers))] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.adapt(answers)

    def test_invalid_probabilities_are_rejected_even_if_they_would_be_filtered(self):
        for value in (-0.01, 1.01, float("nan"), float("inf"), -float("inf"),
                      True, False, "0.9", None, 10**1000, -(10**1000)):
            answers = copy.deepcopy(self.answers)
            answers[next(iter(answers))]["noul"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.adapt(answers)

    def test_valid_negative_answers_are_not_confused_with_missing_answers(self):
        output = self.adapt(self.answers)
        self.assertEqual(output["risk_cues"], [])
        clean_issue_locator(output, self.parsed)

    def test_probability_boundaries_and_threshold_are_accepted(self):
        key = "EVT_PRIVACY__pii_candidate"
        for value, count in ((0, 0), (0.799, 0), (0.8, 1), (1, 1)):
            answers = copy.deepcopy(self.answers)
            answers[key]["noul"] = value
            with self.subTest(value=value):
                self.assertEqual(len(self.adapt(answers)["risk_cues"]), count)

    def test_provider_answer_order_does_not_change_evidence_ids(self):
        answers = copy.deepcopy(self.answers)
        for name in list(answers)[:2]:
            answers[name]["noul"] = 0.96
        reversed_answers = dict(reversed(list(answers.items())))
        self.assertEqual(self.adapt(answers), self.adapt(reversed_answers))

    def test_excess_cues_fail_instead_of_being_truncated(self):
        self.assertGreater(len(self.answers), 80)
        answers = {name: {"type": "noul", "noul": 1} for name in self.answers}
        with self.assertRaises(ValueError):
            self.adapt(answers)

    def test_no_questions_with_no_answers_is_valid(self):
        output = adapt_jev_response({"questions": {}, "state": {"events": []}},
                                    {"answers": {}})
        self.assertEqual(output["risk_cues"], [])

    def test_missing_locator_configuration_fails_explicitly(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            locate_issues(self.parsed["observation_detail"])

    def test_locator_timeout_stops_pipeline_before_relation_or_report(self):
        from unittest.mock import Mock
        relation, report = Mock(), Mock()
        with patch.dict(os.environ, {"VIDEO_MODEL_API_KEY": "mock-key",
                                     "VIDEO_MODEL_BASE_URL": "https://example.invalid"}), \
             self.assertRaises(TimeoutError):
            run_live(b"mock-video", 25_000, "synthetic",
                     parse_fn=lambda *_: PARSE,
                     locator_fn=Mock(side_effect=TimeoutError("timeout")),
                     relation_fn=relation, report_fn=report)
        relation.assert_not_called()
        report.assert_not_called()


class OptionalStageFailureTests(unittest.TestCase):
    def setUp(self):
        self.located = clean_issue_locator(copy.deepcopy(LOCATOR),
                                          clean_video_parse(copy.deepcopy(PARSE), 25_000))

    def test_empty_relation_answer_is_reviewed_and_not_marked_live(self):
        result = _run_models(self.located, 25_000, lambda _: {}, lambda _: None,
                             allow_relation=True, allow_report=False)
        finding = next(f for f in result["findings"] if f["policy_id"] == "R_DANGER_PROMOTION")
        self.assertEqual(result["meta"]["relation_check"], "INVALID_OUTPUT")
        self.assertEqual(result["meta"]["semantic_check"], "API_FAILED")
        self.assertNotEqual(finding["disposition"], "FLAG")

    def test_relation_timeout_degrades_without_a_strong_flag(self):
        def timeout(_):
            raise TimeoutError("provider unavailable")
        result = _run_models(self.located, 25_000, timeout, lambda _: None,
                             allow_relation=True, allow_report=False)
        self.assertEqual(result["meta"]["relation_check"], "FAILED")
        self.assertEqual(result["meta"]["semantic_check"], "API_FAILED")
        finding = next(f for f in result["findings"] if f["policy_id"] == "R_DANGER_PROMOTION")
        self.assertNotEqual(finding["disposition"], "FLAG")

    def test_invalid_report_uses_an_explicit_validated_fallback(self):
        from src.audit_report import validate_audit_report
        result = _run_models(self.located, 25_000, lambda _: None, lambda _: {},
                             allow_relation=False, allow_report=True)
        self.assertEqual(result["meta"]["audit_report"], "FALLBACK_INVALID_OUTPUT")
        self.assertIsNotNone(validate_audit_report(result["audit_report"], result,
                                                  result["findings"], 25_000))

    def test_relation_validation_is_not_disabled_by_python_optimization(self):
        import subprocess
        import sys
        code = """
from fixtures.compare_pead import load_input
from pipeline import clean_video_parse, clean_issue_locator
from src.relation_client import select_pairs, build_request, validate_response
raw=load_input('danger_promotion')
located=clean_issue_locator(raw['issue_locator'],clean_video_parse(raw['video_parse'],raw['duration_ms']))
request=build_request(select_pairs(located['observations'],raw['duration_ms']))
for name, answer in raw['relation']['answers'].items():
    if name.endswith('_relation'):
        answer['confidence']=True
results=validate_response(request,raw['relation'])
if not results or any(item['status'] != 'INVALID_RESPONSE' for item in results):
    raise SystemExit('validation was bypassed')
"""
        result = subprocess.run([sys.executable, "-O", "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
