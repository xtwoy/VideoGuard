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

    def test_every_policy_is_exercised_by_some_case(self):
        """All ten policies must have a case asserting a non-NONE disposition.

        The four studied risks are required to have a substantive positive case;
        the six direct-cue policies are covered by their own single-cue cases.
        """
        matrix = validate.policy_matrix()
        for policy in case_defs.ALL_POLICIES:
            with self.subTest(policy=policy):
                self.assertTrue(
                    matrix[policy],
                    f"{policy} has no case with a non-NONE disposition")

    def test_studied_risks_have_a_case_beyond_partial_coverage(self):
        """The four studied risks must not rely on RECHECK alone."""
        matrix = validate.policy_matrix()
        for policy in ("R_DANGER_PROMOTION", "R_VIOLENCE",
                       "R_PRIVACY_EXPOSURE", "R_MARKETING_CLAIM"):
            with self.subTest(policy=policy):
                self.assertTrue(
                    [name for name in matrix[policy] if name != "partial_coverage"],
                    f"{policy} is only exercised by the partial-coverage case")


    # --- the mechanism that makes PEAD more than a model wrapper -------------

    def _judgement_and_disposition(self, name: str) -> tuple[str, str]:
        state = validate.simulate(
            validate.load(name, "video_parse_response.json"),
            validate.load(name, "issue_locator_response.json"),
            case_defs.DURATION_MS,
            relation_raw=validate.load(name, "relation_response.json"))
        finding = next(f for f in state["findings"]
                       if f["policy_id"] == "R_DANGER_PROMOTION")
        return finding["judgement"], finding["disposition"]

    def test_pead_overrides_a_confident_answer_the_structure_contradicts(self):
        """A provider that is confidently wrong must not force a strong flag.

        The two cues cite different referent keys, so the structural constraint
        fires even though the provider answered ``encourages_same``.
        """
        self.assertEqual(self._judgement_and_disposition("relation_override_conflict"),
                         ("CONFLICTED", "REVIEW"))

    def test_known_limitation_model_error_on_warning_footage_is_not_corrected(self):
        """The counterpart of the test above, and a limitation we publish.

        When the action and the warning belong to the same event there is no
        structural conflict, so PEAD has no independent signal and follows the
        provider. If this ever starts behaving differently, update the limitation
        note in fixtures/README.md rather than silently dropping it.
        """
        self.assertEqual(
            self._judgement_and_disposition("relation_wrong_encouragement"),
            ("SUPPORTED", "FLAG"))


if __name__ == "__main__":
    unittest.main()
