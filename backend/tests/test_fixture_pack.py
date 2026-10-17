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

import json
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
        """Final verdict for a case, using its stored relation response if any.

        A missing relation_response.json means the case deliberately runs without
        one (either no candidate pairs, or a hard PEAD conflict that is not
        negotiable by the relation stage).
        """
        relation_path = validate.CASE_ROOT / name / "relation_response.json"
        relation_raw = (validate.load(name, "relation_response.json")
                        if relation_path.exists() else None)
        state = validate.simulate(
            validate.load(name, "video_parse_response.json"),
            validate.load(name, "issue_locator_response.json"),
            case_defs.DURATION_MS, relation_raw=relation_raw)
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

    def test_same_event_warning_blocks_wrong_model_encouragement(self):
        """The former pinned failure is now an explicit corrected regression."""
        self.assertEqual(self._judgement_and_disposition("relation_wrong_encouragement"),
                         ("CONFLICTED", "REVIEW"))

    def test_counter_evidence_does_not_depend_on_the_chosen_tag(self):
        """Encouragement plus cautionary framing must be a conflict either way."""
        self.assertEqual(
            self._judgement_and_disposition("counter_context_tagging"),
            ("CONFLICTED", "REVIEW"))


class TruthTableTests(unittest.TestCase):
    """The exhaustive decision table is the evidence for PEAD's rule behaviour."""

    def test_every_combination_is_total_and_deterministic(self):
        from fixtures import truth_table
        for name in truth_table._cases_with_pairs():
            with self.subTest(case=name):
                result = truth_table.enumerate_case(name)
                self.assertEqual(result["problems"], [])
                self.assertEqual(result["combination_count"],
                                 4 ** result["pair_count"])

    def test_a_supported_pair_survives_an_unrelated_other_phrase(self):
        """An unrelated second phrase is not a warning against the first claim."""
        from fixtures import truth_table
        result = truth_table.enumerate_case("danger_promotion")
        flagged = [row for row in result["rows"] if row["disposition"] == "FLAG"]
        self.assertTrue(flagged)
        for row in flagged:
            self.assertIn("encourages_same", row["answers"])
            self.assertTrue(set(row["answers"]).issubset({"encourages_same", "unrelated"}))

    def test_warning_regression_cannot_flag_under_any_relation_choice(self):
        from fixtures import truth_table
        result = truth_table.enumerate_case("relation_wrong_encouragement")
        self.assertTrue(result["rows"])
        self.assertFalse([row for row in result["rows"] if row["disposition"] == "FLAG"])


class ArgumentationReportTests(unittest.TestCase):
    """The attack/defence report is the evidence for PEAD's argumentation behaviour.

    Each scenario must keep producing the grounded labels and attack edges it
    documents. A silent change here would mean the published mechanism no longer
    matches the code.
    """

    def test_every_scenario_matches_its_expected_labels(self):
        from fixtures import argumentation_report

        report = argumentation_report.build()
        self.assertEqual(report["problems"], [])

    def _labels(self, index: int) -> dict:
        from fixtures import argumentation_report

        scenario = argumentation_report.build()["scenarios"][index]
        return {argument["id"]: argument["label"] for argument in scenario["arguments"]}

    def test_a_counter_argument_really_defeats_local_support(self):
        """Bidirectional attack where the counter has no attacker -> support is OUT."""
        from fixtures import argumentation_report

        labels = self._labels(0)
        self.assertEqual(labels['LOCAL_PROMOTION:["E01","E02"]'], "OUT")
        self.assertEqual(labels['COUNTER_CONTEXT:["E01","E03"]'], "IN")
        self.assertTrue(argumentation_report.build()["scenarios"][0]["cycles"],
                        "双向攻击应被识别为循环")

    def test_a_confidently_wrong_model_answer_is_defeated_by_structure(self):
        """The provider claims one event; the parse recorded two."""
        from fixtures import argumentation_report

        self.assertEqual(self._labels(1)['MODEL_PROMOTION:["E01","E02"]'], "OUT")
        self.assertEqual(
            argumentation_report.build()["scenarios"][1]["finding"]["judgement"],
            "CONFLICTED")

    def test_the_models_own_counter_argument_can_be_defeated(self):
        """A claimed warning that structurally belongs elsewhere is rejected."""
        from fixtures import argumentation_report

        self.assertEqual(self._labels(2)['MODEL_COUNTER:["E01","E02"]'], "OUT")
        self.assertEqual(
            argumentation_report.build()["scenarios"][2]["finding"]["disposition"],
            "REVIEW")

    def test_pure_support_has_no_attacks_and_is_accepted(self):
        from fixtures import argumentation_report

        scenario = argumentation_report.build()["scenarios"][3]
        self.assertEqual(scenario["attacks"], [])
        self.assertEqual(scenario["labels"].get("IN"), 4)
        self.assertEqual(scenario["finding"]["disposition"], "FLAG")


