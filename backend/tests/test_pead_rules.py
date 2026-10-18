"""Runtime integration, configuration safety, resource boundaries and provenance."""
from __future__ import annotations
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from src.argumentation import ArgumentationLimitError, grounded
from src.evidence_graph import decide
from src.pead_rules import Condition, FACTS, RuleSet, load_rules


def observations():
    return [{"id": oid, "tag": tag, "referent_key": "event-A", "modality": modality,
             "start_ms": 0, "end_ms": 1000, "source_refs": ["source:" + oid], "time_confidence": "HIGH"}
            for oid, tag, modality in [("action", "danger_action", "visual"),
                                       ("promotion", "encouragement", "speech")]]


def relation():
    return [{"action_id": "action", "stance_id": "promotion", "stance": "encourages_same"}]


class OpenSourceSolverTests(unittest.TestCase):
    def test_pyarg_is_the_runtime_solver_and_exception_has_no_fallback(self):
        from src import argumentation
        with patch.object(argumentation, "get_grounded_extension", wraps=argumentation.get_grounded_extension) as solver:
            result = grounded(["a", "b"], [("a", "b")])
            solver.assert_called_once()
        self.assertEqual(result["backend"]["name"], "PyArg")
        self.assertFalse(result["backend"]["fallback"])
        with patch.object(argumentation, "get_grounded_extension", side_effect=RuntimeError("broken solver")):
            with self.assertRaisesRegex(RuntimeError, "broken solver"):
                grounded(["a"], [])

    def test_networkx_cycles_and_defense_witnesses_are_consistent(self):
        result = grounded(["a", "b", "c", "d", "e"], [("a", "b"), ("b", "c"), ("d", "e"), ("e", "d")])
        self.assertEqual(result["cycles"], [["d", "e"]])
        self.assertEqual(result["explanations"]["c"]["defenses"],
                         [{"attacker_id": "b", "accepted_defender_ids": ["a"]}])
        self.assertEqual(result["explanations"]["b"]["defeated_by"], ["a"])
        self.assertEqual(result["explanations"]["d"]["unresolved_attacker_ids"], ["e"])
        self.assertEqual(grounded(["a"], [("a", "a")])["cycles"], [["a"]])

    def test_budget_boundaries_and_duplicate_attacks(self):
        result = grounded(["a", "b"], [("a", "b"), ("a", "b")], max_arguments=2, max_attacks=1)
        self.assertEqual(result["statistics"]["attacks"], 1)
        with self.assertRaises(ArgumentationLimitError):
            grounded(["a", "b"], [], max_arguments=1)
        with self.assertRaises(ArgumentationLimitError):
            grounded(["a", "b"], [("a", "b"), ("b", "a")], max_attacks=1)


class RuleConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.rules = load_rules()
        self.raw = self.rules.model_dump(mode="json")

    def test_unknown_predicate_extra_field_and_invalid_limits_rejected(self):
        edits = []
        bad = copy.deepcopy(self.raw);bad["argument_rules"][0]["when"] = {"all_of": ["typo"]};edits.append(bad)
        bad = copy.deepcopy(self.raw);bad["extra"] = True;edits.append(bad)
        for invalid in (0, -1, True, "512", 2049):
            bad = copy.deepcopy(self.raw);bad["limits"]["max_arguments"] = invalid;edits.append(bad)
        bad = copy.deepcopy(self.raw);bad["argument_rules"][0]["when"] = {"all_of": ["same_event"], "none_of": ["same_event"]};edits.append(bad)
        for bad in edits:
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):RuleSet.model_validate(bad)

    def test_duplicate_ids_tied_priorities_missing_kinds_and_missing_default_rejected(self):
        edits=[]
        bad=copy.deepcopy(self.raw);bad["argument_rules"][1]["id"]=bad["argument_rules"][0]["id"];edits.append(bad)
        bad=copy.deepcopy(self.raw);bad["decision_rules"][1]["priority"]=bad["decision_rules"][0]["priority"];edits.append(bad)
        bad=copy.deepcopy(self.raw);bad["argument_rules"]=[r for r in bad["argument_rules"] if r["kind"]!="LOCAL_PROMOTION"];edits.append(bad)
        bad=copy.deepcopy(self.raw);bad["decision_rules"]=[r for r in bad["decision_rules"] if r["id"]!="D_DEFAULT"];edits.append(bad)
        for bad in edits:
            with self.assertRaises(ValidationError):RuleSet.model_validate(bad)

    def test_critical_guards_cannot_be_removed_weakened_or_bypassed(self):
        for rid in ("D_UNAVAILABLE", "D_RESOURCE", "D_INVALID", "D_UNCERTAIN", "D_PARTIAL", "D_STANCE_CONFLICT", "D_REFERENT_CONFLICT"):
            for operation in ("remove", "weaken"):
                bad=copy.deepcopy(self.raw)
                if operation=="remove":bad["decision_rules"]=[r for r in bad["decision_rules"] if r["id"]!=rid]
                else:next(r for r in bad["decision_rules"] if r["id"]==rid)["when"]={}
                with self.subTest(rule=rid, operation=operation):
                    with self.assertRaises(ValidationError):RuleSet.model_validate(bad)
        bad=copy.deepcopy(self.raw)
        next(r for r in bad["decision_rules"] if r["id"]=="D_MODEL_SUPPORTED")["when"]={}
        with self.assertRaises(ValidationError):RuleSet.model_validate(bad)
        bad=copy.deepcopy(self.raw)
        next(r for r in bad["decision_rules"] if r["id"]=="D_MODEL_SUPPORTED")["priority"]=995
        with self.assertRaises(ValidationError):RuleSet.model_validate(bad)

    def test_snapshot_is_deeply_immutable_and_hash_ignores_json_formatting(self):
        with self.assertRaises(ValidationError):self.rules.version="2.0.0"
        with self.assertRaises(ValidationError):self.rules.limits.max_arguments=1
        with self.assertRaises(ValidationError):self.rules.argument_rules[0].when.all_of=()
        roundtrip=RuleSet.model_validate_json(json.dumps(self.raw,indent=4,sort_keys=True))
        self.assertEqual(roundtrip.fingerprint,self.rules.fingerprint)
        changed=copy.deepcopy(self.raw);changed["version"]="1.0.1"
        self.assertNotEqual(RuleSet.model_validate(changed).fingerprint,self.rules.fingerprint)

    def test_malformed_file_fails_instead_of_loading_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"rules.json";path.write_text('{broken',encoding='utf-8')
            with self.assertRaises(ValidationError):load_rules(path)

    def test_predicates_use_boolean_values_and_no_eval(self):
        condition=Condition(all_of=("same_event",),none_of=("time_uncertain",))
        self.assertTrue(condition.matches({"same_event":True,"time_uncertain":False}))
        self.assertFalse(condition.matches({"same_event":False,"time_uncertain":False}))
        with self.assertRaises(ValueError):condition.matches({"same_event":1,"time_uncertain":False})
        with self.assertRaises(ValueError):condition.matches({})

    def test_tightening_a_support_generation_rule_is_rejected(self):
        """A stricter support condition would erase the risk instead of flagging it.

        This used to be accepted as a normal configuration change: the same input
        went from FLAG to NONE, and the test recorded that as correct behaviour.
        It is a bypass — the risk disappears because no argument was generated.
        """
        changed = copy.deepcopy(self.raw)
        next(r for r in changed["argument_rules"]
             if r["kind"] == "LOCAL_PROMOTION")["when"]["all_of"].append("relation_review")
        with self.assertRaises(ValidationError):
            RuleSet.model_validate(changed)

    def test_deleting_the_support_decisions_is_rejected(self):
        changed = copy.deepcopy(self.raw)
        changed["decision_rules"] = [
            rule for rule in changed["decision_rules"]
            if rule["id"] not in ("D_MODEL_SUPPORTED", "D_LOCAL_SUPPORTED")
        ]
        with self.assertRaises(ValidationError):
            RuleSet.model_validate(changed)

    def test_extra_condition_on_a_support_decision_is_rejected(self):
        changed = copy.deepcopy(self.raw)
        next(rule for rule in changed["decision_rules"]
             if rule["id"] == "D_LOCAL_SUPPORTED")["when"]["all_of"].append("accepted_model_support")
        with self.assertRaises(ValidationError):
            RuleSet.model_validate(changed)

    def test_accepted_support_always_reaches_a_risk_decision(self):
        """Semantic invariant: support may not end in the non-supporting default."""
        facts = {name: False for name in FACTS}
        facts.update(accepted_support=True, has_support=True, accepted_model_support=True)
        selected, _ = self.rules.decision(facts)
        self.assertEqual((selected.judgement, selected.disposition), ("SUPPORTED", "FLAG"))

        # The invariant must hold for every rule set that loaded successfully, not
        # just the shipped one. Re-validate the loaded model and re-run the check.
        reloaded = RuleSet.model_validate(self.raw)
        selected, _ = reloaded.decision(facts)
        self.assertEqual((selected.judgement, selected.disposition), ("SUPPORTED", "FLAG"))

    def test_a_stricter_new_rule_still_takes_effect(self):
        """Configuration is not frozen: adding a *more cautious* rule works."""
        changed = copy.deepcopy(self.raw)
        changed["decision_rules"].append({
            "id": "D_EXTRA_CAUTION", "description": "额外保守规则，仅用于验证配置可生效",
            "priority": 50,
            "when": {"all_of": ["unrelated_confirmed"], "any_of": [], "none_of": []},
            "judgement": "INSUFFICIENT", "disposition": "REVIEW",
            "reason_code": "MISSING_SEMANTIC_RELATION",
        })
        ruleset = RuleSet.model_validate(changed)
        facts = {name: False for name in FACTS}
        facts.update(unrelated_confirmed=True)
        selected, _ = ruleset.decision(facts)
        self.assertEqual(selected.id, "D_EXTRA_CAUTION")

    def test_all_matching_decisions_recorded_and_highest_priority_wins(self):
        facts={name:False for name in FACTS};facts.update(coverage_failure=True,accepted_support=True,accepted_model_support=True)
        selected,trace=self.rules.decision(facts)
        self.assertEqual(selected.id,"D_UNAVAILABLE")
        matches=[r for r in trace["evaluated_rules"] if r["matched"]]
        self.assertEqual(selected.priority,max(r["priority"] for r in matches))
        self.assertIn("D_MODEL_SUPPORTED",{r["rule_id"] for r in matches})


