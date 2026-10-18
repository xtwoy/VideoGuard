"""Resolve provider relation arguments in the event-scoped PEAD evidence graph."""
from __future__ import annotations
import copy

from src import config
from src.pead_rules import RuleSet, load_rules
from src.evidence_graph import decide
from src.pead_engine import assess, build_event_findings
from src.relation_client import select_pairs_with_coverage, build_request, validate_response, semantic_gate

POLICY = "R_DANGER_PROMOTION"


def assess_joint(observation_result: dict, duration_ms: int,
                 relation_response: dict | None = None,
                 relation_failed: bool = False, *, ruleset: RuleSet | None = None) -> dict:
    ruleset = ruleset if ruleset is not None else load_rules()
    baseline = assess(observation_result, duration_ms, ruleset=ruleset)
    merged = copy.deepcopy(baseline)
    pairs, pair_coverage = select_pairs_with_coverage(observation_result.get("observations", []),
                                                      duration_ms)
    request = build_request(pairs) if pairs else None
    decisions = validate_response(request, relation_response) if request and relation_response is not None else []
    graph_decisions = [
        {"action_id": pair["action_id"], "stance_id": pair["stance_id"], "stance": semantic_gate(decision),
         "valid": decision["status"] == "VALID"}
        for pair, decision in zip(pairs, decisions)
    ]
    finding, graph = decide(observation_result.get("observations", []), duration_ms,
                            observation_result.get("coverage", "UNKNOWN"), config.relation_gap_ms(),
                            graph_decisions, require_relation=True, ruleset=ruleset)
    merged["findings"] = [finding if f["policy_id"] == POLICY else f for f in merged["findings"]]
    merged["pead_audit"] = graph
    merged["event_findings"] = build_event_findings(observation_result.get("observations", []),
                                                   merged["findings"], duration_ms)
    if not pairs:
        semantic_check = "NOT_NEEDED_OR_UNLOCATED"
    elif relation_response is None:
        semantic_check = "API_FAILED" if relation_failed else "PENDING_CALL"
    elif any(decision["status"] != "VALID" for decision in decisions):
        semantic_check = "API_FAILED"
    elif pair_coverage["omitted"] > 0:
        # Every asked pair answered, but qualifying pairs were left unasked because the
        # call is capped. That is not "all candidate relations verified".
        semantic_check = "PARTIAL_CANDIDATES"
    else:
        semantic_check = "COMPLETE"
    return {"baseline": baseline, "merged": merged, "pairs": pairs,
            "relation_payload": request, "relation_decisions": decisions,
            "pair_coverage": pair_coverage,
            "semantic_check": semantic_check}
