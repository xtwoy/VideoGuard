"""PEAD deterministic reference rules; relation checks are optional external input."""
from __future__ import annotations
from typing import Any
import json
from pathlib import Path

from src import config as params

MODALITIES = {"visual","speech","screen_text","sound","metadata"}
TAGS = {"danger_action","danger_description","encouragement","challenge","warning",
        "violence","news_context","fiction_context","pii_candidate","credential_claim",
        "marketing_claim","absolute_claim","self_harm_action","self_harm_instruction",
        "sexual_content","sexual_minor_risk","hate_or_harassment","fraud_or_scam",
        "financial_inducement","controlled_goods","controlled_goods_promotion","minor_risk",
        "education_context","other"}
REQUIRED_COVERAGES = {"FULL","PARTIAL","UNKNOWN","REFUSED","ERROR"}

def load_policies()->dict:
    f=Path(__file__).resolve().parents[1]/"config/policies_v03.json"
    return json.loads(f.read_text(encoding="utf-8"))

def relation_gap_ms()->int:
    """Relation time window, taken from the single shared parameter module.

    Delegating here (instead of keeping a local constant) is what stops the
    selection window and the judgement window from drifting apart.
    """
    return params.relation_gap_ms()

def _f(policy_id: str, judgement: str, disposition: str,
       reason_code: str, supporting=(), counter=()) -> dict:
    return dict(policy_id=policy_id, judgement=judgement, disposition=disposition,
                reason_code=reason_code, supporting_ids=list(supporting),
                counter_ids=list(counter))

def _valid_obs(e: dict, duration_ms: int) -> bool:
    if not isinstance(e,dict) or not isinstance(e.get("id"),str) or not e["id"]:
        return False
    if e.get("modality") not in MODALITIES or e.get("tag") not in TAGS:
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
    return bool(a.get("referent_key")) and a.get("referent_key")==b.get("referent_key")

