"""One linear pipeline. Third-party APIs are invoked only on the LIVE path."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Callable

from src.model_gateway import generate_audit_report, parse_video
from src.issue_locator_client import locate_issues
from src.relation_client import query_relations, select_pairs, build_request, validate_response
from src.relation_fusion import assess_joint
from src.pead_engine import build_event_findings
from src.audit_report import build_audit_context, build_fallback_audit_report, validate_audit_report
from src.redaction import redact

VALID_COVERAGE={"FULL","PARTIAL","UNKNOWN","REFUSED","ERROR"}
VALID_MODALITIES={"visual","speech","screen_text","sound","metadata"}
VALID_TIME_LOCALIZATION={"RELIABLE","APPROXIMATE","UNAVAILABLE"}
VALID_CONTINUITY={"CONTIGUOUS","CUT","TRANSITION","UNKNOWN"}
VALID_FACT_CONFIDENCE={"HIGH","MEDIUM","LOW","UNKNOWN"}
VALID_STANCE={"ENCOURAGEMENT","WARNING","REPORTING","FICTION","EDUCATION","QUOTE","UNKNOWN"}
VALID_TARGET_RELATION={"SAME_EVENT","DIFFERENT_EVENT","UNCERTAIN"}
VALID_READABILITY={"CLEAR","LIMITED","UNAVAILABLE"}
VALID_QUALITY_STATUS={"PASS","WARNING","FAIL","MANUAL_REVIEW"}
VALID_QUALITY_OR_NA=VALID_QUALITY_STATUS|{"NOT_APPLICABLE"}
VALID_ALIASING_STATUS={"PASS","WARNING","MANUAL_REVIEW"}
VALID_SEVERITY={"HIGH","MEDIUM","LOW"}
ANALYSIS_SECTIONS=("material_completeness","structure","hook","subject_presentation","audio_visual_quality")
ANALYSIS_CATEGORIES={
    "material_completeness":"MATERIAL_COMPLETENESS",
    "structure":"STRUCTURE",
    "hook":"HOOK",
    "subject_presentation":"SUBJECT_PRESENTATION",
    "audio_visual_quality":"AUDIOVISUAL",
}
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
MAX_SHOTS=120
MAX_EVENTS=100
MAX_CUES=80
MAX_FACTS_PER_SHOT=40
MAX_ANALYSIS_ISSUES=40


def _text(value: object, limit: int) -> str:
    """Bound and redact model text before it enters durable audit data."""
    return redact(str(value or ""))[:limit]


def _text_list(value: object, item_limit: int, count_limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item, item_limit) for item in value if isinstance(item, str)][:count_limit]


def _time_range(start: object, end: object, duration_ms: int | None) -> tuple[int, int]:
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError("时间范围必须是递增的毫秒整数")
    if duration_ms is not None and end > duration_ms:
        raise ValueError("时间范围超出原视频时长")
    return start, end


def _enum(value: object, valid: set[str], field: str) -> str:
    if value not in valid:
        raise ValueError(f"{field} 取值无效")
    return str(value)


def _clean_quality(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("shot.quality 必须是对象")
    audio=raw.get("audio")
    visual=raw.get("visual")
    if not isinstance(audio, dict) or not isinstance(visual, dict):
        raise ValueError("shot.quality 缺少 audio 或 visual 对象")
    return {
        "visual_clarity":_enum(raw.get("visual_clarity"),VALID_READABILITY,"quality.visual_clarity"),
        "speech_clarity":_enum(raw.get("speech_clarity"),VALID_READABILITY,"quality.speech_clarity"),
        "audio":{
            "status":_enum(audio.get("status"),VALID_QUALITY_STATUS,"quality.audio.status"),
            "voice_clarity":_enum(audio.get("voice_clarity"),VALID_QUALITY_OR_NA,"quality.audio.voice_clarity"),
            "bgm_interference":_enum(audio.get("bgm_interference"),VALID_QUALITY_OR_NA,"quality.audio.bgm_interference"),
            "evidence":_text(audio.get("evidence"),400),
            "evidence_refs":list(dict.fromkeys(audio.get("evidence_refs", [])))[:40] if isinstance(audio.get("evidence_refs"), list) else [],
            "limitations":_text_list(audio.get("limitations"),180,8),
        },
        "visual":{
            "clarity":_enum(visual.get("clarity"),VALID_QUALITY_STATUS,"quality.visual.clarity"),
            "pixelation":_enum(visual.get("pixelation"),VALID_QUALITY_STATUS,"quality.visual.pixelation"),
            "aliasing_candidate":_enum(visual.get("aliasing_candidate"),VALID_ALIASING_STATUS,"quality.visual.aliasing_candidate"),
            "evidence":_text(visual.get("evidence"),400),
            "evidence_refs":list(dict.fromkeys(visual.get("evidence_refs", [])))[:40] if isinstance(visual.get("evidence_refs"), list) else [],
            "limitations":_text_list(visual.get("limitations"),180,8),
        },
        "limitations":_text_list(raw.get("limitations"),180,8),
    }


def _clean_analysis_issues(raw: object, fact_map: dict[str, dict],
                           duration_ms: int | None, seen_ids: set[str],
                           category: str) -> list[dict]:
    if not isinstance(raw, list) or len(raw)>MAX_ANALYSIS_ISSUES:
        raise ValueError("content_analysis.issues 必须是受限数组")
    issues=[]
    for issue in raw:
        if not isinstance(issue, dict):
            raise ValueError("content_analysis issue 必须是对象")
        issue_id=str(issue.get("id", ""))[:32]
        if not issue_id or issue_id in seen_ids:
            raise ValueError("content_analysis issue ID 为空或重复")
        if issue.get("category") != category:
            raise ValueError("content_analysis issue 分类与分析区块不一致")
        start,end=_time_range(issue.get("start_ms"),issue.get("end_ms"),duration_ms)
        refs=issue.get("evidence_refs")
        if not isinstance(refs,list) or not refs or not set(refs).issubset(fact_map):
            raise ValueError("content_analysis issue 引用了不存在的事实")
        if not any(fact_map[ref]["start_ms"] < end and start < fact_map[ref]["end_ms"] for ref in refs):
            raise ValueError("content_analysis issue 时间未覆盖其证据")
        seen_ids.add(issue_id)
        issues.append({
            "id":issue_id,
            "category":category,
            "severity":_enum(issue.get("severity"),VALID_SEVERITY,"content_analysis issue severity"),
            "summary":_text(issue.get("summary"),600),
            "start_ms":start,
            "end_ms":end,
            "evidence_refs":refs[:40],
            "limitations":_text_list(issue.get("limitations"),180,8),
        })
    return issues


def _clean_analysis_trace(raw: object, fact_map: dict[str, dict],
                          duration_ms: int | None, label: str) -> dict:
    """Keep section-level summaries traceable, not only their issue arrays."""
    if not isinstance(raw, dict):
        raise ValueError(f"content_analysis.{label} 必须是对象")
    refs=raw.get("evidence_refs")
    if not isinstance(refs, list) or len(refs)>40 or not set(refs).issubset(fact_map):
        raise ValueError(f"content_analysis.{label}.evidence_refs 无效")
    ranges=raw.get("time_ranges")
    if not isinstance(ranges, list) or len(ranges)>40:
        raise ValueError(f"content_analysis.{label}.time_ranges 必须是数组")
    clean_ranges=[]
    for item in ranges:
        if not isinstance(item, dict):
            raise ValueError(f"content_analysis.{label}.time_ranges 项无效")
        start,end=_time_range(item.get("start_ms"),item.get("end_ms"),duration_ms)
        item_refs=item.get("evidence_refs")
        if not isinstance(item_refs, list) or not item_refs or not set(item_refs).issubset(fact_map):
            raise ValueError(f"content_analysis.{label}.time_ranges.evidence_refs 无效")
        if not any(fact_map[ref]["start_ms"] < end and start < fact_map[ref]["end_ms"] for ref in item_refs):
            raise ValueError(f"content_analysis.{label}.time_ranges 未覆盖引用事实")
        clean_ranges.append({"start_ms":start,"end_ms":end,"evidence_refs":list(dict.fromkeys(item_refs))[:40]})
    limitations=_text_list(raw.get("limitations"),180,8)
    if not refs and not limitations:
        raise ValueError(f"content_analysis.{label} 缺少证据时必须说明限制")
    if refs and (not clean_ranges or not all(any(ref in item["evidence_refs"] for item in clean_ranges) for ref in refs)):
        raise ValueError(f"content_analysis.{label}.time_ranges 必须覆盖全部 evidence_refs")
    return {
        "evidence_refs":list(dict.fromkeys(refs))[:40],
        "time_ranges":clean_ranges,
        "limitations":limitations,
    }


def _clean_content_analysis(raw: object, fact_map: dict[str, dict],
                            duration_ms: int | None) -> dict:
    """Keep only the audio/visual readability analysis.

    This protocol reviews content safety, not commercial content quality. The
    earlier material/structure/hook/subject blocks came from an e-commerce video
    rubric and are no longer requested; if a provider still sends them they are
    dropped rather than rejected.
    """
    if not isinstance(raw, dict):
        raise ValueError("解析结果缺少 content_analysis 对象")
    media=raw.get("audio_visual_quality")
    if not isinstance(media,dict):
        raise ValueError("content_analysis.audio_visual_quality 必须是对象")
    seen_ids:set[str]=set()
    return {
        "audio_visual_quality":{
            **_clean_analysis_trace(media,fact_map,duration_ms,"audio_visual_quality"),
            "summary":_text(media.get("summary"),800),
            "issues":_clean_analysis_issues(media.get("issues"),fact_map,duration_ms,seen_ids,"AUDIOVISUAL"),
        },
    }


def _validate_quality_refs(quality: dict, fact_map: dict[str, dict], shot_id: str) -> None:
    """Quality judgments must point at facts in the same shot when provided."""
    for item in (quality.get("audio", {}), quality.get("visual", {})):
        refs=item.get("evidence_refs", []) if isinstance(item, dict) else []
        if not isinstance(refs, list) or not set(refs).issubset(fact_map):
            raise ValueError(f"{shot_id} quality.evidence_refs 无效")
        if any(not ref.startswith(f"{shot_id}:") for ref in refs):
            raise ValueError(f"{shot_id} quality.evidence_refs 必须引用本 shot 事实")
    if not quality.get("audio", {}).get("evidence_refs") and not quality.get("audio", {}).get("limitations"):
        raise ValueError(f"{shot_id} audio quality 必须提供证据或限制")
    if not quality.get("visual", {}).get("evidence_refs") and not quality.get("visual", {}).get("limitations"):
        raise ValueError(f"{shot_id} visual quality 必须提供证据或限制")


def clean_video_parse(raw: dict, duration_ms: int | None = None) -> dict:
    """Validate the v2 factual parse before it can influence audit results."""
    if not isinstance(raw,dict):
        raise ValueError("视频解析必须返回JSON对象")
    if raw.get("schema_version") != "videoguard_video_parse_v2":
        raise ValueError("仅支持 videoguard_video_parse_v2 解析协议")
    coverage_raw=raw.get("coverage")
    if not isinstance(coverage_raw,dict):
        raise ValueError("解析结果 coverage 必须是对象")
    coverage=_enum(coverage_raw.get("status"),VALID_COVERAGE,"coverage.status")
    video_start,video_end=_time_range(coverage_raw.get("video_start_ms"),coverage_raw.get("video_end_ms"),duration_ms)
    if video_start != 0:
        raise ValueError("视频覆盖必须从原视频 0ms 开始")
    modalities=coverage_raw.get("modalities")
    if not isinstance(modalities,dict):
        raise ValueError("coverage.modalities 必须是对象")
    clean_coverage={
        "status":coverage, "video_start_ms":video_start, "video_end_ms":video_end,
        "modalities":{key:_enum(modalities.get(key),{"FULL","PARTIAL","UNKNOWN"},f"coverage.modalities.{key}")
                      for key in ("visual","speech","screen_text","sound")},
        "limitations":_text_list(coverage_raw.get("limitations"),180,10),
        "time_localization":_enum(coverage_raw.get("time_localization"),VALID_TIME_LOCALIZATION,"coverage.time_localization"),
    }
    timeline=raw.get("timeline")
    if not isinstance(timeline,dict):
        raise ValueError("解析结果缺少 timeline 对象")
    raw_shots=timeline.get("shots")
    if not isinstance(raw_shots,list) or len(raw_shots)>MAX_SHOTS:
        raise ValueError("timeline.shots 必须是受限数组")
    shots=[]; fact_map:dict[str,dict]={}; shot_ids=set(); last_end=0
    for index, shot in enumerate(raw_shots):
        if not isinstance(shot,dict):
            raise ValueError("shot 必须是对象")
        shot_id=str(shot.get("shot_id", ""))[:32]
        expected_shot_id=f"S{index + 1:03d}"
        if shot_id != expected_shot_id or shot_id in shot_ids:
            raise ValueError("shot_id 必须从 S001 连续编号")
        start,end=_time_range(shot.get("start_ms"),shot.get("end_ms"),duration_ms)
        if index and start < last_end:
            raise ValueError("shots 不得重叠")
        if coverage == "FULL" and ((index == 0 and start != video_start) or (index and start != last_end)):
            raise ValueError("FULL 覆盖时 shots 必须连续覆盖原视频")
        shot_ids.add(shot_id); last_end=end
        clean_shot={
            "shot_id":shot_id, "start_ms":start, "end_ms":end,
            "continuity":_enum(shot.get("continuity"),VALID_CONTINUITY,"shot.continuity"),
            "scene_summary":_text(shot.get("scene_summary"),600),
            "visual_facts":[], "speech_transcript":[], "subtitle_text":[],
            "screen_text":[], "audio_observations":[],
            "quality":_clean_quality(shot.get("quality")),
        }
        for field in ("visual_facts","speech_transcript","subtitle_text","screen_text","audio_observations"):
            values=shot.get(field)
            if not isinstance(values,list) or len(values)>MAX_FACTS_PER_SHOT:
                raise ValueError(f"{field} 必须是受限数组")
            for fact in values:
                if not isinstance(fact,dict):
                    raise ValueError("时间线事实必须是对象")
                fact_id=str(fact.get("fact_id", ""))[:32]
                ref=f"{shot_id}:{fact_id}"
                if not fact_id or ref in fact_map:
                    raise ValueError("fact_id 为空或重复")
                fact_start,fact_end=_time_range(fact.get("start_ms"),fact.get("end_ms"),duration_ms)
                if fact_start < start or fact_end > end:
                    raise ValueError("事实时间必须位于所属 shot 内")
                clean_fact={
                    "fact_id":fact_id, "start_ms":fact_start, "end_ms":fact_end,
                    "summary_zh":_text(fact.get("summary_zh"),500),
                    "verbatim_redacted":_text(fact.get("verbatim_redacted"),500),
                    "confidence":_enum(fact.get("confidence"),VALID_FACT_CONFIDENCE,"fact.confidence"),
                    "limitations":_text_list(fact.get("limitations"),160,5),
                }
                fact_map[ref]=clean_fact
                clean_shot[field].append(clean_fact)
        _validate_quality_refs(clean_shot["quality"], fact_map, shot_id)
        shots.append(clean_shot)
    if coverage == "FULL" and (not shots or last_end != video_end):
        raise ValueError("FULL 覆盖时 shots 必须覆盖至原视频结束")
    raw_events=timeline.get("events")
    if not isinstance(raw_events,list) or len(raw_events)>MAX_EVENTS:
        raise ValueError("timeline.events 必须是受限数组")
    events=[]; event_ids=set()
    for event in raw_events:
        if not isinstance(event,dict):
            raise ValueError("event 必须是对象")
        event_id=str(event.get("event_id", ""))[:32]
        if not event_id or event_id in event_ids:
            raise ValueError("event_id 为空或重复")
        start,end=_time_range(event.get("start_ms"),event.get("end_ms"),duration_ms)
        refs=event.get("evidence_refs")
        if not isinstance(refs,list) or not refs or not set(refs).issubset(fact_map):
            raise ValueError("event 引用了不存在的事实")
        if not any(fact_map[ref]["start_ms"] < end and start < fact_map[ref]["end_ms"] for ref in refs):
            raise ValueError("event 时间未覆盖其证据")
        context=event.get("context")
        if not isinstance(context,dict):
            raise ValueError("event.context 必须是对象")
        counter_refs=context.get("counter_context_refs")
        if not isinstance(counter_refs,list) or not set(counter_refs).issubset(fact_map):
            raise ValueError("event counter_context_refs 无效")
        event_ids.add(event_id)
        events.append({
            "event_id":event_id, "start_ms":start, "end_ms":end,
            "event_type":_text(event.get("event_type"),80) or "other",
            "referent_key":_text(event.get("referent_key"),60) or None,
            "summary":_text(event.get("summary"),600), "evidence_refs":refs[:40],
            "context":{
                "stance":_enum(context.get("stance"),VALID_STANCE,"event.context.stance"),
                "target_relation":_enum(context.get("target_relation"),VALID_TARGET_RELATION,"event.context.target_relation"),
                "counter_context_refs":counter_refs[:20],
            },
            "uncertainties":_text_list(event.get("uncertainties"),180,8),
        })
    video_summary=raw.get("video_summary")
    if not isinstance(video_summary,dict):
        raise ValueError("解析结果缺少 video_summary 对象")
    summary_refs=video_summary.get("evidence_refs")
    if not isinstance(summary_refs,list) or len(summary_refs)>40 or not set(summary_refs).issubset(fact_map):
        raise ValueError("video_summary.evidence_refs 无效")
    summary_ranges=video_summary.get("time_ranges")
    if not isinstance(summary_ranges,list) or len(summary_ranges)>40:
        raise ValueError("video_summary.time_ranges 必须是数组")
    clean_summary_ranges=[]
    for item in summary_ranges:
        if not isinstance(item,dict):
            raise ValueError("video_summary.time_ranges 项无效")
        start,end=_time_range(item.get("start_ms"),item.get("end_ms"),duration_ms)
        refs=item.get("evidence_refs")
        if not isinstance(refs,list) or not refs or not set(refs).issubset(fact_map):
            raise ValueError("video_summary.time_ranges.evidence_refs 无效")
        if not any(fact_map[ref]["start_ms"] < end and start < fact_map[ref]["end_ms"] for ref in refs):
            raise ValueError("video_summary.time_ranges 未覆盖引用事实")
        clean_summary_ranges.append({"start_ms":start,"end_ms":end,"evidence_refs":list(dict.fromkeys(refs))[:40]})
    summary_limitations=_text_list(video_summary.get("limitations"),180,12)
    if not summary_refs and not summary_limitations:
        raise ValueError("video_summary 缺少证据时必须说明限制")
    if summary_refs and (not clean_summary_ranges or not all(any(ref in item["evidence_refs"] for item in clean_summary_ranges) for ref in summary_refs)):
        raise ValueError("video_summary.time_ranges 必须覆盖全部 evidence_refs")
    detail={
        "schema_version":"videoguard_video_parse_v2", "coverage":clean_coverage,
        "timeline":{"shots":shots,"events":events},
        "video_summary":{"summary_zh":_text(video_summary.get("summary_zh"),1200),
                         "evidence_refs":list(dict.fromkeys(summary_refs))[:40],
                         "time_ranges":clean_summary_ranges,
                         "limitations":summary_limitations},
        "content_analysis":_clean_content_analysis(raw.get("content_analysis"),fact_map,duration_ms),
    }
    return {"coverage":coverage,
            "coverage_notes":_text("；".join(clean_coverage["limitations"]),300),
            "observation_detail":detail}


def clean_issue_locator(raw: dict, parsed: dict) -> dict:
    """Validate locator output and project only cited cues into PEAD input."""
    if not isinstance(raw,dict) or raw.get("schema_version") != "videoguard_issue_locator_v1":
        raise ValueError("仅支持 videoguard_issue_locator_v1 问题定位协议")
    detail=parsed["observation_detail"]
    events=detail["timeline"]["events"]
    facts={f"{shot['shot_id']}:{fact['fact_id']}":fact for shot in detail["timeline"]["shots"] for field in
           ("visual_facts","speech_transcript","subtitle_text","screen_text","audio_observations")
           for fact in shot[field]}
    by_event={event["event_id"]:event for event in events}
    reserved_ids = set(by_event) | set(facts)
    for section in detail.get("content_analysis", {}).values():
        if isinstance(section, dict):
            reserved_ids.update(issue["id"] for issue in section.get("issues", [])
                                if isinstance(issue, dict) and isinstance(issue.get("id"), str))
    raw_cues=raw.get("risk_cues",[])
    if not isinstance(raw_cues,list) or len(raw_cues)>MAX_CUES: raise ValueError("risk_cues 必须是受限数组")
    cues=[]; observations=[]; cue_ids=set()
    by_event={event["event_id"]:event for event in events}
    for cue in raw_cues:
        if not isinstance(cue,dict): raise ValueError("risk cue 必须是对象")
        cue_id=str(cue.get("cue_id", ""))[:32]
        tag=cue.get("tag")
        event_id=cue.get("event_id")
        refs=cue.get("evidence_refs",[])
        if not cue_id or cue_id in cue_ids or cue_id in reserved_ids or tag not in VALID_TAGS or event_id not in by_event:
            raise ValueError("risk cue ID、标签或事件无效")
        if not isinstance(refs,list) or not refs or not set(refs).issubset(facts):
            raise ValueError("risk cue 必须引用已有事实")
        cue_ids.add(cue_id); event=by_event[event_id]
        modality=cue.get("modality") if cue.get("modality") in VALID_MODALITIES else "metadata"
        observation=_text(cue.get("observation"),600)
        verbatim=_text(cue.get("verbatim_redacted"),350)
        cues.append({"cue_id":cue_id,"tag":tag,"event_id":event_id,"modality":modality,
                     "evidence_refs":refs[:30],"observation":observation,
                     "verbatim_redacted":verbatim,
                     "time_confidence":cue.get("time_confidence") if cue.get("time_confidence") in {"HIGH","MEDIUM","LOW","UNAVAILABLE"} else "UNAVAILABLE",
                     "needs_human_review":bool(cue.get("needs_human_review",False))})
        cue_start=min(facts[ref]["start_ms"] for ref in refs)
        cue_end=max(facts[ref]["end_ms"] for ref in refs)
        observations.append({"id":cue_id,"modality":modality,"tag":tag,
                             "start_ms":cue_start,"end_ms":cue_end,
                             "referent_key":event["referent_key"] or event_id,
                             "description_redacted":observation,"text_redacted":verbatim,
                             "verification":"MODEL_REPORTED_V2",
                             "source_refs":refs[:30], "event_id":event_id,
                             "time_confidence":cues[-1]["time_confidence"]})
    detail["risk_cues"]=cues
    detail["issue_locator_limitations"]=[_text(x,180) for x in raw.get("limitations",[]) if isinstance(x,str)][:10]
    return {"coverage":parsed["coverage"],"coverage_notes":parsed["coverage_notes"],
            "observations":observations,"observation_detail":detail}


def _run_models(observations: dict, duration_ms: int,
                relation_fn: Callable | None=None, report_fn: Callable | None=None,
                allow_relation: bool=True, allow_report: bool=True) -> dict:
    """Pure-ish orchestration: injectable model functions enable real offline testing."""
    if relation_fn is None or report_fn is None:
        raise ValueError("关系判断与审核报告阶段必须提供可调用实现")
    relation_status="NOT_NEEDED"
    relation_response=None
    pairs=select_pairs(observations["observations"],duration_ms)
    if pairs:
        if not allow_relation:
            relation_status="SKIPPED_NO_KEY"
        else:
            try:
                request=build_request(pairs)
                relation_response=relation_fn(request)
                decisions=validate_response(request,relation_response)
                if any(item["status"] != "VALID" for item in decisions):
                    relation_response=None
                    relation_status="INVALID_OUTPUT"
                else:
                    relation_status="LIVE"
            except Exception:
                # Never confuse one provider outage with 'video is safe'.
                relation_status="FAILED"
    merged=assess_joint(observations,duration_ms,relation_response,
                        relation_failed=relation_status in {"FAILED","INVALID_OUTPUT"})
    findings=merged["merged"]["findings"]
    for f in findings:
        f["name"]=POLICIES.get(f["policy_id"], f["policy_id"])
        f["id"]=f["policy_id"]
    event_findings=build_event_findings(observations["observations"],findings,duration_ms)
    audit_context=build_audit_context(observations,findings,event_findings)
    audit_report=None
    report_status="SKIPPED_NO_KEY"
    if allow_report:
        try:
            candidate=report_fn(audit_context)
            audit_report=validate_audit_report(candidate,observations,findings,duration_ms)
            report_status="LIVE" if audit_report else "INVALID_OUTPUT"
        except Exception:
            report_status="FAILED"
    if audit_report is None:
        audit_report=build_fallback_audit_report(observations,findings,duration_ms)
        report_status=f"FALLBACK_{report_status}"
    if not pairs:
        semantic_check=merged["semantic_check"]
    elif relation_status=="SKIPPED_NO_KEY":
        semantic_check="SKIPPED_NO_KEY"
    elif relation_status in {"FAILED","INVALID_OUTPUT"}:
        semantic_check="API_FAILED"
    else:
        semantic_check=merged["semantic_check"]
    return {
        "observations":observations["observations"],
        "coverage":observations["coverage"],
        "coverage_notes":observations["coverage_notes"],
        "observation_detail":observations.get("observation_detail"),
        "findings":findings,
        "event_findings":event_findings,
        "pead_audit":merged["merged"].get("pead_audit"),
        "audit_report":audit_report,
        "meta":{
            "video_parse":"LIVE",
            "relation_check":relation_status,
            "semantic_check":semantic_check,
            "relation_decisions":merged["relation_decisions"],
            "audit_report":report_status,
            "policy_version":"v0.3",
            "policy_count":len(findings),
            "note":"模型观察及规则判断属于辅助审核，并非真实违法认定。"
        }
    }

def run_live(video_bytes: bytes, duration_ms: int, title: str,
             parse_fn: Callable=parse_video, locator_fn: Callable=locate_issues,
             relation_fn: Callable=query_relations,
             report_fn: Callable=generate_audit_report) -> dict:
    if not os.getenv("VIDEO_MODEL_API_KEY") or not os.getenv("VIDEO_MODEL_BASE_URL"):
        raise RuntimeError("未配置视频模型 API Key / Base URL")
    encoded=base64.b64encode(video_bytes).decode("ascii")
    assert len(encoded)<10_000_000, "video file is too large for Base64 provider input"
    parsed=clean_video_parse(parse_fn("data:;base64,"+encoded,duration_ms,title),duration_ms)
    observations=clean_issue_locator(locator_fn(parsed["observation_detail"]),parsed)
    result=_run_models(
        observations,duration_ms,
        relation_fn,report_fn,
        allow_relation=bool(os.getenv("RELATION_MODEL_API_KEY")),
        allow_report=bool(os.getenv("AUDIT_REPORT_MODEL"))
    )
    result["meta"]["issue_locator"]="LIVE"
    return result

DEMO_PARSE_PATH=Path(__file__).parent/"fixtures"/"demo_video_parse_response.json"
DEMO_LOCATOR_PATH=Path(__file__).parent/"fixtures"/"demo_issue_locator_response.json"
DEMO_PARSE=json.loads(DEMO_PARSE_PATH.read_text(encoding="utf-8"))
DEMO_LOCATOR=json.loads(DEMO_LOCATOR_PATH.read_text(encoding="utf-8"))
DEMO_DURATION_MS=25_000

def run_demo() -> dict:
    parsed=clean_video_parse(DEMO_PARSE,DEMO_DURATION_MS)
    evidence=clean_issue_locator(DEMO_LOCATOR,parsed)
    result=_run_models(evidence,DEMO_DURATION_MS,relation_fn=lambda _:None,
                       report_fn=lambda _:None,allow_relation=False,allow_report=False)
    result["meta"]["video_parse"]="DEMO_SYNTHETIC"
    result["meta"]["issue_locator"]="DEMO_SYNTHETIC"
    result["meta"]["note"]="这是合成证据演示，不是任何真实视频的AI审核。"
    return result
