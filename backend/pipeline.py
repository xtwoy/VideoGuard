"""One linear pipeline. Third-party APIs are invoked only on the LIVE path."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Callable

from src.aliyun_client import omni_observe, max_explain
from src.jev_model_client import query_jev, select_pairs, build_request
from src.semantic_fusion import assess_joint
from src.pead_engine import build_event_findings, validate_max_guidance
from src.redaction import redact

VALID_COVERAGE={"FULL","PARTIAL","UNKNOWN","REFUSED","ERROR"}
VALID_MODALITIES={"visual","speech","screen_text","sound","metadata"}
VALID_TAGS={"danger_action","danger_description","encouragement","challenge","warning",
            "violence","news_context","fiction_context","pii_candidate",
            "credential_claim","marketing_claim","absolute_claim","self_harm_action",
            "self_harm_instruction","sexual_content","sexual_minor_risk",
            "hate_or_harassment","fraud_or_scam","financial_inducement","controlled_goods",
            "controlled_goods_promotion","minor_risk","education_context","other"}
POLICIES={
    "R_DANGER_PROMOTION":"危险行为诱导",
    "R_VIOLENCE":"暴力或危险行为画面",
    "R_PRIVACY_EXPOSURE":"个人隐私暴露",
    "R_MARKETING_CLAIM":"营销及资质声称",
    "R_SELF_HARM":"自伤风险",
    "R_SEXUAL_CONTENT":"性内容风险",
    "R_HATE_HARASSMENT":"仇恨与骚扰",
    "R_FRAUD_SCAM":"诈骗与高风险诱导",
    "R_CONTROLLED_GOODS":"受控商品风险",
    "R_MINORS_PROTECTION":"未成年人保护"
}
STATIC_ADVICE={
    "R_DANGER_PROMOTION":"请核对对应时段是否存在鼓励模仿危险行为的言语；必要时修改引导话术并补充明确安全说明。",
    "R_VIOLENCE":"请回看对应画面，核对是否属于新闻记录、影视演绎或安全教育，必要时补充准确的背景说明。",
    "R_PRIVACY_EXPOSURE":"请人工确认是否暴露私人联系方式、证件或住址；有风险时遮挡相关画面或消除对应音频。",
    "R_MARKETING_CLAIM":"请核对营销用语和职业资质声称的客观依据，无法核实时删除或修改相关表述。"
    ,"R_SELF_HARM":"请人工核对是否存在自伤相关画面、方法传播或诱导内容；必要时移除相关片段并补充求助与安全信息。"
    ,"R_SEXUAL_CONTENT":"请人工核对是否包含不适宜的性内容或性暗示；必要时删除、遮挡或调整发布范围。"
    ,"R_HATE_HARASSMENT":"请核对是否包含针对个人或群体的侮辱、歧视或定向骚扰；必要时删除攻击性表述并调整语境。"
    ,"R_FRAUD_SCAM":"请核对是否存在冒充、虚假获利、转账或高风险交易引导；无法证实的信息应删除或改为可核验表述。"
    ,"R_CONTROLLED_GOODS":"请核对是否展示、交易或引导获取受控商品；必要时移除相关内容并停止引导性表述。"
    ,"R_MINORS_PROTECTION":"请人工核对是否涉及未成年人不适宜、剥削或人身安全风险内容；必要时移除、遮挡并采取更严格的发布限制。"
}
MAX_OBSERVATIONS=80

def clean_observations(raw: dict, duration_ms: int | None = None) -> dict:
    """Treat provider output as untrusted. Retain useful errors for PEAD to flag."""
    if not isinstance(raw,dict):
        raise ValueError("Omni必须返回JSON对象")
    source=raw.get("observations")
    if not isinstance(source,list):
        raise ValueError("Omni输出缺少 observations 数组")
    if len(source)>MAX_OBSERVATIONS:
        raise ValueError("Omni观察证据过多，不能安全处理")
    coverage=raw.get("coverage","UNKNOWN")
    if coverage not in VALID_COVERAGE: coverage="UNKNOWN"
    cleaned=[]
    seen=set()
    for i,obs in enumerate(source):
        if not isinstance(obs,dict):
            raise ValueError(f"第{i+1}条观察不是对象")
        eid=str(obs.get("id",""))[:32]
        if not eid or eid in seen:
            raise ValueError("证据ID为空或重复")
        seen.add(eid)
        tag=obs.get("tag","other")
        modality=obs.get("modality","metadata")
        if tag not in VALID_TAGS: tag="other"
        if modality not in VALID_MODALITIES: modality="metadata"
        a,b=obs.get("start_ms"),obs.get("end_ms")
        # Invalid timestamps are preserved as None and cannot become strong evidence.
        invalid_time = not ((type(a) is int and type(b) is int) or
                            (a is None and b is None))
        if type(a) is int and type(b) is int:
            invalid_time = invalid_time or a < 0 or b <= a
            if duration_ms is not None:
                invalid_time = invalid_time or b > duration_ms
        if invalid_time:
            a=b=None
        ref=obs.get("referent_key")
        cleaned.append({
            "id":eid,
            "modality":modality,
            "tag":tag,
            "start_ms":a,"end_ms":b,
            "referent_key":redact(ref)[:60] if isinstance(ref,str) and ref else None,
            "description_redacted":redact(str(obs.get("description_redacted") or ""))[:600],
            "text_redacted":redact(str(obs.get("text_redacted") or ""))[:350],
            "verification":"MODEL_REPORTED"
        })
    candidates=[]
    raw_candidates=raw.get("candidate_risks")
    if not isinstance(raw_candidates,list):
        raw_candidates=[]
    for c in raw_candidates[:30]:
        if isinstance(c,dict) and c.get("policy_id") in POLICIES:
            candidates.append({
                "policy_id":c["policy_id"],
                "supporting_evidence_ids":[x for x in (c.get("supporting_evidence_ids")
                    if isinstance(c.get("supporting_evidence_ids"),list) else [])
                    if isinstance(x,str)][:20],
                "counter_evidence_ids":[x for x in (c.get("counter_evidence_ids")
                    if isinstance(c.get("counter_evidence_ids"),list) else [])
                    if isinstance(x,str)][:20]
            })
    return {
        "coverage":coverage,
        "coverage_notes":redact(str(raw.get("coverage_notes") or ""))[:300],
        "observations":cleaned,
        "candidate_risks":candidates
    }

def _rule_template(finding: dict) -> dict:
    """Create a clearly labelled fallback when Max has no valid guidance."""
    return {
        "finding_id":finding["id"],
        "reason":finding["reason_code"],
        "evidence_ids":finding["supporting_ids"],
        "uncertainties":["本条结果来自模型观察/规则推断，仍需原视频人工核对。"],
        "edit_suggestions":[{
            "time_start_ms":None,"time_end_ms":None,
            "action":"人工核查并修改",
            "detail":STATIC_ADVICE.get(finding["id"],"请人工复核相关视频片段。"),
            "evidence_ids":finding["supporting_ids"]
        }],
        "source":"RULE_TEMPLATE"
    }

def _run_models(observations: dict, duration_ms: int,
                jev_fn: Callable, max_fn: Callable,
                allow_jev: bool=True, allow_max: bool=True) -> dict:
    """Pure-ish orchestration: injectable model functions enable real offline testing."""
    jev_status="NOT_NEEDED"
    jev_response=None
    pairs=select_pairs(observations["observations"],duration_ms)
    if pairs:
        if not allow_jev:
            jev_status="SKIPPED_NO_KEY"
        else:
            try:
                jev_response=jev_fn(build_request(pairs))
                jev_status="LIVE" if isinstance(jev_response,dict) else "FAILED"
            except Exception:
                # Never confuse one provider outage with 'video is safe'.
                jev_status="FAILED"
    merged=assess_joint(observations,duration_ms,jev_response,
                        jev_failed=jev_status=="FAILED")
    findings=merged["merged"]["findings"]
    for f in findings:
        f["name"]=POLICIES.get(f["policy_id"], f["policy_id"])
        f["id"]=f["policy_id"]
    notes=[]
    guidance_status="SKIPPED_NO_KEY"
    action_findings=[f for f in findings if f["disposition"] not in ("NONE",)]
    if action_findings and allow_max:
        try:
            # Never send raw video or complete sensitive text to Qwen Max.
            context={
                "coverage": observations["coverage"],
                "findings":action_findings,
                "observations": [
                    e for e in observations["observations"]
                    if e["id"] in {
                        x for f in action_findings
                        for x in f["supporting_ids"]+f["counter_ids"]
                    }
                ]
            }
            max_response=max_fn(context)
            notes=validate_max_guidance(max_response,findings,
                                        observations["observations"])
            guidance_status="LIVE" if notes else "INVALID_OUTPUT"
        except Exception:
            guidance_status="FAILED"
    elif not action_findings:
        guidance_status="NOT_NEEDED"
    # Keep valid Max content, but never let a partial model response omit
    # guidance for another finding that still needs human action.
    valid_notes={n["finding_id"]:n for n in notes}
    for note in valid_notes.values():
        note["source"]="QWEN_MAX"
    notes=[valid_notes.get(f["id"],_rule_template(f)) for f in action_findings]
    if not pairs:
        semantic_check=merged["semantic_check"]
    elif jev_status=="SKIPPED_NO_KEY":
        semantic_check="SKIPPED_NO_KEY"
    elif jev_status=="FAILED":
        semantic_check="API_FAILED"
    else:
        semantic_check=merged["semantic_check"]
    return {
        "observations":observations["observations"],
        "coverage":observations["coverage"],
        "coverage_notes":observations["coverage_notes"],
        "findings":findings,
        # Rebuild after Jev fusion so event records carry the final judgement.
        "event_findings":build_event_findings(
            observations["observations"],findings,duration_ms),
        "recommendations":notes,
        "meta":{
            "omni":"LIVE",
            "jev":jev_status,
            "jev_semantic_check":semantic_check,
            "jev_decisions":merged["jev_decisions"],
            "max":guidance_status,
            "policy_version":"v0.3",
            "policy_count":len(findings),
            "note":"模型观察及规则判断属于辅助审核，并非真实违法认定。"
        }
    }

def run_live(video_bytes: bytes, duration_ms: int, title: str,
             omni_fn: Callable=omni_observe, jev_fn: Callable=query_jev,
             max_fn: Callable=max_explain) -> dict:
    if not os.getenv("DASHSCOPE_API_KEY") or not os.getenv("DASHSCOPE_BASE_URL"):
        raise RuntimeError("未配置阿里云百炼 API Key / Base URL")
    encoded=base64.b64encode(video_bytes).decode("ascii")
    assert len(encoded)<10_000_000, "video file is too large for Base64 provider input"
    observations=clean_observations(
        omni_fn("data:;base64,"+encoded,duration_ms,title),duration_ms)
    return _run_models(
        observations,duration_ms,
        jev_fn,max_fn,
        allow_jev=bool(os.getenv("TYPESAFE_API_KEY")),
        allow_max=True
    )

DEMO_FIXTURE_PATH=Path(__file__).parent/"fixtures"/"demo_omni_response.json"
DEMO_FACTS=json.loads(DEMO_FIXTURE_PATH.read_text(encoding="utf-8"))
DEMO_DURATION_MS=25_000

def run_demo() -> dict:
    evidence=clean_observations(DEMO_FACTS,DEMO_DURATION_MS)
    result=_run_models(evidence,DEMO_DURATION_MS,jev_fn=lambda _:None,
                       max_fn=lambda _:None,allow_jev=False,allow_max=False)
    result["meta"]["omni"]="DEMO_SYNTHETIC"
    result["meta"]["note"]="这是合成证据演示，不是任何真实视频的AI审核。"
    return result