def assess(data: dict, duration_ms: int, policy_config: dict | None=None)->dict:
    """Evaluate all policies, *not only* model-reported candidate risks.
    Input keys: coverage and observations. Never asserts illegality.
    """
    if type(duration_ms) is not int or duration_ms<0:
        raise ValueError("duration_ms must be a non-negative integer")
    policy_source=policy_config if policy_config is not None else load_policies()
    policies=policy_source["policies"]
    policy_ids=tuple(policies)
    # Fails loudly when the policy file and the effective code/env value disagree,
    # instead of silently selecting pairs by one window and judging by another.
    gap_ms=params.assert_policy_gap_agrees(policies)
    coverage=data.get("coverage","UNKNOWN")
    if coverage not in REQUIRED_COVERAGES: coverage="UNKNOWN"
    observations=data.get("observations",[])
    if not isinstance(observations,list): observations=[]
    seen=set(); good=[]; invalid=[]; invalid_tags=set()
    for obj in observations:
        oid=obj.get("id") if isinstance(obj,dict) else None
        if oid in seen or not _valid_obs(obj,duration_ms):
            invalid.append(oid if isinstance(oid,str) else "(no id)")
            if isinstance(obj,dict) and isinstance(obj.get("tag"),str):
                invalid_tags.add(obj["tag"])
        else:
            seen.add(oid); good.append(obj)
    findings=[]
    if coverage in {"ERROR","REFUSED"}:
        return {"coverage":coverage,"invalid_evidence_ids":invalid,
                "findings":[_f(p,"UNKNOWN","RETRY","MODEL_UNAVAILABLE") for p in policy_ids]}
    tags=lambda *wanted:[e for e in good if e["tag"] in wanted and _located(e)]
    all_with_tag=lambda *wanted:[e for e in good if e["tag"] in wanted]
    for p in policy_ids:
        if p=="R_DANGER_PROMOTION":
            actions=tags(*policies[p]["action_tags"])
            promos=tags(*policies[p]["promotion_tags"])
            # Counter-context evidence is anything that marks the same material as
            # cautionary rather than promotional: an explicit warning, or an
            # education/news/fiction framing. Keeping the wider list in config
            # means the verdict no longer depends on whether the parse happened to
            # label "请勿模仿" as `warning` or as `education_context`.
            counter_tags=policies[p].get("counter_context_tags") or policies[p]["warning_tags"]
            counters=tags(*counter_tags)
            matches=[(a,b) for a in actions for b in promos if _same_referent(a,b) and _near(a,b,gap_ms)]
            related_counter=[w for a,b in matches for w in counters if
                             (_same_referent(w,a) or _same_referent(w,b)) and _near(w,a,gap_ms)]
            if matches and related_counter:
                ids=sorted({x["id"] for pair in matches for x in pair})
                findings.append(_f(p,"CONFLICTED","REVIEW","CONFLICTING_STANCE",
                                   ids,sorted({x["id"] for x in related_counter})))
            elif matches:
                ids=sorted({x["id"] for pair in matches for x in pair})
                findings.append(_f(p,"SUPPORTED","FLAG","RELATED_ACTION_AND_PROMOTION",ids))
            elif (actions and promos and not matches) or (
                invalid_tags & set(policies[p]["action_tags"]+
                                   policies[p]["promotion_tags"]+
                                   list(counter_tags))):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","MISSING_SEMANTIC_RELATION"))
            elif coverage!="FULL":
                findings.append(_f(p,"UNKNOWN","RECHECK","INCOMPLETE_OBSERVATION"))
            elif actions and any(not _located(e) for e in all_with_tag("encouragement","challenge")):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","UNLOCATED_PROMOTION"))
            else:
                findings.append(_f(p,"NOT_SUPPORTED","NONE","NO_SUPPORTING_RELATION"))
        elif p=="R_VIOLENCE":
            acts=[e for e in tags(*policies[p]["action_tags"]) if e["modality"]=="visual"]
            if acts:
                contexts=[e for e in tags(*policies[p]["context_tags"]) if
                          any(_same_referent(e,a) and _near(e,a,gap_ms) for a in acts)]
                if contexts:
                    findings.append(_f(p,"SUPPORTED","REVIEW","DEPICTION_WITH_CONTEXT",
                                      [x["id"] for x in acts],[x["id"] for x in contexts]))
                else:
                    findings.append(_f(p,"SUPPORTED","FLAG","VIOLENCE_DEPICTION",
                                      [x["id"] for x in acts]))
            elif all_with_tag("violence") or (
                invalid_tags & set(policies[p]["action_tags"])):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","UNVERIFIED_OR_UNLOCATED"))
            elif coverage!="FULL":
                findings.append(_f(p,"UNKNOWN","RECHECK","INCOMPLETE_OBSERVATION"))
            else:
                findings.append(_f(p,"NOT_SUPPORTED","NONE","NO_OBSERVED_VIOLENCE"))
        elif p=="R_PRIVACY_EXPOSURE":
            pii=[e for e in tags(*policies[p]["action_tags"]) if e["modality"] in {"visual","screen_text","speech"}]
            if pii:
                findings.append(_f(p,"SUPPORTED","FLAG","POTENTIAL_PII",[x["id"] for x in pii]))
            elif all_with_tag("pii_candidate") or (
                invalid_tags & set(policies[p]["action_tags"])):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","UNLOCATED_PII"))
            elif coverage!="FULL":
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
            elif coverage!="FULL":
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
            elif coverage!="FULL":
                findings.append(_f(p,"UNKNOWN","RECHECK","INCOMPLETE_OBSERVATION"))
            else:
                findings.append(_f(p,"NOT_SUPPORTED","NONE","NO_RELEVANT_CUE"))
    return {"coverage":coverage,"invalid_evidence_ids":invalid,"findings":findings,"event_findings":build_event_findings(good, findings, duration_ms)}

def build_event_findings(observations: list[dict], findings: list[dict],
                         duration_ms: int) -> list[dict]:
    """Create event-level audit records.

    The video-level finding remains for backward compatibility.  Event records
    prevent one conflicting scene from hiding another independent scene.
    This function only groups model observations; it does not invent evidence.
    """
    valid=[x for x in observations if isinstance(x,dict) and isinstance(x.get("id"),str)]
    events=[]
    def event_key(obs):
        return obs.get("referent_key") or f"timeline:{obs.get('start_ms')}:{obs.get('end_ms')}"

    groups={}
    for obs in valid:
        groups.setdefault(event_key(obs),[]).append(obs)

    for key, group in groups.items():
        ids=[x["id"] for x in group]
        related=[f for f in findings
                 if any(i in f.get("supporting_ids",[])+f.get("counter_ids",[])
                        for i in ids)]
        if related:
            # Keep every local judgement. Do not collapse different events.
            for f in related:
                events.append({
                    "event_id": f"{f['policy_id']}:{key}",
                    "policy_id": f["policy_id"],
                    "evidence_ids": ids,
                    "judgement": f["judgement"],
                    "disposition": f["disposition"],
                    "reason_code": f["reason_code"],
                    "audit": {
                        "evidence_checked": len(ids),
                        "duration_ms": duration_ms,
                        "scope": "event"
                    }
                })
    return events
