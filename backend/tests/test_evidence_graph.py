"""Independent semantic oracle plus event, provenance and explanation guards."""
from __future__ import annotations

import copy
import itertools
import unittest

from src.argumentation import grounded
from src.evidence_graph import canonicalize, decide


def evidence(oid, tag, event="A", start=100, end=900, refs=None, quality="HIGH"):
    return {"id": oid, "tag": tag, "referent_key": event, "modality": "visual" if tag == "danger_action" else "speech",
            "start_ms": start, "end_ms": end, "source_refs": refs or ["S:" + oid], "time_confidence": quality}


def decision(a, s, stance="encourages_same"):
    return {"action_id": a, "stance_id": s, "stance": stance}


def evaluate(atoms, relations=None, coverage="FULL", limit=8):
    return decide(atoms, 30_000, coverage, 15_000, relations, counterfactual_limit=limit)


class GroundedSemanticsTests(unittest.TestCase):
    def test_all_three_node_attack_graphs_match_independent_complete_extension_oracle(self):
        names = ("a", "b", "c")
        possible = list(itertools.product(names, repeat=2))
        checked = 0
        for bits in itertools.product((False, True), repeat=len(possible)):
            attacks = {edge for edge, present in zip(possible, bits) if present}
            complete = []
            for members in itertools.product((False, True), repeat=len(names)):
                extension = {name for name, present in zip(names, members) if present}
                if any(a in extension and b in extension for a, b in attacks):
                    continue
                defended = {name for name in names if all(
                    any((defender, attacker) in attacks for defender in extension)
                    for attacker in names if (attacker, name) in attacks)}
                if defended == extension:
                    complete.append(extension)
            self.assertTrue(complete)
            expected = set.intersection(*complete)
            result = grounded(list(names), list(attacks))
            self.assertEqual(set(result["accepted"]), expected)
            self.assertTrue(set(result["accepted"]).isdisjoint(result["rejected"]))
            checked += 1
        self.assertEqual(checked, 2 ** 9)

    def test_empty_self_attack_mutual_attack_and_defended_chain(self):
        self.assertEqual(grounded([], [])["accepted"], [])
        self.assertEqual(grounded(["a"], [("a", "a")])["undecided"], ["a"])
        self.assertEqual(grounded(["a", "b"], [("a", "b"), ("b", "a")])["undecided"], ["a", "b"])
        self.assertEqual(grounded(["a", "b", "c"], [("a", "b"), ("b", "c")])["accepted"], ["a", "c"])

    def test_invalid_graphs_are_rejected(self):
        for arguments, attacks in ((["a", "a"], []), (["a"], [("a", "missing")])):
            with self.assertRaises(ValueError):
                grounded(arguments, attacks)


