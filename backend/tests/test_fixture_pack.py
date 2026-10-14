"""Fixture-pack regression tests.

These keep the curated mock cases (``backend/fixtures/cases``) honest:

* every case still validates through the real pipeline and still behaves the way
  its expectations file claims;
* regenerating the fixtures is a no-op, so the checked-in JSON cannot silently
  drift from the case definitions;
* the pinned defects in ``fixtures/README.md`` are still reproducible.

Run with the rest of the suite from ``backend/``:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from fixtures import cases as case_defs
from fixtures import generate, validate


class FixturePackTests(unittest.TestCase):
    def test_every_case_matches_its_expectations(self):
        for name in case_defs.CASE_ORDER:
            with self.subTest(case=name):
                validate.validate_case(name)

    def test_fixtures_match_their_case_definitions(self):
        stale = generate.stale_files()
        self.assertEqual(
            stale, [], "fixture files are stale; run `python -m fixtures.generate`")

    def test_manifest_indexes_every_case(self):
        manifest = generate.build_manifest(
            [generate.build_case(name) for name in case_defs.CASE_ORDER])
        self.assertEqual(manifest["case_order"], list(case_defs.CASE_ORDER))
        self.assertEqual(len(manifest["cases"]), len(case_defs.CASE_ORDER))

    def test_known_report_failures_are_still_pinned(self):
        """Every case in KNOWN_REPORT_FAILURES must still fail, and nothing else.

        The set is empty now that the builder handles findings without an event of
        their own. If a future regression reintroduces a crash, the case that
        exposes it must be listed here with a fixtures/README.md note.
        """
        for name in case_defs.CASE_ORDER:
            state = validate.simulate(
                validate.load(name, "video_parse_response.json"),
                validate.load(name, "issue_locator_response.json"),
                case_defs.DURATION_MS, relation_raw=None)
            with self.subTest(case=name):
                if name in validate.KNOWN_REPORT_FAILURES:
                    self.assertIsNone(state["audit_report"])
                else:
                    self.assertIsNotNone(
                        state["audit_report"],
                        f"{name} can no longer produce a report: "
                        f"{state['audit_report_error']}")

    def test_missing_relation_service_is_more_conservative_than_a_negative_answer(self):
        """The H1 contrast: same evidence, only the relation answer differs."""
        answered = validate.simulate(
            validate.load("unrelated_promotion", "video_parse_response.json"),
            validate.load("unrelated_promotion", "issue_locator_response.json"),
            case_defs.DURATION_MS,
            relation_raw=validate.load("unrelated_promotion", "relation_response.json"))
        unanswered = validate.simulate(
            validate.load("unrelated_without_relation_service", "video_parse_response.json"),
            validate.load("unrelated_without_relation_service", "issue_locator_response.json"),
            case_defs.DURATION_MS, relation_raw=None)

        def disposition(state):
            return next(f["disposition"] for f in state["findings"]
                        if f["policy_id"] == "R_DANGER_PROMOTION")

        self.assertEqual(disposition(answered), "NONE")
        self.assertEqual(disposition(unanswered), "REVIEW")

    def test_studied_risks_are_exercised_by_some_case(self):
        matrix = validate.policy_matrix()
        for policy in ("R_DANGER_PROMOTION", "R_VIOLENCE",
                       "R_PRIVACY_EXPOSURE", "R_MARKETING_CLAIM"):
            with self.subTest(policy=policy):
                self.assertTrue(
                    matrix[policy],
                    f"{policy} has no case with a non-NONE disposition")


if __name__ == "__main__":
    unittest.main()
