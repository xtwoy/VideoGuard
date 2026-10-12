"""Integrate external Jev opinions with deterministic PEAD rules.

The model may *help classify a semantic relationship*. It never creates evidence,
changes timestamps, asserts wrongdoing, or overrides a hard PEAD constraint.
"""
from __future__ import annotations
import copy
from src.pead_engine import assess
from src.jev_model_client import (
    select_pairs, build_request, validate_response, semantic_gate
)

POLICY = "R_DANGER_PROMOTION"

def assess_joint(omni_result: dict, duration_ms: int,
                 jev_response: dict | None = None,
                 jev_failed: bool = False) -> dict:
    """Offline-testable fusion; caller owns the external Jev request."""
    baseline = assess(omni_result, duration_ms)
    merged = copy.deepcopy(baseline)
    findings_by_policy = {f["policy_id"]: f for f in merged["findings"]}
    finding = findings_by_policy[POLICY]

    selected_pairs = select_pairs(omni_result.get("observations", []), duration_ms)
    if not selected_pairs:
        return {
            "baseline": baseline, "merged": merged, "pairs": [],
            "jev_payload": None, "jev_decisions": [],
            "semantic_check": "NOT_NEEDED_OR_UNLOCATED",
        }

    request = build_request(selected_pairs)
    if jev_response is None:
        # Fail safe when the Jev service is unavailable: do not turn a missed
        # semantic check into "no risk"; flagged cases go to manual review.
        if finding["disposition"] == "FLAG":
            finding["disposition"] = "REVIEW"
            finding["reason_code"] = "JEV_UNAVAILABLE_SEMANTIC_REVIEW"
        return {
            "baseline": baseline, "merged": merged, "pairs": selected_pairs,
            "jev_payload": request, "jev_decisions": [],
            "semantic_check": "API_FAILED" if jev_failed else "PENDING_CALL",
        }

    decisions=validate_response(request, jev_response)
    # Aggregate all pairs before changing the finding: a relation about an
    # unrelated second narration must not override a well-supported first pair.
    original_supported=set(finding["supporting_ids"])
    positives=[]
    referent_disagreements=[]
    reviewed_base_pairs=[]
    ambiguous_pairs=[]
    for pair, dec in zip(selected_pairs, decisions):
        stance=semantic_gate(dec)
        ids={pair["action_id"],pair["stance_id"]}
        if stance=="encourages_same":
            if pair["referents_conflict"]:
                referent_disagreements.append(pair)
            else:
                positives.append(pair)
        elif stance in {"unrelated","warns_same","insufficient","REVIEW"}:
            if ids.issubset(original_supported):
                reviewed_base_pairs.append(pair)
            if stance in {"insufficient","REVIEW"}:
                ambiguous_pairs.append(pair)

    if finding["judgement"] in {"UNKNOWN", "CONFLICTED"}:
        # Hard PEAD uncertainty dominates third-party model answers.
        pass
    elif referent_disagreements and not positives:
        finding["judgement"]="CONFLICTED"
        finding["disposition"]="REVIEW"
        finding["reason_code"]="OMNI_JEV_REFERENT_DISAGREEMENT"
        finding["supporting_ids"]=sorted(set(finding["supporting_ids"]+
            [x for p in referent_disagreements for x in (p["action_id"],p["stance_id"])]))
    elif reviewed_base_pairs:
        finding["judgement"]="CONFLICTED"
        finding["disposition"]="REVIEW"
        finding["reason_code"]="JEV_DISPUTES_BASELINE_SUPPORT"
        finding["counter_ids"]=sorted(set(finding["counter_ids"]+
            [p["stance_id"] for p in reviewed_base_pairs]))
    elif positives:
        finding["judgement"]="SUPPORTED"
        finding["disposition"]="FLAG"
        finding["reason_code"]="JEV_SEMANTIC_LINK_ASSISTED"
        finding["supporting_ids"]=sorted(set(finding["supporting_ids"]+
            [x for p in positives for x in (p["action_id"],p["stance_id"])]))
    elif finding["disposition"]=="FLAG":
        # Jev did not confirm the only baseline semantic relationship.
        finding["judgement"]="INSUFFICIENT"
        finding["disposition"]="REVIEW"
        finding["reason_code"]="JEV_NO_CONFIRMED_SEMANTIC_LINK"
    elif ambiguous_pairs and finding["judgement"]=="NOT_SUPPORTED":
        finding["judgement"]="INSUFFICIENT"
        finding["disposition"]="REVIEW"
        finding["reason_code"]="JEV_SEMANTIC_AMBIGUITY"
    return {
        "baseline": baseline, "merged": merged, "pairs": selected_pairs,
        "jev_payload": request, "jev_decisions": decisions,
        "semantic_check": "COMPLETE",
    }
