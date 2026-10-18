"""PEAD deterministic reference rules; relation checks are optional external input."""
from __future__ import annotations
from typing import Any
import json
from pathlib import Path

from src import config as params
from src import policy_config as policy_spec
from src.evidence_graph import decide as graph_decide
from src.pead_rules import RuleSet, load_rules

MODALITIES = {"visual","speech","screen_text","sound","metadata"}
TAGS = {"danger_action","danger_description","encouragement","challenge","warning",
        "violence","news_context","fiction_context","pii_candidate","credential_claim",
        "marketing_claim","absolute_claim","self_harm_action","self_harm_instruction",
        "sexual_content","sexual_minor_risk","hate_or_harassment","fraud_or_scam",
        "financial_inducement","controlled_goods","controlled_goods_promotion","minor_risk",
        "education_context","other"}
REQUIRED_COVERAGES = {"FULL","PARTIAL","UNKNOWN","REFUSED","ERROR"}

def load_policies()->dict:
    """Load and validate the ten-policy configuration.

    Validation is not cosmetic: without it, emptying one policy's ``action_tags``
    silently turns a found risk into "nothing to do", which is the same bypass the
    PEAD rule set already refuses.
    """
    f=Path(__file__).resolve().parents[1]/"config/policies_v03.json"
    document=json.loads(f.read_text(encoding="utf-8"))
    policies=policy_spec.validate_policies(document)
    return {**document, "policies": policies}

def relation_gap_ms()->int:
    """Relation time window, taken from the single shared parameter module.

    Delegating here (instead of keeping a local constant) is what stops the
    selection window and the judgement window from drifting apart.
    """
    return params.relation_gap_ms()

def _f(policy_id: str, judgement: str, disposition: str,
       reason_code: str, supporting=(), counter=(), *,
       counter_checked: bool = False, counter_source: str = "NOT_APPLICABLE",
       relation_checked: bool = False, evidence_confidence: str | None = None,
       needs_human_review: bool | None = None) -> dict:
    """Build one finding, including the provenance of its counter evidence.

    ``counter_ids`` being empty is ambiguous on its own: it can mean "the counter
    evidence was looked for and none exists" or "this rule never looks for counter
    evidence". ``counter_checked`` records which, so a reader — or an auditor —
    can tell an examined absence from an unexamined one.
    """
    return dict(policy_id=policy_id, judgement=judgement, disposition=disposition,
                reason_code=reason_code, supporting_ids=list(supporting),
                counter_ids=list(counter),
                # Risk severity and evidence certainty are different axes: a policy may
                # still say FLAG while recording that the cue itself needs checking.
                evidence_confidence=evidence_confidence,
                needs_human_review=needs_human_review,
                counter_evidence=dict(checked=counter_checked,
                                      source=counter_source,
                                      found=bool(counter),
                                      relation_checked=relation_checked))

def _valid_obs(e: dict, duration_ms: int) -> bool:
    if not isinstance(e,dict) or not isinstance(e.get("id"),str) or not e["id"]:
        return False
    if (not isinstance(e.get("modality"), str) or e["modality"] not in MODALITIES
            or not isinstance(e.get("tag"), str) or e["tag"] not in TAGS
            or (e.get("referent_key") is not None and not isinstance(e["referent_key"], str))
            or (e.get("event_id") is not None and not isinstance(e["event_id"], str))
            or (e.get("time_confidence") is not None and e["time_confidence"] not in ("HIGH", "MEDIUM", "LOW", "UNAVAILABLE"))):
        return False
    a,b=e.get("start_ms"),e.get("end_ms")
    if a is None and b is None:  # admissible but unlocated; not enough for STRONG support
        return True
    return (type(a) is int and type(b) is int and 0<=a<b<=duration_ms)

def _located(e: dict)->bool:
    return type(e.get("start_ms")) is int and type(e.get("end_ms")) is int

def _near(a: dict,b: dict,max_gap_ms: int)->bool:
    if not (_located(a) and _located(b)):
        return False
    return max(0,a["start_ms"]-b["end_ms"],b["start_ms"]-a["end_ms"]) <= max_gap_ms

def _same_referent(a: dict,b: dict)->bool:
    if a.get("event_id") or b.get("event_id"):
        return bool(a.get("event_id") and b.get("event_id") and a["event_id"] == b["event_id"])
    return bool(a.get("referent_key")) and a.get("referent_key")==b.get("referent_key")

