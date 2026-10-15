"""Meaningful ablation guards: fixed inputs, fair control, disclosed failures."""
from __future__ import annotations

import copy
import itertools
import unittest
from unittest.mock import patch

from fixtures.compare_pead import SCENARIOS, artifacts, build, compare_input, digest, load_input, simple_mapping
from fixtures.truth_table import _answers_payload
from pipeline import clean_issue_locator, clean_video_parse
from src.relation_client import CHOICES, select_pairs


class MockComparisonTests(unittest.TestCase):
    def test_comparison_is_deterministic_and_does_not_call_providers(self):
        with patch("src.model_gateway._client", side_effect=AssertionError("network")), \
             patch("src.issue_locator_client.urllib.request.urlopen", side_effect=AssertionError("network")), \
             patch("src.relation_client.query_relations", side_effect=AssertionError("network")):
            first, second = build(), build()
        self.assertEqual(first, second)
        self.assertEqual(first[0]["mode"], "MOCK_SYNTHETIC")
        self.assertEqual(first[0]["external_api_calls"], 0)

    def test_two_arms_share_input_and_do_not_modify_it(self):
        for name in SCENARIOS:
            frozen = load_input(name)
            original = copy.deepcopy(frozen)
            row = compare_input(name, frozen)
            self.assertEqual(frozen, original)
            self.assertEqual(row["without_pead_input_sha256"], row["with_pead_input_sha256"])
            self.assertEqual(row["input_sha256"], digest(frozen))

    def test_control_does_not_call_pead(self):
        frozen = load_input("danger_promotion")
        located = clean_issue_locator(frozen["issue_locator"],
                                     clean_video_parse(frozen["video_parse"], frozen["duration_ms"]))
        with patch("src.pead_engine.assess", side_effect=AssertionError("PEAD in control")), \
             patch("src.relation_fusion.assess", side_effect=AssertionError("PEAD in control")):
            self.assertEqual(simple_mapping(located, frozen["duration_ms"], frozen["relation"])["disposition"], "FLAG")

    def test_control_already_reviews_mixed_low_confidence_and_missing_answers(self):
        frozen = load_input("danger_promotion")
        located = clean_issue_locator(frozen["issue_locator"],
                                     clean_video_parse(frozen["video_parse"], frozen["duration_ms"]))
        pairs = select_pairs(located["observations"], frozen["duration_ms"])
        self.assertEqual(len(pairs), 2)
        mixed = {"answers": _answers_payload(located, ("encourages_same", "warns_same"))}
        low = copy.deepcopy(frozen["relation"])
        for key, answer in low["answers"].items():
            if key.endswith("_relation"):
                answer["confidence"] = 0.1
        for relation in (None, {}, mixed, low):
            with self.subTest(relation=relation):
                self.assertEqual(simple_mapping(located, frozen["duration_ms"], relation)["disposition"], "REVIEW")

    def test_structural_and_same_event_counter_context_conflicts_are_reviewed(self):
        conflict = compare_input("relation_override_conflict", load_input("relation_override_conflict"), "REVIEW")
        failure = compare_input("relation_wrong_encouragement", load_input("relation_wrong_encouragement"), "REVIEW")
        self.assertEqual(conflict["without_pead"]["disposition"], "FLAG")
        self.assertEqual(conflict["with_pead"]["disposition"], "REVIEW")
        self.assertEqual(failure["with_pead"]["disposition"], "REVIEW")
        self.assertTrue(failure["with_pead_meets_synthetic_expectation"])

    def test_enumeration_covers_every_choice_combination_exactly_once(self):
        report, inputs = build()
        expected = set()
        for name, frozen in inputs["inputs"].items():
            located = clean_issue_locator(frozen["issue_locator"],
                                         clean_video_parse(frozen["video_parse"], frozen["duration_ms"]))
            pairs = select_pairs(located["observations"], frozen["duration_ms"])
            if pairs:
                expected.update((name, choices) for choices in itertools.product(sorted(CHOICES), repeat=len(pairs)))
        actual = [(row["name"], tuple(row["relation_choices"])) for row in report["enumeration"]]
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(expected))

    def test_summary_reconciles_to_rows_and_keeps_review_separate(self):
        report, _ = build()
        for prefix, rows in (("curated", report["curated_cases"]), ("enumeration", report["enumeration"])):
            summary = report[f"{prefix}_summary"]
            self.assertEqual(summary["count"], len(rows))
            for arm in ("without_pead", "with_pead"):
                self.assertEqual(sum(summary[arm].values()), len(rows))
                self.assertIn("REVIEW", summary[arm])
            self.assertEqual(summary["changed"], sum(row["changed"] for row in rows))

    def test_frozen_inputs_and_outputs_are_reproducible(self):
        report, bundle = build()
        for name, frozen in bundle["inputs"].items():
            self.assertEqual(bundle["sha256"][name], digest(frozen))
        self.assertEqual(artifacts(report, bundle), artifacts(*build()))


if __name__ == "__main__":
    unittest.main()