class ArgumentationHtmlTests(unittest.TestCase):
    """The demo page must stay self-contained and consistent with the models."""

    def test_page_matches_the_current_scenarios(self):
        from fixtures import argumentation_html

        expected = argumentation_html.render(argumentation_html.build())
        path = argumentation_html.REPORT
        self.assertTrue(path.exists(), "reports/pead-argumentation.html 未生成")
        self.assertEqual(path.read_text(encoding="utf-8"), expected,
                         "HTML 与当前模型不一致；运行 python -m fixtures.argumentation_html")

    def test_page_is_offline_safe(self):
        """A demo shown on someone else's machine must need no network or script."""
        from fixtures import argumentation_html

        html = argumentation_html.REPORT.read_text(encoding="utf-8")
        self.assertNotIn("<script", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertIn('Content-Security-Policy', html)

    def test_page_shows_labels_and_attack_edges(self):
        from fixtures import argumentation_html

        html = argumentation_html.REPORT.read_text(encoding="utf-8")
        for token in (">IN<", ">OUT<", "REFERENT_CONFLICT", "COUNTER_CONTEXT", "<svg"):
            with self.subTest(token=token):
                self.assertIn(token, html)


class PromptContractTests(unittest.TestCase):
    """Prompts must ask for exactly what the validators accept.

    A prompt that names a field the validator drops wastes model output; a prompt
    that omits a required field makes every real response fail at the parse stage.
    Both are invisible until someone spends a key, so they are checked statically.
    """

    def test_every_prompt_contract_check_passes(self):
        from fixtures import prompt_contract

        report = prompt_contract.build()
        self.assertEqual(report["failed"], [],
                         "prompt 与校验器契约不一致；运行 "
                         "python -m fixtures.prompt_contract 查看明细")

    def test_enum_extraction_handles_both_prompt_notations(self):
        """Regression: the scan must see pipe lists and backticked prose values."""
        from fixtures import prompt_contract

        self.assertEqual(
            prompt_contract.token_sets('"a": "FULL | PARTIAL | UNKNOWN"'),
            [{"FULL", "PARTIAL", "UNKNOWN"}])
        self.assertIn({"SAME_EVENT", "UNCERTAIN"},
                      prompt_contract.token_sets("使用 `SAME_EVENT`；否则 `UNCERTAIN`"))
        # A whole document must never collapse into one bogus candidate.
        self.assertEqual(prompt_contract.token_sets("no enum here"), [])

    def test_video_parse_names_every_value_the_model_must_emit(self):
        from fixtures import prompt_contract

        document = (prompt_contract.PROMPTS / "video_parse_system.md").read_text(
            encoding="utf-8")
        template = prompt_contract.template_of("video_parse_system.md")
        from pipeline import VALID_STANCE
        matched, tokens = prompt_contract.match_enum(set(VALID_STANCE), document, template)
        self.assertTrue(matched, "context.stance 的取值必须写在 prompt 里")
        self.assertEqual(tokens, VALID_STANCE)

class ManifestProvenanceTests(unittest.TestCase):
    """Frozen stage-4 replies are synthetic; the manifest must say so.

    Freezing proves the bytes were not rewritten. It does not turn a locally built
    report into a captured provider response, so the origin is recorded per case.
    """

    def test_every_case_declares_where_its_stage4_reply_came_from(self):
        manifest = json.loads((generate.HERE / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("audit_report_origin_note", manifest)
        for entry in manifest["cases"]:
            self.assertEqual(entry.get("audit_report_origin"), "synthetic_builder",
                             f"{entry['name']} 缺少阶段四回包来源标注")
        self.assertIn("不是真实模型回包", manifest["audit_report_origin_note"])

if __name__ == "__main__":
    unittest.main()