class RuntimeTraceTests(unittest.TestCase):
    def test_graph_overflow_routes_to_review_without_running_solver(self):
        raw=load_rules().model_dump(mode="json");raw["limits"]["max_arguments"]=1
        with patch("src.argumentation.get_grounded_extension",side_effect=AssertionError("must not run")):
            finding,graph=decide(observations(),2000,"FULL",15000,relation(),ruleset=RuleSet.model_validate(raw))
        self.assertEqual(finding["disposition"],"REVIEW")
        self.assertEqual(finding["reason_code"],"ARGUMENTATION_RESOURCE_LIMIT")
        self.assertFalse(graph["certificates"])
        self.assertFalse(graph["event_decisions"][0]["argument_labels"]["executed"])

    def test_removal_checks_reuse_same_snapshot_and_frozen_relations(self):
        rules=load_rules()
        with patch("src.evidence_graph.load_rules",return_value=rules) as loader:
            finding,graph=decide(observations(),2000,"FULL",15000,relation())
        loader.assert_called_once()
        self.assertEqual(finding["disposition"],"FLAG")
        self.assertTrue(graph["counterfactuals"])
        self.assertTrue(all(row["ruleset_sha256"]==graph["ruleset"]["sha256"] for row in graph["counterfactuals"]))
        ids={r.id for r in rules.argument_rules}
        self.assertTrue(all(row["rule_id"] in ids for row in graph["rule_firings"]))

    def test_joint_assessment_uses_one_snapshot_for_baseline_and_treatment(self):
        from src.relation_fusion import assess_joint
        with patch("src.relation_fusion.load_rules",wraps=load_rules) as loader:
            result=assess_joint({"coverage":"FULL","observations":observations()},2000)
        loader.assert_called_once()
        self.assertEqual(result["baseline"]["pead_audit"]["ruleset"],result["merged"]["pead_audit"]["ruleset"])

    def test_counterfactual_budget_and_invalid_parameters(self):
        raw=load_rules().model_dump(mode="json");raw["limits"]["max_counterfactuals"]=1
        _,graph=decide(observations(),2000,"FULL",15000,relation(),counterfactual_limit=100,ruleset=RuleSet.model_validate(raw))
        self.assertEqual(len(graph["counterfactuals"]),1)
        self.assertTrue(graph["counterfactuals_truncated"])
        for invalid in (-1,True,"8"):
            with self.assertRaises(ValueError):decide([],2000,"FULL",15000,counterfactual_limit=invalid)

    def test_report_exposes_rules_and_escapes_new_explanation_fields(self):
        from report import evidence_graph_content
        _,graph=decide(observations(),2000,"FULL",15000,relation())
        html=evidence_graph_content(graph)
        self.assertIn("PyArg",html);self.assertIn("规则命中与冲突追踪",html)
        evil='<script>alert(1)</script>'
        graph["ruleset"]["sha256"]=evil
        graph["arguments"][0]["rule_ids"]=[evil]
        graph["event_decisions"][0]["decision_trace"]["selected_rule_id"]=evil
        graph["event_decisions"][0]["argument_labels"]["cycles"]=[[evil]]
        graph["arguments"][0]["label"]="OUT"
        graph["arguments"][0]["explanation"]={"defeated_by":[evil]}
        rendered=evidence_graph_content(graph)
        self.assertNotIn(evil,rendered);self.assertIn('&lt;script&gt;',rendered)

    def test_health_exposes_actual_solver_and_rule_snapshot(self):
        from fastapi.testclient import TestClient
        from main import app
        response=TestClient(app).get('/api/health')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["pead"]["solver"]["name"],"PyArg")
        self.assertEqual(response.json()["pead"]["ruleset_sha256"],load_rules().fingerprint)

    def test_demo_http_roundtrip_preserves_solver_trace_and_exported_report(self):
        from fastapi.testclient import TestClient
        from main import app
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VIDEOGUARD_DB": str(Path(directory)/"reviews.db")}):
            client=TestClient(app)
            response=client.post('/api/demo')
            self.assertEqual(response.status_code,200)
            record=response.json()
            graph=record["result"]["pead_audit"]
            self.assertEqual(graph["solver"]["name"],"PyArg")
            self.assertTrue(graph["rule_firings"])
            stored=client.get('/api/reviews/'+record['id']).json()
            self.assertEqual(stored['result']['pead_audit'],graph)
            report=client.get('/api/reviews/'+record['id']+'/report')
            self.assertEqual(report.status_code,200)
            self.assertIn(graph['ruleset']['sha256'],report.text)
            self.assertIn('规则命中与冲突追踪',report.text)
            self.assertIn('合成演示，非真实视频审核',report.text)

    def test_solver_failure_on_upload_is_persisted_as_error(self):
        from fastapi.testclient import TestClient
        from main import app
        from pipeline import run_demo
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"VIDEOGUARD_DB": str(Path(directory)/"reviews.db")}), \
                patch('main.probe_duration_ms',return_value=25000), \
                patch('main.run_live',side_effect=lambda *args:run_demo()), \
                patch('src.argumentation.get_grounded_extension',side_effect=RuntimeError('solver failed')):
            client=TestClient(app)
            response=client.post('/api/reviews',data={'consent':'true'},files={'video':('test.mp4',b'\x00\x00\x00\x18ftypisom','video/mp4')})
            self.assertEqual(response.status_code,502)
            record=client.get('/api/reviews/'+response.json()['detail']['review_id']).json()
            self.assertEqual(record['status'],'ERROR')
            self.assertEqual(record['result']['findings'],[])


