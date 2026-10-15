"""Validate and safely fall back for the final, evidence-traceable audit report."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from src.redaction import redact

DIMENSIONS = (
    "audit_coverage", "evidence_traceability", "safety_risk_control",
    "context_completeness", "material_completeness", "narrative_structure",
    "hook_clarity", "subject_presentation", "audiovisual_readability",
)
STATUSES = {"PASS", "WARNING", "FAIL", "MANUAL_REVIEW", "NOT_APPLICABLE"}
VERDICTS = {"PUBLISHABLE", "NEEDS_REVISION", "BLOCKED", "MANUAL_REVIEW"}
SOURCES = {"FINDING", "ANALYSIS"}
PRIORITIES = {"P0", "P1", "P2"}
ACTIONS = {
    "MASK", "REMOVE", "TRIM", "REORDER", "REPLACE", "ADD_CONTEXT",
    "EDIT_TEXT", "EDIT_AUDIO", "RECORD", "ADD_MEDIA", "VERIFY", "MANUAL_REVIEW",
}
SCOPES = {"EVENT", "GLOBAL"}
FACT_FIELDS = ("visual_facts", "speech_transcript", "subtitle_text", "screen_text", "audio_observations")
ANALYSIS_SECTIONS = (
    "material_completeness", "structure", "hook", "subject_presentation",
    "audio_visual_quality",
)
ANALYSIS_SECTION_LABELS = {
    "material_completeness": "素材完整性",
    "structure": "内容结构",
    "hook": "开头信息建立",
    "subject_presentation": "主体展示",
    "audio_visual_quality": "音画可读性",
}

# Shared marker for "this dimension never received evidence of its own". Kept as a
# named pair so every unevaluated branch reports the same score/status, and so the
# report-level verdict check can recognise the state without magic numbers.
UNEVALUATED_SCORE = 40
UNEVALUATED_STATUS = "MANUAL_REVIEW"

POLICY_NAMES = {
    "R_DANGER_PROMOTION": "危险行为诱导",
    "R_VIOLENCE": "暴力或危险行为画面",
    "R_PRIVACY_EXPOSURE": "个人隐私暴露",
    "R_MARKETING_CLAIM": "营销及资质声称",
    "R_SELF_HARM": "自伤风险",
    "R_SEXUAL_CONTENT": "性内容风险",
    "R_HATE_HARASSMENT": "仇恨与骚扰",
    "R_FRAUD_SCAM": "诈骗与高风险诱导",
    "R_CONTROLLED_GOODS": "受控商品风险",
    "R_MINORS_PROTECTION": "未成年人保护",
}

REASONS = {
    "RELATED_ACTION_AND_PROMOTION": "危险动作与鼓励或挑战表述指向同一事件。",
    "CONFLICTING_STANCE": "同一事件同时存在风险线索和警示或反对语境。",
    "MISSING_SEMANTIC_RELATION": "存在相关线索，但现有证据无法确认语义关联。",
    "UNLOCATED_PROMOTION": "存在相关表述线索，但缺少可靠时间定位。",
    "RELATION_CHECK_UNAVAILABLE": "关键语义关系尚未完成自动核验。",
    "RELATION_DISPUTES_BASELINE": "关系核验与基础证据存在分歧。",
    "RELATION_NOT_CONFIRMED": "未能确认危险动作与相关表述的关联。",
    "RELATION_AMBIGUITY": "相关表述存在语义歧义。",
    "RELATION_REFERENT_DISAGREEMENT": "不同观察对所指事件存在分歧。",
    "VIOLENCE_DEPICTION": "观察到疑似暴力或危险行为画面。",
    "DEPICTION_WITH_CONTEXT": "观察到相关画面，同时存在需要核验的语境线索。",
    "POTENTIAL_PII": "观察到可能包含个人隐私的信息。",
    "CREDENTIAL_AUTHENTICITY_UNKNOWN": "观察到资质声称，真实性需要外部材料核验。",
    "MARKETING_CLAIM_NEEDS_CONTEXT": "观察到营销或绝对化表述，需要结合上下文核对。",
    "SELF_HARM_CUE": "观察到可能涉及自伤相关内容的线索。",
    "SEXUAL_CONTENT_CUE": "观察到可能不适宜的性内容或性暗示线索。",
    "HATE_HARASSMENT_CUE": "观察到可能涉及仇恨、歧视、侮辱或定向骚扰的线索。",
    "FRAUD_SCAM_CUE": "观察到可能涉及高风险获利或交易引导的线索。",
    "CONTROLLED_GOODS_CUE": "观察到可能涉及受控商品展示、交易或引导的线索。",
    "MINOR_PROTECTION_CUE": "观察到可能涉及未成年人保护风险的线索。",
    "UNVERIFIED_OR_UNLOCATED": "存在相关线索，但证据未能可靠定位。",
    "UNLOCATED_PII": "存在隐私暴露线索，但证据未能可靠定位。",
    "UNLOCATED_MARKETING_CLAIM": "存在营销或资质声称线索，但证据未能可靠定位。",
    "INCOMPLETE_OBSERVATION": "视频观察不完整，需要补充核查。",
    "MODEL_UNAVAILABLE": "自动审核未能完成，需要重新执行。",
}


def _text(value: object, limit: int) -> str:
    return redact(str(value or ""))[:limit]


def _text_list(value: object, item_limit: int, count_limit: int) -> list[str]:
    return [_text(item, item_limit) for item in value if isinstance(item, str)][:count_limit] if isinstance(value, list) else []


def _range(start: object, end: object, duration_ms: int) -> tuple[int, int]:
    if type(start) is not int or type(end) is not int or start < 0 or end <= start or end > duration_ms:
        raise ValueError("报告时间范围无效")
    return start, end


def _analysis_entries(detail: dict) -> list[tuple[str, dict]]:
    """Return only validated analysis issues, retaining their source section."""
    content = detail.get("content_analysis") if isinstance(detail, dict) else {}
    entries=[]
    for section in ANALYSIS_SECTIONS:
        value = content.get(section) if isinstance(content, dict) else None
        for issue in value.get("issues", []) if isinstance(value, dict) else []:
            if isinstance(issue, dict) and isinstance(issue.get("id"), str):
                entries.append((section, issue))
    return entries


def _detail_catalog(detail: dict, observations: list[dict]) -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    catalog: dict[str, dict] = {}
    events: dict[str, dict] = {}
    analysis: dict[str, dict] = {}
    timeline = detail.get("timeline") if isinstance(detail, dict) else {}
    for shot in timeline.get("shots", []) if isinstance(timeline, dict) else []:
        if not isinstance(shot, dict):
            continue
        shot_id = shot.get("shot_id")
        for field in FACT_FIELDS:
            for fact in shot.get(field, []) if isinstance(shot.get(field), list) else []:
                if isinstance(shot_id, str) and isinstance(fact, dict) and isinstance(fact.get("fact_id"), str):
                    ref = f"{shot_id}:{fact['fact_id']}"
                    catalog[ref] = {"type": "FACT", "start_ms": fact.get("start_ms"), "end_ms": fact.get("end_ms"), "content": fact.get("summary_zh") or fact.get("verbatim_redacted") or "视频事实"}
    for event in timeline.get("events", []) if isinstance(timeline, dict) else []:
        if isinstance(event, dict) and isinstance(event.get("event_id"), str):
            events[event["event_id"]] = event
            catalog[event["event_id"]] = {"type": "EVENT", "start_ms": event.get("start_ms"), "end_ms": event.get("end_ms"), "content": event.get("summary") or "视频事件"}
    for observation in observations:
        if isinstance(observation, dict) and isinstance(observation.get("id"), str):
            catalog[observation["id"]] = {"type": "OBSERVATION", "start_ms": observation.get("start_ms"), "end_ms": observation.get("end_ms"), "content": observation.get("description_redacted") or observation.get("text_redacted") or "模型观察"}
    for _, issue in _analysis_entries(detail):
        analysis[issue["id"]] = issue
        catalog[issue["id"]] = {"type": "ANALYSIS", "start_ms": issue.get("start_ms"), "end_ms": issue.get("end_ms"), "content": issue.get("summary") or "视频分析问题"}
    return catalog, events, analysis


def build_audit_context(observation_result: dict, findings: list[dict], event_findings: list[dict]) -> dict:
    detail = observation_result.get("observation_detail") or {}
    analysis_issues = [{"section": section, **issue} for section, issue in _analysis_entries(detail)]
    return {
        "coverage": observation_result.get("coverage", "UNKNOWN"),
        "video_parse": detail,
        "observations": observation_result.get("observations", []),
        "findings": [{key: value if key != "event_decisions" else [
            {k: v for k, v in row.items() if k != "argument_labels"} for row in value]
                      for key, value in finding.items()} for finding in findings],
        "event_findings": event_findings,
        "analysis_issues": analysis_issues,
    }


def _clean_ranges(raw: object, catalog: dict[str, dict], duration_ms: int, allow_empty: bool = False) -> list[dict]:
    if not isinstance(raw, list) or (not raw and not allow_empty) or len(raw) > 40:
        raise ValueError("报告时间范围必须是受限数组")
    clean=[]
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("报告时间范围必须是对象")
        start, end = _range(item.get("start_ms"), item.get("end_ms"), duration_ms)
        refs = item.get("evidence_refs")
        if not isinstance(refs, list) or not refs or not set(refs).issubset(catalog):
            raise ValueError("报告时间范围必须引用已有证据")
        if not all(type(catalog[ref].get("start_ms")) is int and type(catalog[ref].get("end_ms")) is int
                   and catalog[ref]["start_ms"] < end and start < catalog[ref]["end_ms"] for ref in refs):
            raise ValueError("报告时间范围必须覆盖每一条引用证据")
        clean.append({"start_ms": start, "end_ms": end, "evidence_refs": list(dict.fromkeys(refs))[:30]})
    return clean


def _ranges_cover_refs(ranges: list[dict], refs: list[str], catalog: dict[str, dict]) -> bool:
    """Every declared evidence reference must be visibly represented in a time range."""
    for ref in refs:
        item=catalog.get(ref)
        if not item or type(item.get("start_ms")) is not int or type(item.get("end_ms")) is not int:
            return False
        if not any(ref in time_range["evidence_refs"]
                   and item["start_ms"] < time_range["end_ms"]
                   and time_range["start_ms"] < item["end_ms"] for time_range in ranges):
            return False
    return True


def _clean_evidence(raw: object, catalog: dict[str, dict], duration_ms: int) -> list[dict]:
    if not isinstance(raw, list) or not raw or len(raw) > 40:
        raise ValueError("supporting_evidence 必须是非空受限数组")
    result=[]
    for item in raw:
        if not isinstance(item, dict) or item.get("ref") not in catalog:
            raise ValueError("supporting_evidence 引用无效")
        ref = item["ref"]
        expected = catalog[ref]["type"]
        if item.get("type") != expected:
            raise ValueError("supporting_evidence 类型不匹配")
        ranges=_clean_ranges(item.get("time_ranges"),catalog,duration_ms)
        if not _ranges_cover_refs(ranges,[ref],catalog):
            raise ValueError("supporting_evidence 时间范围未覆盖自身引用")
        result.append({
            "ref": ref,
            "type": expected,
            "content": _text(item.get("content"), 700) or _text(catalog[ref]["content"], 700),
            "time_ranges":ranges,
            "limitations":_text_list(item.get("limitations"),240,12),
        })
    return result


def _clean_dimensions(raw: object, catalog: dict[str, dict], duration_ms: int) -> dict:
    if not isinstance(raw, dict) or set(raw) != set(DIMENSIONS):
        raise ValueError("dimension_scores 必须完整包含所有固定维度")
    output={}
    for name in DIMENSIONS:
        item=raw[name]
        if not isinstance(item, dict) or type(item.get("score")) is not int or not 0 <= item["score"] <= 100:
            raise ValueError("维度评分必须是 0-100 整数")
        if item.get("status") not in STATUSES:
            raise ValueError("维度状态无效")
        refs=item.get("evidence_refs")
        if not isinstance(refs, list) or not refs or not set(refs).issubset(catalog):
            raise ValueError("维度评分必须引用已有证据")
        ranges=_clean_ranges(item.get("time_ranges"),catalog,duration_ms)
        clean_refs=list(dict.fromkeys(refs))[:30]
        if not _ranges_cover_refs(ranges,clean_refs,catalog):
            raise ValueError("维度评分时间范围未覆盖全部证据")
        raw_items=item.get("items")
        if not isinstance(raw_items,list) or not raw_items or len(raw_items)>12:
            raise ValueError("维度评分必须包含受限的评分子项")
        clean_items=[]; keys=set(); item_refs=set()
        for detail in raw_items:
            if not isinstance(detail,dict):
                raise ValueError("维度评分子项无效")
            key=_text(detail.get("key"),64)
            label=_text(detail.get("label"),100)
            if not key or key in keys or not label:
                raise ValueError("维度评分子项 key 或 label 无效")
            if type(detail.get("score")) is not int or not 0 <= detail["score"] <= 100 or detail.get("status") not in STATUSES:
                raise ValueError("维度评分子项分数或状态无效")
            detail_refs=detail.get("evidence_refs")
            if not isinstance(detail_refs,list) or not detail_refs or not set(detail_refs).issubset(catalog):
                raise ValueError("维度评分子项必须引用已有证据")
            clean_detail_refs=list(dict.fromkeys(detail_refs))[:30]
            detail_ranges=_clean_ranges(detail.get("time_ranges"),catalog,duration_ms)
            if not _ranges_cover_refs(detail_ranges,clean_detail_refs,catalog):
                raise ValueError("维度评分子项时间范围未覆盖全部证据")
            keys.add(key); item_refs.update(clean_detail_refs)
            clean_items.append({
                "key":key,
                "label":label,
                "score":detail["score"],
                "status":detail["status"],
                "summary":_text(detail.get("summary"),240),
                "evidence_refs":clean_detail_refs,
                "time_ranges":detail_ranges,
                "limitations":_text_list(detail.get("limitations"),240,12),
            })
        if set(clean_refs) != item_refs:
            raise ValueError("维度汇总证据必须由评分子项完整覆盖")
        output[name]={
            "score":item["score"],
            "status":item["status"],
            "summary":_text(item.get("summary"),180),
            "items":clean_items,
            "evidence_refs":clean_refs,
            "time_ranges":ranges,
            "limitations":_text_list(item.get("limitations"),240,12),
        }
    return output


COUNTER_SOURCES = {"COUNTER_CONTEXT_TAGS", "CONTEXT_TAGS", "NOT_APPLICABLE", "NOT_CHECKED"}


def _clean_counter_evidence(raw: object) -> dict:
    """Normalise the counter-evidence provenance block, defaulting to unknown."""
    if not isinstance(raw, dict):
        return {"checked": False, "source": "NOT_CHECKED",
                "found": False, "relation_checked": False}
    source = raw.get("source")
    if source not in COUNTER_SOURCES:
        source = "NOT_CHECKED"
    return {
        "checked": bool(raw.get("checked")),
        "source": source,
        "found": bool(raw.get("found")),
        "relation_checked": bool(raw.get("relation_checked")),
    }


def validate_audit_report(raw: dict, observation_result: dict, findings: list[dict], duration_ms: int) -> dict | None:
    """Return a cleaned report only when it is fully traceable to validated inputs."""
    if not isinstance(raw, dict) or raw.get("schema_version") != "videoguard_audit_report_v1":
        return None
    detail=observation_result.get("observation_detail") or {}
    observations=observation_result.get("observations") or []
    catalog, events, analysis = _detail_catalog(detail, observations)
    active={f.get("id", f.get("policy_id")): f for f in findings if isinstance(f,dict) and f.get("disposition") != "NONE"}
    all_findings={f.get("id", f.get("policy_id")): f for f in findings if isinstance(f,dict)}
    try:
        verdict=raw.get("overall_verdict")
        if verdict not in VERDICTS or type(raw.get("overall_score")) is not int or not 0 <= raw["overall_score"] <= 100:
            raise ValueError("报告总评无效")
        dimensions=_clean_dimensions(raw.get("dimension_scores"),catalog,duration_ms)
        applicable_scores=[item["score"] for item in dimensions.values() if item["status"] != "NOT_APPLICABLE"]
        if applicable_scores and raw["overall_score"] > min(applicable_scores):
            raise ValueError("报告总分不得高于任何适用维度评分")
        plans=raw.get("revision_plan")
        if not isinstance(plans,list) or len(plans)>80:
            raise ValueError("revision_plan 无效")
        seen_plan_ids=set(); seen_issue_ids=set(); seen_action_ids=set(); covered_findings=set(); covered_analysis=set(); clean_plans=[]
        for plan in plans:
            if not isinstance(plan,dict) or plan.get("scope") not in SCOPES:
                raise ValueError("整改分组无效")
            plan_id=str(plan.get("id") or "")[:32]
            if not plan_id or plan_id in seen_plan_ids:
                raise ValueError("整改分组 ID 无效")
            seen_plan_ids.add(plan_id)
            event_id=plan.get("event_id")
            if plan["scope"] == "EVENT" and event_id not in events:
                raise ValueError("事件整改分组必须引用已有 event")
            if plan["scope"] == "GLOBAL" and event_id is not None:
                raise ValueError("全局整改分组不能绑定 event")
            video=plan.get("video")
            if not isinstance(video,dict):
                raise ValueError("整改分组缺少 video")
            video_ranges=_clean_ranges(video.get("time_ranges"),catalog,duration_ms,allow_empty=plan["scope"] == "GLOBAL")
            issues=plan.get("issues")
            actions=plan.get("actions")
            if not isinstance(issues,list) or not issues or not isinstance(actions,list) or not actions:
                raise ValueError("整改分组必须有问题与动作")
            clean_issues=[]; local_issue_ids=set()
            for issue in issues:
                if not isinstance(issue,dict) or issue.get("source") not in SOURCES or issue.get("priority") not in PRIORITIES:
                    raise ValueError("整改问题无效")
                issue_id=str(issue.get("id") or "")[:32]
                if not issue_id or issue_id in seen_issue_ids:
                    raise ValueError("整改问题 ID 无效")
                finding_ids=issue.get("finding_ids")
                analysis_ids=issue.get("analysis_issue_ids")
                if not isinstance(finding_ids,list) or not isinstance(analysis_ids,list):
                    raise ValueError("整改问题引用无效")
                if issue["source"] == "FINDING":
                    if not finding_ids or not set(finding_ids).issubset(active) or analysis_ids:
                        raise ValueError("FINDING 问题只能引用需处理 finding")
                    covered_findings.update(finding_ids)
                elif finding_ids or not analysis_ids or not set(analysis_ids).issubset(analysis):
                    raise ValueError("ANALYSIS 问题引用无效")
                else:
                    covered_analysis.update(analysis_ids)
                ranges=_clean_ranges(issue.get("time_ranges"),catalog,duration_ms,allow_empty=True)
                evidence=_clean_evidence(issue.get("supporting_evidence"),catalog,duration_ms)
                if not ranges and not issue.get("uncertainties"):
                    raise ValueError("未定位问题必须说明不确定性")
                evidence_refs={item["ref"] for item in evidence}
                if ranges and not all(set(item["evidence_refs"]).intersection(evidence_refs) for item in ranges):
                    raise ValueError("整改问题时间范围必须由 supporting_evidence 支撑")
                if not _text(issue.get("category"),100) or not _text(issue.get("title"),160) or not _text(issue.get("description"),1000):
                    raise ValueError("整改问题必须具有分类、标题和描述")
                seen_issue_ids.add(issue_id); local_issue_ids.add(issue_id)
                clean_issues.append({
                    "id":issue_id, "source":issue["source"], "finding_ids":finding_ids[:12], "analysis_issue_ids":analysis_ids[:12],
                    "priority":issue["priority"], "category":_text(issue.get("category"),100), "title":_text(issue.get("title"),160),
                    "description":_text(issue.get("description"),1000), "time_ranges":ranges,
                    "supporting_evidence":evidence, "uncertainties":_text_list(issue.get("uncertainties"),240,12),
                })
            clean_actions=[]; linked=set()
            for action in actions:
                if not isinstance(action,dict) or action.get("action") not in ACTIONS:
                    raise ValueError("整改动作无效")
                action_id=str(action.get("id") or "")[:32]
                related=action.get("related_issue_ids")
                if not action_id or action_id in seen_action_ids or not isinstance(related,list) or not related or not set(related).issubset(local_issue_ids):
                    raise ValueError("整改动作 ID 或关联问题无效")
                target=_clean_ranges(action.get("target_time_ranges"),catalog,duration_ms,allow_empty=True)
                reuse=_clean_ranges(action.get("reuse_time_ranges"),catalog,duration_ms,allow_empty=True)
                if type(action.get("requires_reshoot")) is not bool:
                    raise ValueError("requires_reshoot 必须是布尔值")
                detail=_text(action.get("detail"),1000)
                acceptance=_text(action.get("acceptance_criteria"),800)
                if not detail or not acceptance:
                    raise ValueError("整改动作必须具有明确动作和验收条件")
                if action["action"] in {"MASK", "REMOVE", "TRIM", "REORDER", "REPLACE", "EDIT_TEXT", "EDIT_AUDIO"} and not target:
                    raise ValueError("编辑已有片段的动作必须定位目标时间范围")
                if action["action"] in {"VERIFY", "MANUAL_REVIEW"} and action["requires_reshoot"]:
                    raise ValueError("核验或人工复核不能要求重新拍摄")
                seen_action_ids.add(action_id); linked.update(related)
                clean_actions.append({
                    "id":action_id, "related_issue_ids":related[:20], "action":action["action"],
                    "detail":detail, "target_time_ranges":target, "reuse_time_ranges":reuse,
                    "insertion_position":None if action.get("insertion_position") is None else _text(action.get("insertion_position"),300),
                    "requires_reshoot":action["requires_reshoot"], "acceptance_criteria":acceptance,
                })
            if linked != local_issue_ids:
                raise ValueError("每个整改问题必须关联至少一个动作")
            clean_plans.append({"id":plan_id, "section":_text(plan.get("section"),160), "scope":plan["scope"], "event_id":event_id,
                                "video":{"summary":_text(video.get("summary"),1000),"time_ranges":video_ranges},
                                "counter_evidence":_clean_counter_evidence(plan.get("counter_evidence")),
                                "issues":clean_issues,"actions":clean_actions})
        if set(active) != covered_findings:
            raise ValueError("每个需处理 finding 必须进入整改计划")
        if set(analysis) != covered_analysis:
            raise ValueError("每个已定位内容分析问题必须进入整改计划")
        has_flag=any(f.get("disposition") == "FLAG" for f in active.values())
        if has_flag and verdict not in {"BLOCKED","NEEDS_REVISION"}:
            raise ValueError("存在 FLAG 时报告总评不一致")
        if not has_flag and active and verdict != "MANUAL_REVIEW":
            raise ValueError("只有复核类 finding 时必须人工复核")
        if not active and analysis and verdict != ("NEEDS_REVISION" if observation_result.get("coverage") == "FULL" else "MANUAL_REVIEW"):
            raise ValueError("存在内容分析问题时报告总评不一致")
        if not active and not analysis:
            # A dimension that received no evidence of its own is reported as
            # UNEVALUATED_STATUS / UNEVALUATED_SCORE, and the report then cannot
            # claim the video is publishable. Accept either verdict so
            # "nothing found" and "nothing evaluated" stay distinguishable.
            unevaluated=any(item["status"] == UNEVALUATED_STATUS
                            and item["score"] == UNEVALUATED_SCORE
                            for item in dimensions.values())
            expected={"PUBLISHABLE"} if observation_result.get("coverage") == "FULL" else {"MANUAL_REVIEW"}
            if unevaluated:
                expected.add("MANUAL_REVIEW")
            if verdict not in expected:
                raise ValueError("无风险 finding 时报告总评不一致")
        return {"schema_version":"videoguard_audit_report_v1", "overall_verdict":verdict, "overall_score":raw["overall_score"],
                "executive_summary":_text(raw.get("executive_summary"),1000), "dimension_scores":dimensions,
                "revision_plan":clean_plans, "overall_direction":_text(raw.get("overall_direction"),1600),
                "limitations":_text_list(raw.get("limitations"),240,20) or ["机器辅助审核，需回看原视频并进行人工复核。"]}
    except (TypeError, ValueError, KeyError):
        return None


def _range_for(refs: list[str], catalog: dict[str, dict]) -> list[dict]:
    timed=[
        (ref, catalog[ref]) for ref in refs
        if ref in catalog and type(catalog[ref].get("start_ms")) is int
        and type(catalog[ref].get("end_ms")) is int
    ]
    if not timed:
        return []
    groups=[]
    for ref, item in sorted(timed, key=lambda pair: (pair[1]["start_ms"], pair[1]["end_ms"])):
        if not groups or item["start_ms"] > groups[-1]["end_ms"]:
            groups.append({"start_ms":item["start_ms"], "end_ms":item["end_ms"], "evidence_refs":[ref]})
            continue
        group=groups[-1]
        group["end_ms"]=max(group["end_ms"],item["end_ms"])
        group["evidence_refs"].append(ref)
    return groups


def _evidence_for(ref: str, catalog: dict[str, dict], limitations: list[str] | None = None) -> dict:
    item=catalog[ref]
    return {
        "ref":ref,
        "type":item["type"],
        "content":_text(item["content"],700),
        "time_ranges":_range_for([ref],catalog),
        "limitations":limitations or [],
    }


def _dimension_item(key: str, label: str, score: int, status: str, summary: str,
                    refs: list[str], catalog: dict[str, dict],
                    limitations: list[str] | None = None) -> dict:
    clean_refs=[ref for ref in dict.fromkeys(refs) if ref in catalog]
    if not clean_refs:
        raise ValueError("维度评分子项缺少可追溯证据")
    return {
        "key":key,
        "label":label,
        "score":score,
        "status":status,
        "summary":summary,
        "evidence_refs":clean_refs,
        "time_ranges":_range_for(clean_refs,catalog),
        "limitations":limitations or [],
    }


def _dimension(score: int, status: str, summary: str, items: list[dict],
               catalog: dict[str, dict], limitations: list[str] | None = None) -> dict:
    refs=list(dict.fromkeys(ref for item in items for ref in item["evidence_refs"]))
    if not refs:
        raise ValueError("维度评分缺少可追溯证据")
    return {
        "score":score,
        "status":status,
        "summary":summary,
        "items":items,
        "evidence_refs":refs,
        "time_ranges":_range_for(refs,catalog),
        "limitations":limitations or [],
    }


def _action_for(finding: dict, ranges: list[dict]) -> tuple[str, str, list[dict], str]:
    policy=finding.get("policy_id")
    if policy == "R_PRIVACY_EXPOSURE":
        return "MASK", "对疑似隐私文字所在画面进行遮挡或替换，避免保留可识别信息。", ranges, "回看对应画面时，疑似联系方式或其他个人信息已无法被识别。"
    if policy in {"R_DANGER_PROMOTION", "R_FRAUD_SCAM", "R_SELF_HARM", "R_CONTROLLED_GOODS"}:
        return "REMOVE", "移除或替换对应的引导性表述及其关联内容，避免继续传播该风险线索。", ranges, "回看对应片段时，已不再保留原有引导性表述或关联呈现。"
    if policy == "R_MARKETING_CLAIM":
        return "VERIFY", "核验对应资质或营销声称的外部依据；无法核验时删除或改写为可被证据支持的表述。", [], "已取得可核验依据，或相关未经证实的资质与营销声称已从视频中移除。"
    return "MANUAL_REVIEW", "人工回看对应片段并核对语境、对象和发布要求；确认后再决定是否编辑或调整发布。", [], "人工已完成原视频和对应证据的复核，并记录处理结论。"


def _evaluated_sections(detail: dict) -> dict[str, bool]:
    """Which content-quality sections the parse actually assessed.

    A section counts as assessed only when it cites traceable evidence. A section
    with neither located issues nor evidence was never examined, and must not be
    scored as if it had passed.
    """
    content=detail.get("content_analysis") if isinstance(detail, dict) else {}
    return {
        section.upper(): bool(
            isinstance(content.get(section), dict)
            and (content[section].get("evidence_refs") or content[section].get("issues")))
        for section in ANALYSIS_SECTIONS
    }


def _roll_up(items: list[dict], label: str) -> tuple[int, str, str]:
    """Aggregate a dimension from its items, taking the worst reported state.

    A parent must never look healthier than its own children: if one modality or
    one sub-check is unevaluated or failed, the dimension as a whole is too.
    """
    scores=[item["score"] for item in items]
    score=min(scores) if scores else UNEVALUATED_SCORE
    if any(item["status"] == "FAIL" for item in items):
        return score, "FAIL", f"{label}中存在未通过的子项。"
    if any(item["status"] == UNEVALUATED_STATUS and item["score"] == UNEVALUATED_SCORE
           for item in items):
        return score, UNEVALUATED_STATUS, f"{label}中仍有子项未完成评估，需人工判断。"
    if any(item["status"] == "MANUAL_REVIEW" for item in items):
        return score, "MANUAL_REVIEW", f"{label}中部分子项需要人工复核。"
    if any(item["status"] == "WARNING" for item in items):
        return score, "WARNING", f"{label}中部分子项需要关注。"
    return score, "PASS", f"{label}的子项均已评估，未发现问题。"


def _analysis_dimension(issue_entries: list[tuple[str, dict]], category: str,
                        fallback_refs: list[str], label: str, catalog: dict[str, dict],
                        evaluated: bool = True) -> dict:
    """Score one content-quality dimension from its parsed issues.

    ``evaluated`` says whether the parse assessed this dimension at all. When it
    did not, the dimension is reported as unevaluated rather than as a pass, so a
    report cannot manufacture quality scores for dimensions nobody looked at.
    """
    matched=[issue for _, issue in issue_entries if issue.get("category") == category]
    refs=[issue["id"] for issue in matched] or fallback_refs
    severities={issue.get("severity") for issue in matched}
    if "HIGH" in severities:
        status="FAIL"; score=35; summary=f"已定位到高优先级{label}问题。"
    elif "MEDIUM" in severities:
        status="WARNING"; score=60; summary=f"已定位到需要处理的{label}问题。"
    elif "LOW" in severities:
        status="WARNING"; score=75; summary=f"已定位到可优化的{label}问题。"
    elif evaluated:
        status="PASS"; score=90; summary=f"已评估{label}，未发现需要处理的已定位问题。"
    else:
        status=UNEVALUATED_STATUS; score=UNEVALUATED_SCORE
        summary=f"未对{label}完成评估，需人工判断。"
    if matched:
        items=[_dimension_item(
            key=issue["id"], label=label,
            score={"HIGH":35,"MEDIUM":60,"LOW":75}.get(issue.get("severity"),75),
            status={"HIGH":"FAIL","MEDIUM":"WARNING","LOW":"WARNING"}.get(issue.get("severity"),"WARNING"),
            summary=_text(issue.get("summary"),240), refs=[issue["id"]], catalog=catalog,
            limitations=_text_list(issue.get("limitations"),240,12),
        ) for issue in matched]
    else:
        items=[_dimension_item("observed_result",label,score,status,summary,refs,catalog)]
    return _dimension(score,status,summary,items,catalog)


def _audiovisual_dimension(issue_entries: list[tuple[str, dict]], fallback_refs: list[str],
                           readability: str, catalog: dict[str, dict]) -> dict:
    """Prefer explicit audio/visual issues over a generic shot-quality aggregate.

    The shot-quality fallback is only meaningful when the parse actually recorded
    per-shot quality, which ``readability`` distinguishes.
    """
    if any(issue.get("category") == "AUDIOVISUAL" for _, issue in issue_entries):
        return _analysis_dimension(issue_entries,"AUDIOVISUAL",fallback_refs,"音画可读性",catalog)
    if readability == "PASS":
        return _dimension(95,"PASS","已解析镜头的音画信息总体可辨认。",[
            _dimension_item("shot_readability","镜头可读性",95,"PASS","已解析镜头的音画信息总体可辨认。",fallback_refs,catalog),
        ],catalog)
    if readability == "WARNING":
        return _dimension(70,"WARNING","部分镜头的音画可读性需要人工回看。",[
            _dimension_item("shot_readability","镜头可读性",70,"WARNING","部分镜头的音画信息需要人工回看。",fallback_refs,catalog),
        ],catalog)
    return _analysis_dimension(issue_entries,"AUDIOVISUAL",fallback_refs,"音画可读性",catalog,
                               evaluated=False)


def _analysis_plan(issue_entries: list[tuple[str, dict]], catalog: dict[str, dict],
                   plan_number: int, issue_number: int, action_number: int) -> tuple[dict, int, int]:
    """Keep factual content-quality issues visible when the report model is unavailable."""
    fact_refs=[]
    for _, issue in issue_entries:
        fact_refs.extend(ref for ref in issue.get("evidence_refs", []) if ref in catalog)
    fact_refs=list(dict.fromkeys(fact_refs))
    video_summary="；".join(_text(catalog[ref]["content"],300) for ref in fact_refs[:6]) or "已定位内容分析问题的原始视频证据。"
    plan={
        "id":f"R{plan_number:02d}", "section":"内容呈现与可读性", "scope":"GLOBAL", "event_id":None,
        "video":{"summary":video_summary,"time_ranges":_range_for(fact_refs,catalog)},
        "issues":[], "actions":[],
    }
    for section, analysis_issue in issue_entries:
        issue_number += 1
        action_number += 1
        analysis_id=analysis_issue["id"]
        refs=list(dict.fromkeys([analysis_id, *analysis_issue.get("evidence_refs", [])]))
        ranges=_range_for(refs,catalog)
        evidence=[_evidence_for(ref,catalog,_text_list(analysis_issue.get("limitations"),240,12)) for ref in refs if ref in catalog]
        priority={"HIGH":"P1","MEDIUM":"P1","LOW":"P2"}.get(analysis_issue.get("severity"),"P2")
        issue_id=f"I{issue_number:02d}"
        label=ANALYSIS_SECTION_LABELS.get(section,"内容分析")
        plan["issues"].append({
            "id":issue_id, "source":"ANALYSIS", "finding_ids":[], "analysis_issue_ids":[analysis_id],
            "priority":priority, "category":analysis_issue.get("category") or label,
            "title":label, "description":_text(analysis_issue.get("summary"),1000),
            "time_ranges":ranges, "supporting_evidence":evidence,
            "uncertainties":_text_list(analysis_issue.get("limitations"),240,12),
        })
        plan["actions"].append({
            "id":f"A{action_number:02d}", "related_issue_ids":[issue_id], "action":"MANUAL_REVIEW",
            "detail":f"回看对应证据并确认{label}问题的具体剪辑、补录、补充素材或重拍方案；当前证据不足以自动指定唯一修改方式。",
            "target_time_ranges":[], "reuse_time_ranges":[], "insertion_position":None, "requires_reshoot":False,
            "acceptance_criteria":f"已完成对应片段的人工复核，并记录可执行的{label}处理决定及验收结果。",
        })
    return plan, issue_number, action_number


def build_fallback_audit_report(observation_result: dict, findings: list[dict], duration_ms: int) -> dict:
    """Build the same report contract from verified data when report generation is unavailable."""
    detail=observation_result.get("observation_detail") or {}
    observations=observation_result.get("observations") or []
    catalog, events, analysis=_detail_catalog(detail, observations)
    analysis_entries=_analysis_entries(detail)
    cues={cue.get("cue_id"):cue for cue in detail.get("risk_cues", []) if isinstance(cue,dict) and isinstance(cue.get("cue_id"),str)}
    active=[finding for finding in findings if isinstance(finding,dict) and finding.get("disposition") != "NONE"]
    grouped:dict[str|None,list[dict]]=defaultdict(list)
    for finding in active:
        ids=list(dict.fromkeys(finding.get("supporting_ids",[])+finding.get("counter_ids",[])))
        event_ids={cues[item].get("event_id") for item in ids if item in cues and cues[item].get("event_id") in events}
        for event_id in event_ids or {None}:
            grouped[event_id].append(finding)
    plans=[]; issue_number=0; action_number=0
    sortable=sorted(grouped, key=lambda key: events[key]["start_ms"] if key in events else duration_ms + 1)
    for position,event_id in enumerate(sortable,1):
        event=events.get(event_id)
        event_refs=list(event.get("evidence_refs",[])) if event else []
        plan={"id":f"R{position:02d}", "section":_text(event.get("summary"),160) if event else "全局审核项", "scope":"EVENT" if event else "GLOBAL", "event_id":event_id,
              "video":{"summary":_text(event.get("summary"),1000) if event else "该问题缺少可归属的独立视频事件。", "time_ranges":_range_for([event_id],catalog) if event_id else _range_for(event_refs,catalog)}, "issues":[], "actions":[]}
        for finding in grouped[event_id]:
            issue_number += 1; action_number += 1
            fid=finding.get("id",finding.get("policy_id"))
            ids=list(dict.fromkeys(finding.get("supporting_ids",[])+finding.get("counter_ids",[])))
            if event_id:
                # Only keep the cues that belong to this event; a finding can cite
                # cues from several events and each event gets its own plan.
                ids=[item for item in ids if cues.get(item,{}).get("event_id") == event_id]
            elif not ids:
                # A global plan has no event to filter against. Findings without
                # any event-bound cue (MISSING_SEMANTIC_RELATION, and every
                # INCOMPLETE_OBSERVATION under partial coverage) reach this branch;
                # without a fallback the issue would carry no evidence and
                # validate_audit_report would reject the whole report.
                ids=list(cues)
            fact_refs=[]
            for observation_id in ids:
                fact_refs.extend(cues.get(observation_id,{}).get("evidence_refs",[]))
            evidence_refs=list(dict.fromkeys(ids+fact_refs))
            ranges=_range_for(evidence_refs,catalog)
            evidence=[_evidence_for(ref,catalog) for ref in evidence_refs]
            if not evidence and event_refs:
                evidence=[_evidence_for(ref,catalog) for ref in event_refs]
                ranges=_range_for(event_refs,catalog)
            if not evidence:
                # Last resort: anchor the issue to a real, cited fact and keep the
                # limitation explicit. Never emit an issue with no evidence at all.
                anchor=next(iter(catalog),None)
                if anchor is None:
                    raise ValueError("无法为缺少事件归属的问题提供可回溯证据")
                evidence=[_evidence_for(anchor,catalog,
                                        ["该问题没有可直接定位的观察证据，仅以视频事实作为锚点。"])]
                ranges=_range_for([anchor],catalog)
            priority="P0" if finding.get("disposition") == "FLAG" else "P1"
            issue_id=f"I{issue_number:02d}"
            description=REASONS.get(finding.get("reason_code"),"该审核项需要结合原视频和可回溯证据人工核对。")
            issue={"id":issue_id,"source":"FINDING","finding_ids":[fid],"analysis_issue_ids":[],"priority":priority,
                   "category":POLICY_NAMES.get(finding.get("policy_id"),finding.get("policy_id","内容安全")),"title":POLICY_NAMES.get(finding.get("policy_id"),"内容安全问题"),
                   "description":description,"time_ranges":ranges,"supporting_evidence":evidence,
                   "uncertainties":[] if evidence else ["该审核项没有可用的定位证据，需人工补充核查。"]}
            action,detail_text,target,acceptance=_action_for(finding,ranges)
            plan["issues"].append(issue)
            plan["actions"].append({"id":f"A{action_number:02d}","related_issue_ids":[issue_id],"action":action,"detail":detail_text,
                                    "target_time_ranges":target,"reuse_time_ranges":[],"insertion_position":None,"requires_reshoot":False,"acceptance_criteria":acceptance})
        # Carry the counter-evidence provenance up to the plan. Without it the
        # report cannot tell "counter evidence was searched for and none exists"
        # apart from "this rule never looks for counter evidence".
        for finding in grouped[event_id]:
            block=finding.get("counter_evidence")
            if isinstance(block,dict):
                plan["counter_evidence"]={
                    "checked":bool(block.get("checked")),
                    "source":_text(block.get("source"),40),
                    "found":bool(block.get("found")),
                    "relation_checked":bool(block.get("relation_checked")),
                }
                break
        plans.append(plan)
    if analysis_entries:
        analysis_plan, issue_number, action_number=_analysis_plan(
            analysis_entries,catalog,len(plans)+1,issue_number,action_number,
        )
        plans.append(analysis_plan)
    flag=any(f.get("disposition") == "FLAG" for f in active)
    coverage=observation_result.get("coverage","UNKNOWN")
    fact_refs=[ref for ref,item in catalog.items() if item.get("type") == "FACT"]
    observation_refs=[ref for ref,item in catalog.items() if item.get("type") == "OBSERVATION"]
    event_refs=[ref for ref,item in catalog.items() if item.get("type") == "EVENT"]
    first_ref=next(iter(fact_refs or observation_refs or event_refs),None)
    refs=[first_ref] if first_ref else []
    if not refs:
        raise ValueError("无法基于空证据目录生成审核报告")
    quality_states=[shot.get("quality",{}) for shot in detail.get("timeline",{}).get("shots",[]) if isinstance(shot,dict)]
    readability="PASS" if quality_states and all(item.get("visual",{}).get("clarity") == "PASS" and item.get("audio",{}).get("status") == "PASS" for item in quality_states) else "WARNING"
    active_refs=list(dict.fromkeys(ref for finding in active for ref in
                                  [*finding.get("supporting_ids",[]), *finding.get("counter_ids",[])] if ref in catalog))
    context_refs=[event_id for event_id,event in events.items() if event.get("context",{}).get("stance") != "UNKNOWN"] or event_refs or refs
    coverage_items=[]
    declared=detail.get("coverage",{}).get("modalities",{}) if isinstance(detail,dict) else {}
    for key,label,field in (
        ("visual","视觉覆盖","visual_facts"),
        ("speech","口播覆盖","speech_transcript"),
        ("screen_text","屏幕文字覆盖","screen_text"),
        ("sound","声音覆盖","audio_observations"),
    ):
        matched=[f"{shot.get('shot_id')}:{fact.get('fact_id')}" for shot in detail.get("timeline",{}).get("shots",[])
                 if isinstance(shot,dict) for fact in shot.get(field,[]) if isinstance(fact,dict)
                 and f"{shot.get('shot_id')}:{fact.get('fact_id')}" in catalog]
        evidence=matched or refs
        modality=declared.get(key,"UNKNOWN")
        if modality == "FULL":
            # The parse reports having examined this modality, so "examined and
            # nothing of this kind found" is a real finding, whether or not it
            # happened to record a fact here.
            score=100
            status="PASS"
            note=("该模态已纳入完整视频解析。" if matched
                  else "该模态已完整解析，未记录可辨认内容；不能据此推断不存在内容。")
        else:
            # The modality was not fully observed: the dimension cannot be scored,
            # and claiming a pass here is exactly the defect this guards against.
            score=UNEVALUATED_SCORE
            status=UNEVALUATED_STATUS
            note=f"该模态仅记录为 {modality}，未被完整观察，不能据此推断不存在内容。"
        coverage_items.append(_dimension_item(key,label,score,status,note,evidence,catalog))
    trace_items=[]
    for ref in active_refs or refs:
        trace_items.append(_dimension_item(f"trace_{ref}","问题证据定位",95 if active_refs else 90,
                                           "PASS",f"{ref} 可回溯至已定位视频证据。",[ref],catalog))
    safety_items=[]
    for finding in active:
        finding_refs=[ref for ref in [*finding.get("supporting_ids",[]), *finding.get("counter_ids",[])] if ref in catalog] or refs
        policy=finding.get("policy_id", "风险项")
        finding_score=20 if finding.get("disposition") == "FLAG" else 55
        finding_status="FAIL" if finding.get("disposition") == "FLAG" else "MANUAL_REVIEW"
        safety_items.append(_dimension_item(
            f"finding_{policy}", POLICY_NAMES.get(policy,policy), finding_score, finding_status,
            REASONS.get(finding.get("reason_code"),"该风险项需要人工结合原片核对。"), finding_refs, catalog,
        ))
    if not safety_items:
        safety_items.append(_dimension_item("active_findings","需处理风险项",100,"PASS","未发现需要处置的风险 finding。",refs,catalog))
    context_uncertain=any(f.get("judgement") in {"CONFLICTED","INSUFFICIENT","UNKNOWN"} for f in active)
    assessed=_evaluated_sections(detail)
    context_items=[_dimension_item(
        "observable_context","可观察语境",55 if context_uncertain else 90,
        "MANUAL_REVIEW" if context_uncertain else "PASS",
        "相关语境只能以输入中的提示、画面或口播为准。",context_refs,catalog)]
    coverage_score,coverage_status,coverage_summary=_roll_up(coverage_items,"审核覆盖")
    trace_score,trace_status,trace_summary=_roll_up(trace_items,"证据可追溯")
    safety_score,safety_status,safety_summary=_roll_up(safety_items,"安全风险控制")
    context_score,context_status,context_summary=_roll_up(context_items,"语境完整性")
    dimensions={
        "audit_coverage":_dimension(coverage_score,coverage_status,coverage_summary,coverage_items,catalog),
        "evidence_traceability":_dimension(trace_score,trace_status,trace_summary,trace_items,catalog),
        "safety_risk_control":_dimension(safety_score,safety_status,safety_summary,safety_items,catalog),
        "context_completeness":_dimension(context_score,context_status,context_summary,context_items,catalog),
        "material_completeness":_analysis_dimension(analysis_entries,"MATERIAL_COMPLETENESS",refs,"素材完整性",catalog,evaluated=assessed["MATERIAL_COMPLETENESS"]),
        "narrative_structure":_analysis_dimension(analysis_entries,"STRUCTURE",refs,"内容结构",catalog,evaluated=assessed["STRUCTURE"]),
        "hook_clarity":_analysis_dimension(analysis_entries,"HOOK",refs,"开头信息建立",catalog,evaluated=assessed["HOOK"]),
        "subject_presentation":_analysis_dimension(analysis_entries,"SUBJECT_PRESENTATION",refs,"主体展示",catalog,evaluated=assessed["SUBJECT_PRESENTATION"]),
        "audiovisual_readability":_audiovisual_dimension(analysis_entries,refs,readability,catalog),
    }
    # A dimension that never received evidence of its own is counted as
    # unevaluated, so the report cannot claim a publishable verdict on the
    # strength of the dimensions that were examined.
    unevaluated=any(dimension["status"] == UNEVALUATED_STATUS
                    and dimension["score"] == UNEVALUATED_SCORE
                    for dimension in dimensions.values())
    if flag:
        verdict="BLOCKED"; direction="先处理 P0 风险项并回看对应原片段；完成遮挡、移除或替换后，再进行人工复核。"
    elif active:
        verdict="MANUAL_REVIEW"; direction="先按 P1 项回看证据并完成语境或外部依据核验，再决定是否编辑或调整发布。"
    elif analysis_entries and coverage == "FULL":
        verdict="NEEDS_REVISION"; direction="先回看并处理 P1、P2 内容呈现问题，确认具体剪辑或补充素材方案后，再进行人工复核。"
    elif coverage == "FULL" and not unevaluated:
        verdict="PUBLISHABLE"; direction="当前没有 PEAD 标记的需处理事项；发布前仍应完成常规人工复核。"
    else:
        # A dimension with no located evidence was not evaluated, so the report
        # must not conclude "publishable" on the strength of the dimensions that
        # did have evidence.
        verdict="MANUAL_REVIEW"
        direction=("存在未完成评估的维度，需先补充该维度的证据或由人工判断，"
                   "不能据此给出可发布结论。")
    candidate={"schema_version":"videoguard_audit_report_v1","overall_verdict":verdict,"overall_score":min(item["score"] for item in dimensions.values()),
            "executive_summary":("基于已验证的视频事实、问题定位和 PEAD 结果生成的审核报告。"
                                 if not unevaluated else
                                 "基于已验证的视频事实、问题定位和 PEAD 结果生成的审核报告；"
                                 "其中部分维度缺少可定位证据，尚未完成评估。"),
            "dimension_scores":dimensions,
            "revision_plan":plans,"overall_direction":direction,"limitations":["该报告由机器观察和规则结果生成，需回看原视频并进行人工复核。"]}
    validated=validate_audit_report(candidate,observation_result,findings,duration_ms)
    if validated is None:
        raise ValueError("兜底审核报告未通过正式协议校验")
    return validated
