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
        """If the report builder is fixed, this test says to update the pack."""
        for name in sorted(validate.KNOWN_REPORT_FAILURES):
            with self.subTest(case=name):
                state = validate.simulate(
                    validate.load(name, "video_parse_response.json"),
                    validate.load(name, "issue_locator_response.json"),
                    case_defs.DURATION_MS, relation_raw=None)
                self.assertIsNone(
                    state["audit_report"],
                    f"{name} now produces an audit report; remove it from "
                    "KNOWN_REPORT_FAILURES and record the verdict in its expectations")

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