class ArgumentConstructionTests(unittest.TestCase):
    """The graph must describe the evidence, not the order rules happened to fire."""

    def setUp(self):
        self.raw = load_rules().model_dump(mode="json")
        self.atoms = [
            {"id": "A1", "tag": "danger_action", "referent_key": "EVT_A", "modality": "visual",
             "start_ms": 100, "end_ms": 900, "source_refs": ["src:1"], "time_confidence": "HIGH"},
            {"id": "P1", "tag": "encouragement", "referent_key": "EVT_B", "modality": "speech",
             "start_ms": 100, "end_ms": 900, "source_refs": ["src:2"], "time_confidence": "HIGH"},
        ]
        self.decisions = [{"action_id": "A1", "stance_id": "P1", "stance": "encourages_same",
                           "valid": True}]

    def _run(self, raw, atoms=None, decisions=None):
        ruleset = RuleSet.model_validate(raw)
        return decide(atoms or self.atoms, 30_000, "FULL", 15_000,
                      self.decisions if decisions is None else decisions,
                      require_relation=True, counterfactual_limit=0, ruleset=ruleset)

    def test_conflict_edge_survives_any_argument_priority_order(self):
        """Generating the conflict argument first must not delete its attack edge.

        The edge used to be added only when its target already existed, so raising
        A_REFERENT_CONFLICT above A_MODEL_PROMOTION silently produced FLAG instead of
        CONFLICTED — the model's wrong answer would have won.
        """
        default_finding, default_graph = self._run(json.loads(json.dumps(self.raw)))

        boosted = json.loads(json.dumps(self.raw))
        conflict = next(r for r in boosted["argument_rules"] if r["id"] == "A_REFERENT_CONFLICT")
        promotion = next(r for r in boosted["argument_rules"] if r["id"] == "A_MODEL_PROMOTION")
        conflict["priority"] = promotion["priority"] + 1
        boosted_finding, boosted_graph = self._run(boosted)

        def edges(graph):
            return {(edge["source"].split(":")[0], edge["target"].split(":")[0])
                    for edge in graph["attacks"]}

        self.assertEqual((default_finding["judgement"], default_finding["disposition"]),
                         ("CONFLICTED", "REVIEW"))
        self.assertIn(("REFERENT_CONFLICT", "MODEL_PROMOTION"), edges(default_graph))
        self.assertEqual(edges(default_graph), edges(boosted_graph))
        self.assertEqual(boosted_finding["reason_code"], default_finding["reason_code"])

    def test_an_unanswered_stance_does_not_cancel_a_verified_one(self):
        """Verified support survives; the open doubt is reported as REVIEW instead."""
        action = {"id": "A1", "tag": "danger_action", "referent_key": "EVT_A",
                  "modality": "visual", "start_ms": 100, "end_ms": 900,
                  "source_refs": ["src:a"], "time_confidence": "HIGH"}
        stances = [{"id": f"P{i}", "tag": "encouragement", "referent_key": "EVT_A",
                    "modality": "speech", "start_ms": 100, "end_ms": 900,
                    "source_refs": [f"src:p{i}"], "time_confidence": "HIGH"}
                   for i in range(1, 5)]
        answered = [{"action_id": "A1", "stance_id": f"P{i}", "stance": "encourages_same",
                     "valid": True} for i in range(1, 4)]

        finding, graph = self._run(json.loads(json.dumps(self.raw)),
                                   atoms=[action] + stances, decisions=answered)

        for i in range(1, 4):
            self.assertTrue(
                any(a["kind"] == "LOCAL_PROMOTION" and f"P{i}" in a["id"] and a["label"] == "IN"
                    for a in graph["arguments"]),
                f"P{i} 的已核验支持被未核验话语击倒")
            self.assertIn(f"P{i}", finding["supporting_ids"])
        self.assertEqual((finding["judgement"], finding["disposition"]),
                         ("INSUFFICIENT", "REVIEW"))
        self.assertEqual(finding["reason_code"], "MISSING_SEMANTIC_RELATION")

    def test_an_unrelated_counter_answer_cannot_lift_the_review_gate(self):
        """Adding a third, unrelated answer must not upgrade REVIEW to FLAG.

        D_UNCERTAIN_SUPPORT used to be disabled by has_counter, which only means a
        counter node exists — not that the solver accepted it. An extra irrelevant
        answer therefore removed the manual-review gate.
        """
        from tests.test_pead_self_review import base, evidence, relation

        unanswered = [evidence("P2", "encouragement")]
        three = base() + unanswered + [evidence("P3", "encouragement")]
        two = base() + unanswered
        decisions = [relation("A", "P"),
                     {"action_id": "A", "stance_id": "P3", "stance": "unrelated", "valid": True}]

        with_three, _ = decide(three, 25_000, "FULL", 15_000, decisions, require_relation=True)
        with_two, _ = decide(two, 25_000, "FULL", 15_000, [relation("A", "P")],
                             require_relation=True)

        self.assertEqual((with_two["judgement"], with_two["disposition"]),
                         ("INSUFFICIENT", "REVIEW"))
        self.assertEqual((with_three["judgement"], with_three["disposition"]),
                         ("INSUFFICIENT", "REVIEW"),
                         "加入一条无关的反向回答后结论被升级为强提示")
        self.assertEqual(with_three["reason_code"], "MISSING_SEMANTIC_RELATION")

    def test_an_accepted_counter_still_yields_a_conflict(self):
        """The gate above must not swallow genuine counter evidence."""
        from tests.test_pead_self_review import base, evidence, relation

        atoms = base() + [evidence("P2", "encouragement"), evidence("W", "warning")]
        decisions = [relation("A", "P"), relation("A", "W", "warns_same")]
        finding, _ = decide(atoms, 25_000, "FULL", 15_000, decisions, require_relation=True)
        self.assertIn(finding["disposition"], {"REVIEW", "FLAG"})
        self.assertNotEqual(finding["reason_code"], "MISSING_SEMANTIC_RELATION")


if __name__ == '__main__':unittest.main()
