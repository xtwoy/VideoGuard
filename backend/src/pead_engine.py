"""PEAD deterministic reference rules. Jev is a SEPARATE third-party decision AI."""
from __future__ import annotations
from typing import Any
import json
from pathlib import Path

MODALITIES = {"visual","speech","screen_text","sound","metadata"}
TAGS = {"danger_action","danger_description","encouragement","challenge","warning",
        "violence","news_context","fiction_context","pii_candidate","credential_claim",
        "marketing_claim","absolute_claim","self_harm_action","self_harm_instruction",
        "sexual_content","sexual_minor_risk","hate_or_harassment","fraud_or_scam",
        "financial_inducement","controlled_goods","controlled_goods_promotion","minor_risk",
        "education_context","other"}
REQUIRED_COVERAGES = {"FULL","PARTIAL","UNKNOWN","REFUSED","ERROR"}
MAX_RELATION_GAP_MS = 15000

def load_policies()->dict:
    f=Path(__file__).resolve().parents[1]/"config/policies_v03.json"
    return json.loads(f.read_text(encoding="utf-8"))

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
    Input keys: coverage, observations, candidate_risks. Never asserts illegality.
    """
    if type(duration_ms) is not int or duration_ms<0:
        raise ValueError("duration_ms must be a non-negative integer")
    config=policy_config if policy_config is not None else load_policies()
    policies=config["policies"]
    policy_ids=tuple(policies)
    gap_ms=policies["R_DANGER_PROMOTION"]["max_relation_gap_ms"]
    if type(gap_ms) is not int or gap_ms < 0:
        raise ValueError("max_relation_gap_ms must be nonnegative integer")
    coverage=data.get("coverage","UNKNOWN")
    if coverage not in REQUIRED_COVERAGES: coverage="UNKNOWN"
    observations=data.get("observations",[])
    if not isinstance(observations,list): observations=[]
    candidates=data.get("candidate_risks",[])
    if not isinstance(candidates,list): candidates=[]
    seen=set(); good=[]; invalid=[]; invalid_tags=set()
    for obj in observations:
        oid=obj.get("id") if isinstance(obj,dict) else None
        if oid in seen or not _valid_obs(obj,duration_ms):
            invalid.append(oid if isinstance(oid,str) else "(no id)")
            if isinstance(obj,dict) and isinstance(obj.get("tag"),str):
                invalid_tags.add(obj["tag"])
        else:
            seen.add(oid); good.append(obj)
    candidate_ids={x.get("policy_id") for x in candidates if isinstance(x,dict)}
    suspicious_ref_ids={
        x.get("policy_id") for x in candidates if isinstance(x,dict)
        and any(k not in seen for k in x.get("supporting_evidence_ids",[]) if isinstance(k,str))
    }
    findings=[]
    if coverage in {"ERROR","REFUSED"}:
        return {"coverage":coverage,"invalid_evidence_ids":invalid,
                "findings":[_f(p,"UNKNOWN","RETRY","MODEL_UNAVAILABLE") for p in policy_ids]}
    tags=lambda *wanted:[e for e in good if e["tag"] in wanted and _located(e)]
    all_with_tag=lambda *wanted:[e for e in good if e["tag"] in wanted]
    for p in policy_ids:
        hints=p in candidate_ids
        bad_refs=p in suspicious_ref_ids
        if p=="R_DANGER_PROMOTION":
            actions=tags(*policies[p]["action_tags"])
            promos=tags(*policies[p]["promotion_tags"])
            warnings=tags(*policies[p]["warning_tags"])
            matches=[(a,b) for a in actions for b in promos if _same_referent(a,b) and _near(a,b,gap_ms)]
            related_warning=[w for a,b in matches for w in warnings if
                             (_same_referent(w,a) or _same_referent(w,b)) and _near(w,a,gap_ms)]
            if matches and related_warning:
                ids=sorted({x["id"] for pair in matches for x in pair})
                findings.append(_f(p,"CONFLICTED","REVIEW","CONFLICTING_STANCE",
                                   ids,sorted({x["id"] for x in related_warning})))
            elif matches:
                ids=sorted({x["id"] for pair in matches for x in pair})
                findings.append(_f(p,"SUPPORTED","FLAG","RELATED_ACTION_AND_PROMOTION",ids))
            elif hints or bad_refs or (actions and promos and not matches) or (
                invalid_tags & set(policies[p]["action_tags"]+
                                   policies[p]["promotion_tags"]+
                                   policies[p]["warning_tags"])):
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
            elif hints or bad_refs or all_with_tag("violence") or (
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
            elif hints or bad_refs or all_with_tag("pii_candidate") or (
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
            elif hints or bad_refs or all_with_tag("credential_claim","marketing_claim","absolute_claim") or (
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
            elif hints or bad_refs or unlocated_cues or (invalid_tags & set(configured_tags)):
                findings.append(_f(p,"INSUFFICIENT","REVIEW","UNVERIFIED_OR_UNLOCATED"))
            elif coverage!="FULL":
                findings.append(_f(p,"UNKNOWN","RECHECK","INCOMPLETE_OBSERVATION"))
            else:
                findings.append(_f(p,"NOT_SUPPORTED","NONE","NO_RELEVANT_CUE"))
    return {"coverage":coverage,"invalid_evidence_ids":invalid,"findings":findings,"event_findings":build_event_findings(good, findings, duration_ms)}

def validate_max_guidance(max_response: dict, findings: list, observations: list) -> list:
    """Reject LLM guidance that invents finding/evidence IDs or changes conclusions."""
    by_policy={f.get("id",f["policy_id"]): f for f in findings}
    available={e["id"]:e for e in observations if isinstance(e,dict) and e.get("id")}
    available_ids=set(available)
    results=[]
    for item in max_response.get("items",[]):
        fid=item.get("finding_id")
        # Prototype uses policy ID as finding ID to make offline fixtures simple.
        if fid not in by_policy or by_policy[fid]["disposition"]=="NONE":
            continue
        allowed=set(by_policy[fid]["supporting_ids"]+by_policy[fid]["counter_ids"])
        ids=item.get("evidence_ids",[])
        if not isinstance(ids,list) or not ids or not set(ids).issubset(allowed & available_ids):
            continue
        edits=item.get("edit_suggestions",[])
        if not isinstance(edits,list): continue
        invalid_edits=False
        for ed in edits:
            if not isinstance(ed,dict):
                invalid_edits=True; break
            edit_ids=ed.get("evidence_ids",[])
            if not isinstance(edit_ids,list) or not edit_ids or not set(edit_ids).issubset(allowed & available_ids):
                invalid_edits=True; break
            start,end=ed.get("time_start_ms"),ed.get("time_end_ms")
            if start is not None or end is not None:
                if type(start) is not int or type(end) is not int or start<0 or end<=start:
                    invalid_edits=True; break
                if not any(type(available[k].get("start_ms")) is int and
                           available[k]["start_ms"]<=start and
                           end<=available[k]["end_ms"] for k in edit_ids):
                    invalid_edits=True; break
        if invalid_edits: continue
        results.append(item)
    return results


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