def assess(data: dict, duration_ms: int, policy_config: dict | None=None, *, ruleset: RuleSet | None=None)->dict:
    """Evaluate all policies, *not only* model-reported candidate risks.
    Input keys: coverage and observations. Never asserts illegality.
    """
    if type(duration_ms) is not int or duration_ms<0:
        raise ValueError("duration_ms must be a non-negative integer")
    ruleset = ruleset if ruleset is not None else load_rules()
    policy_source=policy_config if policy_config is not None else load_policies()
    policies=policy_source["policies"]
    policy_ids=tuple(policies)
    # Fails loudly when the policy file and the effective code/env value disagree,
    # instead of silently selecting pairs by one window and judging by another.
    gap_ms=params.assert_policy_gap_agrees(policies)
    coverage=data.get("coverage","UNKNOWN")
    if not isinstance(coverage,str) or coverage not in REQUIRED_COVERAGES: coverage="UNKNOWN"
    observations=data.get("observations",[])
    if not isinstance(observations,list): observations=[]
    seen=set(); good=[]; invalid=[]; invalid_tags=set()
    for obj in observations:
        oid=obj.get("id") if isinstance(obj,dict) else None
        if not _valid_obs(obj,duration_ms) or oid in seen:
            invalid.append(oid if isinstance(oid,str) else "(no id)")
            if isinstance(obj,dict) and isinstance(obj.get("tag"),str):
                invalid_tags.add(obj["tag"])
        else:
            seen.add(oid); good.append(obj)
    findings=[]
    pead_audit=None
    if coverage in {"ERROR","REFUSED"}:
        return {"coverage":coverage,"invalid_evidence_ids":invalid,
                "findings":[_f(p,"UNKNOWN","RETRY","MODEL_UNAVAILABLE") for p in policy_ids]}
    tags=lambda *wanted:[e for e in good if e["tag"] in wanted and _located(e)]
    all_with_tag=lambda *wanted:[e for e in good if e["tag"] in wanted]
    # Video-level coverage says the timeline was complete, not that every modality was
    # readable. When a policy's needed modality was not actually observed, "no cue"
    # means "could not check", not "nothing found".
    modalities_raw=data.get("modalities")
    modalities=({key:(value if value in policy_spec.MODALITY_STATES else "UNKNOWN")
                 for key, value in modalities_raw.items()}
                if isinstance(modalities_raw,dict) else None)
    def modality_gap(policy_id: str) -> bool:
        if modalities is None:
            return False
        return any(modalities.get(name)!="FULL"
                   for name in policy_spec.required_modalities(policy_id))
    for p in policy_ids:
        if p=="R_DANGER_PROMOTION":
            finding, pead_audit = graph_decide(observations, duration_ms, coverage, gap_ms,
                                                require_relation=False, ruleset=ruleset)
            findings.append(finding)
        elif p=="R_VIOLENCE":
            acts=[e for e in tags(*policies[p]["action_tags"]) if e["modality"]=="visual"]
            if acts:
                contexts=[e for e in tags(*policies[p]["context_tags"]) if
                          any(_same_referent(e,a) and _near(e,a,gap_ms) for a in acts)]
                if contexts:
                    findings.append(_f(p,"SUPPORTED","REVIEW","DEPICTION_WITH_CONTEXT",
                                      [x["id"] for x in acts],[x["id"] for x in contexts],
                                      counter_checked=True, counter_source="CONTEXT_TAGS"))
                else:
                    findings.append(_f(p,"SUPPORTED","FLAG","VIOLENCE_DEPICTION",
                                      [x["id"] for x in acts],
                                      counter_checked=True, counter_source="CONTEXT_TAGS"))
            elif all_with_tag("violence") or (
                invalid_tags & set(policies[p]["action_tags"])):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","UNVERIFIED_OR_UNLOCATED",
                                   counter_checked=True, counter_source="CONTEXT_TAGS"))
            elif coverage!="FULL" or modality_gap(p):
                findings.append(_f(p,"UNKNOWN","RECHECK","INCOMPLETE_OBSERVATION",
                                   counter_checked=True, counter_source="CONTEXT_TAGS"))
            else:
                findings.append(_f(p,"NOT_SUPPORTED","NONE","NO_OBSERVED_VIOLENCE",
                                   counter_checked=True, counter_source="CONTEXT_TAGS"))
        elif p=="R_PRIVACY_EXPOSURE":
            pii=[e for e in tags(*policies[p]["action_tags"]) if e["modality"] in {"visual","screen_text","speech"}]
            if pii:
                findings.append(_f(p,"SUPPORTED","FLAG","POTENTIAL_PII",[x["id"] for x in pii]))
            elif all_with_tag("pii_candidate") or (
                invalid_tags & set(policies[p]["action_tags"])):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","UNLOCATED_PII"))
            elif coverage!="FULL" or modality_gap(p):
                findings.append(_f(p,"UNKNOWN","RECHECK","INCOMPLETE_OBSERVATION"))
            else:
                findings.append(_f(p,"NOT_SUPPORTED","NONE","NO_OBSERVED_PII"))
        elif p=="R_MARKETING_CLAIM":
            configured_tags=policies[p]["action_tags"]
            credentials=tags("credential_claim")
            marketing=tags(*[tag for tag in configured_tags if tag!="credential_claim"])
            if credentials:
                findings.append(_f(p,"SUPPORTED","VERIFY_EXTERNAL","CREDENTIAL_AUTHENTICITY_UNKNOWN",
                                   [x["id"] for x in credentials+marketing]))
            elif marketing:
                findings.append(_f(p,"SUPPORTED","REVIEW","MARKETING_CLAIM_NEEDS_CONTEXT",
                                   [x["id"] for x in marketing]))
            elif all_with_tag("credential_claim","marketing_claim","absolute_claim") or (
                invalid_tags & set(policies[p]["action_tags"])):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","UNLOCATED_MARKETING_CLAIM"))
            elif coverage!="FULL" or modality_gap(p):
                findings.append(_f(p,"UNKNOWN","RECHECK","INCOMPLETE_OBSERVATION"))
            else:
                findings.append(_f(p,"NOT_SUPPORTED","NONE","NO_OBSERVED_CLAIM"))
        else:
            # Configuration-driven direct-cue policies make it possible to add
            # new review points without changing the main audit orchestration.
            configured_tags=policies[p].get("action_tags",[])
            cues=tags(*configured_tags)
            unlocated_cues=all_with_tag(*configured_tags)
            if cues:
                findings.append(_f(
                    p,"SUPPORTED",policies[p].get("disposition","REVIEW"),
                    policies[p].get("reason_code","CONTENT_SAFETY_CUE"),
                    [x["id"] for x in cues]))
            elif unlocated_cues or (invalid_tags & set(configured_tags)):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","UNVERIFIED_OR_UNLOCATED"))
            elif coverage!="FULL" or modality_gap(p):
                findings.append(_f(p,"UNKNOWN","RECHECK","INCOMPLETE_OBSERVATION"))
            else:
                findings.append(_f(p,"NOT_SUPPORTED","NONE","NO_RELEVANT_CUE"))
    # Evidence certainty is a property of the cues a finding rests on, so it is
    # derived once for every policy instead of being passed by some branches only.
    # A grounded "IN" says the argument survived, not that the upstream cue was sure.
    #
    # Both directions count: a low-confidence counter (for example an unclear news
    # context) can be exactly what turned FLAG into REVIEW, so reporting HIGH would
    # describe the finding as better-supported than it is.
    by_id={e["id"]:e for e in good}
    for finding in findings:
        ids={i for i in finding.get("supporting_ids",[]) + finding.get("counter_ids",[]) if i in by_id}
        uncertain=any(bool(by_id[i].get("needs_human_review")) for i in ids)
        if finding.get("evidence_confidence") is None:
            finding["evidence_confidence"]="LOW" if uncertain else "HIGH"
        if finding.get("needs_human_review") is None:
            finding["needs_human_review"]=uncertain
    return {"coverage":coverage,"invalid_evidence_ids":invalid,"findings":findings,"event_findings":build_event_findings(good, findings, duration_ms), "pead_audit":pead_audit}