class EvidenceGraphTests(unittest.TestCase):
    def test_explicit_warning_defeats_wrong_model_confidence_by_conflict(self):
        atoms = [evidence("A1", "danger_action"), evidence("W1", "warning")]
        finding, graph = evaluate(atoms, [decision("A1", "W1")])
        self.assertEqual((finding["judgement"], finding["disposition"]), ("CONFLICTED", "REVIEW"))
        self.assertTrue(graph["attacks"])
        self.assertTrue(graph["event_decisions"][0]["argument_labels"]["undecided"])

    def test_a_warning_in_another_event_does_not_cancel_supported_risk(self):
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement"),
                 evidence("A2", "danger_action", "B"), evidence("W2", "warning", "B")]
        relations = [decision("A1", "P1"), decision("A2", "W2", "warns_same")]
        finding, graph = evaluate(atoms, relations)
        self.assertEqual(finding["disposition"], "FLAG")
        events = {e["event_key"]: e for e in graph["event_decisions"]}
        self.assertEqual(events["A"]["disposition"], "FLAG")
        self.assertEqual(events["B"]["disposition"], "NONE")

    def test_model_unrelated_for_another_phrase_does_not_defeat_valid_support(self):
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement"), evidence("P2", "encouragement")]
        finding, _ = evaluate(atoms, [decision("A1", "P1"), decision("A1", "P2", "unrelated")])
        self.assertEqual(finding["disposition"], "FLAG")

    def test_same_event_warning_cannot_be_removed_by_duplicate_support(self):
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement", refs=["S:F2"]),
                 evidence("P2", "encouragement", refs=["S:F2"]), evidence("W1", "warning")]
        finding, graph = evaluate(atoms, [decision("A1", "P1"), decision("A1", "P2")])
        self.assertEqual(finding["disposition"], "REVIEW")
        self.assertEqual(graph["aliases"]["P2"], "P1")
        self.assertEqual(len(graph["evidence"]), 3)

    def test_unknown_provenance_is_not_assumed_independent_or_merged_by_text(self):
        atoms = [evidence("P1", "encouragement"), evidence("P2", "encouragement")]
        for item in atoms:
            item.pop("source_refs")
        prepared = canonicalize(atoms, 30_000)
        self.assertEqual(len(prepared["atoms"]), 2)
        self.assertEqual(prepared["source_groups"], {})

    def test_same_source_aliases_keep_the_least_reliable_time_quality(self):
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement", refs=["S:F2"]),
                 evidence("P2", "encouragement", refs=["S:F2"], quality="LOW")]
        finding, _ = evaluate(atoms, [decision("A1", "P1"), decision("A1", "P2")])
        self.assertEqual(finding["disposition"], "REVIEW")

    def test_unknown_target_low_time_quality_and_missing_relation_cannot_flag(self):
        base = [evidence("A1", "danger_action"), evidence("P1", "encouragement")]
        unknown = copy.deepcopy(base)
        unknown[1]["referent_key"] = ""
        low = copy.deepcopy(base)
        low[1]["time_confidence"] = "LOW"
        for atoms, relations in ((unknown, [decision("A1", "P1")]), (low, [decision("A1", "P1")]), (base, None)):
            self.assertNotEqual(evaluate(atoms, relations)[0]["disposition"], "FLAG")

    def test_invalid_time_duplicate_ids_and_refused_coverage_fail_closed(self):
        base = [evidence("A1", "danger_action"), evidence("P1", "encouragement")]
        invalid = copy.deepcopy(base)
        invalid[1]["end_ms"] = 30_001
        duplicate = base + [copy.deepcopy(base[1])]
        for atoms in (invalid, duplicate):
            self.assertEqual(evaluate(atoms, [decision("A1", "P1")])[0]["disposition"], "REVIEW")
        finding, graph = evaluate(base, [decision("A1", "P1")], coverage="REFUSED")
        self.assertEqual(finding["disposition"], "RETRY")
        self.assertFalse(graph["certificates"])

    def test_timestamp_window_boundary(self):
        action = evidence("A1", "danger_action", start=0, end=1000)
        for start, supported in ((16_000, True), (16_001, False)):
            stance = evidence("P1", "encouragement", start=start, end=start + 100)
            result, _ = evaluate([action, stance], [decision("A1", "P1")])
            self.assertEqual(result["disposition"] == "FLAG", supported)

    def test_missing_upstream_warning_cannot_be_invented(self):
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement")]
        finding, graph = evaluate(atoms, [decision("A1", "P1")])
        self.assertEqual(finding["disposition"], "FLAG")
        self.assertEqual(finding["counter_ids"], [])
        self.assertTrue(graph["certificates"])

    def test_counterfactuals_use_frozen_evidence_ids_and_remove_all_aliases(self):
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement", refs=["S:F2"]),
                 evidence("P2", "encouragement", refs=["S:F2"])]
        _, graph = evaluate(atoms, [decision("A1", "P1"), decision("A1", "P2")])
        removed = next(item for item in graph["counterfactuals"] if "P1" in item["removed_ids"])
        self.assertEqual(removed["removed_ids"], ["P1", "P2"])
        self.assertNotEqual(removed["disposition"], "FLAG")

    def test_permutations_have_identical_graphs_and_do_not_modify_inputs(self):
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement"), evidence("W1", "warning")]
        relations = [decision("A1", "P1"), decision("A1", "W1")]
        original = copy.deepcopy(atoms)
        expected = evaluate(atoms, relations)
        for permutation in itertools.permutations(atoms):
            self.assertEqual(evaluate(list(permutation), list(reversed(relations))), expected)
        self.assertEqual(atoms, original)

    def test_every_attack_and_certificate_refers_to_real_graph_nodes(self):
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement")]
        _, graph = evaluate(atoms, [decision("A1", "P1")])
        ids = {a["id"] for a in graph["arguments"]}
        evidence_ids = {e["id"] for e in graph["evidence"]}
        for edge in graph["attacks"]:
            self.assertIn(edge["source"], ids)
            self.assertIn(edge["target"], ids)
        for certificate in graph["certificates"]:
            self.assertIn(certificate["argument_id"], ids)
            self.assertTrue(set(certificate["premise_ids"]).issubset(evidence_ids))

    def test_real_fusion_returns_independent_event_decisions(self):
        from src.pead_engine import build_event_findings
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement"),
                 evidence("A2", "danger_action", "B"), evidence("W2", "warning", "B")]
        finding, _ = evaluate(atoms, [decision("A1", "P1"), decision("A2", "W2", "warns_same")])
        rows = build_event_findings(atoms, [finding], 30_000)
        self.assertEqual({r["event_id"]: r["disposition"] for r in rows},
                         {"R_DANGER_PROMOTION:A": "FLAG", "R_DANGER_PROMOTION:B": "NONE"})

    def test_html_explanation_escapes_every_graph_field(self):
        from report import evidence_graph_content
        malicious = '<img src=x onerror=alert(1)>'
        html = evidence_graph_content({"arguments": [{"premise_ids": [malicious], "source_refs": [malicious], "kind": "MODEL_PROMOTION", "label": "IN"}],
                                       "event_decisions": [{"event_key": malicious, "disposition": "REVIEW"}],
                                       "counterfactuals": [{"removed_ids": [malicious]}]})
        self.assertNotIn(malicious, html)
        self.assertIn('&lt;img', html)

    def test_duplicate_risk_references_do_not_break_report_dimension_keys(self):
        from pipeline import clean_issue_locator, clean_video_parse
        from src.audit_report import build_fallback_audit_report
        from src.pead_engine import assess
        from fixtures import cases
        raw = copy.deepcopy(cases.CASES["self_harm_cue"]())
        raw["issue_locator"]["risk_cues"][0]["tag"] = "sexual_minor_risk"
        located = clean_issue_locator(raw["issue_locator"], clean_video_parse(raw["video_parse"], cases.DURATION_MS))
        findings = assess(located, cases.DURATION_MS)["findings"]
        report = build_fallback_audit_report(located, findings, cases.DURATION_MS)
        items = report["dimension_scores"]["evidence_traceability"]["items"]
        self.assertEqual(len(items), len({item["key"] for item in items}))

    def test_audit_model_gets_summary_not_the_full_argument_graph(self):
        from src.pead_engine import build_event_findings
        from src.audit_report import build_audit_context
        import json
        atoms = [evidence("A1", "danger_action"), evidence("P1", "encouragement")]
        finding, _ = evaluate(atoms, [decision("A1", "P1")])
        context = build_audit_context({"observations": atoms}, [finding],
                                      build_event_findings(atoms, [finding], 30_000))
        encoded = json.dumps(context)
        self.assertNotIn('"argument_labels"', encoded)
        self.assertNotIn('"iterations"', encoded)
        self.assertIn('"event_decisions"', encoded)
        self.assertEqual(context["findings"][0]["supporting_ids"], finding["supporting_ids"])


if __name__ == "__main__":
    unittest.main()