def build_event_findings(observations: list[dict], findings: list[dict],
                         duration_ms: int) -> list[dict]:
    """Create event-level audit records.

    Graph policies supply independently evaluated event decisions. Other
    policies retain traceable grouping of their supporting observations.
    This function only groups model observations; it does not invent evidence.
    """
    valid=[x for x in observations if isinstance(x,dict) and isinstance(x.get("id"),str)]
    events=[]
    for finding in findings:
        for decision in finding.get("event_decisions", []):
            events.append({
                "event_id": f"{finding['policy_id']}:{decision['event_key']}",
                "policy_id": finding["policy_id"],
                "evidence_ids": decision["evidence_ids"],
                "judgement": decision["judgement"],
                "disposition": decision["disposition"],
                "reason_code": decision["reason_code"],
                "audit": {"evidence_checked": len(decision["evidence_ids"]),
                          "duration_ms": duration_ms, "scope": "event",
                          "argument_summary": {label: len(decision["argument_labels"][label])
                                               for label in ("accepted", "rejected", "undecided")}},
            })
    def event_key(obs):
        # Same precedence as `_same_referent`: the event instance wins over the
        # semantic referent. Preferring referent_key here would merge two distinct
        # events that happen to point at the same entity.
        if obs.get("event_id"):
            return obs["event_id"]
        return obs.get("referent_key") or f"timeline:{obs.get('start_ms')}:{obs.get('end_ms')}"

    groups={}
    for obs in valid:
        groups.setdefault(event_key(obs),[]).append(obs)

    for key, group in groups.items():
        ids=[x["id"] for x in group]
        related=[f for f in findings
                 if "event_decisions" not in f and any(i in f.get("supporting_ids",[])+f.get("counter_ids",[])
                        for i in ids)]
        if related:
            # Keep every local judgement. Do not collapse different events.
            for f in related:
                direct=[i for i in ids
                        if i in f.get("supporting_ids",[]) or i in f.get("counter_ids",[])]
                # Another policy's cue in the same event is background for this
                # finding, not its evidence. Mixing them inflates the proof shown
                # for a single judgement.
                context=[i for i in ids if i not in direct]
                events.append({
                    "event_id": f"{f['policy_id']}:{key}",
                    "policy_id": f["policy_id"],
                    "evidence_ids": direct,
                    "context_evidence_ids": context,
                    "judgement": f["judgement"],
                    "disposition": f["disposition"],
                    "reason_code": f["reason_code"],
                    "audit": {
                        "evidence_checked": len(direct),
                        "duration_ms": duration_ms,
                        "scope": "event"
                    }
                })
    return events
