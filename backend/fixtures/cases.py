"""Curated, reusable mock cases for VideoGuard-E — the case definitions.

Run ``python -m fixtures.generate`` to (re)write the static JSON files, and
``python -m fixtures.validate`` to check every case through the real pipeline.

Each case directory holds the raw provider responses for the model stages plus
a human-owned expectation file:

    <case>/video_parse_response.json      -> pipeline.clean_video_parse
    <case>/issue_locator_response.json    -> pipeline.clean_issue_locator
    <case>/relation_response.json         -> src.relation_client.validate_response
    <case>/audit_report_response.json     -> src.audit_report.validate_audit_report
    <case>/expectations.json              -> assertions owned by humans
    <case>/case.json                      -> title, purpose, derived outcome

Nothing here calls the network or re-implements validation: the generators pass
every authored object through the project's own validators.
"""
from __future__ import annotations

from fixtures._build import (
    cue, event, fact, fact_catalog, issue_locator, quality, shot, trace,
    video_parse,
)

DURATION_MS = 24_000

ALL_POLICIES = (
    "R_DANGER_PROMOTION", "R_VIOLENCE", "R_PRIVACY_EXPOSURE", "R_MARKETING_CLAIM",
    "R_SELF_HARM", "R_SEXUAL_CONTENT", "R_HATE_HARASSMENT", "R_FRAUD_SCAM",
    "R_CONTROLLED_GOODS", "R_MINORS_PROTECTION",
)


# ---------------------------------------------------------------------------
# Content-analysis scaffolding shared by the cases
# ---------------------------------------------------------------------------


def _ranges_for(catalog: dict[str, tuple[int, int]], refs: list[str]) -> list[dict]:
    """One time range per referenced fact, so every range overlaps its own refs."""
    ranges: list[dict] = []
    for ref in refs:
        span = catalog.get(ref)
        if span is None:
            continue
        ranges.append({"start_ms": span[0], "end_ms": span[1], "evidence_refs": [ref]})
    return ranges


def _section(evidence_refs: list[str], catalog: dict[str, tuple[int, int]],
             issues: list[dict] | None = None) -> dict:
    """A section trace block covering every declared ref.

    ``pipeline._clean_analysis_trace`` requires each declared ref to appear in
    some time range, and each range's refs to overlap that range.
    """
    ranges: list[dict] = []
    for issue in list(issues or []):
        for item in _ranges_for(catalog, issue["evidence_refs"]):
            item["start_ms"] = min(item["start_ms"], issue["start_ms"])
            item["end_ms"] = max(item["end_ms"], issue["end_ms"])
            ranges.append(item)
    if not ranges:
        ranges = _ranges_for(catalog, evidence_refs)
    if not ranges:
        raise ValueError(f"no catalog entry for any of {evidence_refs}")
    return {
        "evidence_refs": list(evidence_refs),
        "time_ranges": ranges,
        "limitations": [],
    }


def _summary(text: str, refs: list[str], catalog: dict[str, tuple[int, int]],
             limitations: list[str] | None = None) -> dict:
    block = trace(refs, [(span[0], span[1], [ref])
                         for ref in refs for span in [catalog.get(ref)] if span])
    block["summary_zh"] = text
    if limitations:
        block["limitations"] = list(limitations)
    return block


def _clean_structure() -> dict:
    return {
        "summary": "视频按开场、展开、收束推进，信息顺序连贯。",
        "opening": "开场直接给出主体与场景。",
        "body": "中段展开主体行为与相关说明。",
        "ending": "结尾给出收束性表述。",
        "sequence": ["开场建立场景", "中段展开主体内容", "结尾收束"],
        "hook_summary": "开场以主体与场景建立观看理由。",
        "hook_opening": "开场即出现主体与相关表述。",
        "hook_script": "开场有口播引入。",
        "hook_visual": "开场画面主体清晰。",
        "subject_summary": "主体在画面中持续可见。",
        "subject_visibility": "主体可辨认。",
        "subject_demonstration": "主体完成了相关内容呈现。",
        "subject_context": "场景为室内或户外自拍环境。",
        "media_summary": "音画信息总体清晰，口播可辨认。",
    }


def _analysis(summary: str, materials: list[str],
              catalog: dict[str, tuple[int, int]], structure: dict,
              refs: list[str], issues: list[dict] | None = None,
              section_refs: dict[str, list[str]] | None = None) -> dict:
    """Build content_analysis.

    ``refs`` is the default evidence set; ``section_refs`` optionally narrows an
    individual section by its protocol key.
    """
    issues = list(issues or [])
    overrides = section_refs or {}

    def section_issues(section: str) -> list[dict]:
        return [item for item in issues if item["category"] == section]

    def section_block(section: str) -> dict:
        key = section.lower()
        return _section(overrides.get(key, refs), catalog, section_issues(section))

    return {
        "material_completeness": {
            **section_block("MATERIAL_COMPLETENESS"),
            "summary": summary,
            "observed_materials": list(materials),
            "issues": section_issues("MATERIAL_COMPLETENESS"),
        },
        "structure": {
            **section_block("STRUCTURE"),
            "summary": structure["summary"],
            "opening": structure["opening"],
            "body": structure["body"],
            "ending": structure["ending"],
            "sequence": structure["sequence"],
            "issues": section_issues("STRUCTURE"),
        },
        "hook": {
            **section_block("HOOK"),
            "summary": structure["hook_summary"],
            "opening": structure["hook_opening"],
            "script": structure.get("hook_script"),
            "visual": structure.get("hook_visual"),
            "issues": section_issues("HOOK"),
        },
        "subject_presentation": {
            **section_block("SUBJECT_PRESENTATION"),
            "summary": structure["subject_summary"],
            "visibility": structure["subject_visibility"],
            "demonstration": structure["subject_demonstration"],
            "context": structure["subject_context"],
            "issues": section_issues("SUBJECT_PRESENTATION"),
        },
        "audio_visual_quality": {
            **section_block("AUDIOVISUAL"),
            "summary": structure["media_summary"],
            "issues": section_issues("AUDIOVISUAL"),
        },
    }


# ===========================================================================
# Case 1: danger action + encouragement pointing at the same event
# ===========================================================================


def _case_danger_promotion() -> dict:
    refs = ["S002:F001", "S003:F001", "S003:F002"]
    shots = [
        shot("S001", 0, 5000, "博主在室内开场并自我介绍",
             visual_facts=[fact("F001", 200, 4800, "画面为室内自拍场景，博主半身出镜。")],
             speech_transcript=[fact("F002", 300, 4600, "博主说明接下来要展示一个动作。",
                                     verbatim="今天教大家一个动作")],
             quality_block=quality(audio_refs=["S001:F002"], visual_refs=["S001:F001"])),
        shot("S002", 5000, 12000, "博主演示危险动作",
             visual_facts=[fact("F001", 5200, 11500, "博主在无防护条件下完成一项高风险动作。")],
             audio_observations=[fact("F002", 5400, 11300, "现场可听到落地撞击声。")],
             quality_block=quality(audio_refs=["S002:F002"], visual_refs=["S002:F001"])),
        shot("S003", 12000, 19000, "博主面向镜头鼓励观众模仿",
             speech_transcript=[
                 fact("F001", 12200, 15000, "博主鼓励观众模仿刚才的动作。",
                      verbatim="你们也来试试，很简单的"),
                 fact("F002", 15500, 18500, "博主使用挑战式表述再次引导模仿。",
                      verbatim="敢不敢挑战一下"),
             ],
             quality_block=quality(audio_refs=["S003:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
        shot("S004", 19000, 24000, "博主结束视频",
             speech_transcript=[fact("F001", 19200, 23500, "博主提示关注账号后结束。",
                                     verbatim="记得关注我")],
             quality_block=quality(audio_refs=["S004:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
    ]
    parse = video_parse(
        shots=shots,
        events=[
            event("EVT_DANGER", 5000, 19000, "danger_demonstration",
                  "博主演示危险动作并在随后鼓励观众模仿。",
                  ["S002:F001", "S003:F001"], stance="ENCOURAGEMENT",
                  target_relation="SAME_EVENT", referent_key="EVT_DANGER"),
        ],
        summary=_summary("博主演示一项无防护的危险动作，并鼓励观众模仿。", refs,
                         fact_catalog(shots)),
        content_analysis=_analysis(
            "素材为室内自拍，动作与鼓励表述齐全，但缺少安全提示画面。",
            ["室内自拍画面", "口播讲解", "动作演示"],
            fact_catalog(shots), _clean_structure(), refs,
            section_refs={"hook": ["S001:F002"]},
        ),
        video_end_ms=DURATION_MS,
    )
    locator = issue_locator([
        cue("E01", "danger_action", "EVT_DANGER", "visual", ["S002:F001"],
            "画面中博主在无防护条件下完成高风险动作。"),
        cue("E02", "encouragement", "EVT_DANGER", "speech", ["S003:F001"],
            "博主鼓励观众模仿同一动作。", verbatim="你们也来试试，很简单的"),
        cue("E03", "challenge", "EVT_DANGER", "speech", ["S003:F002"],
            "博主以挑战式表述再次引导模仿。", verbatim="敢不敢挑战一下"),
    ])
    return {
        "title": "危险动作＋鼓励模仿（核心研究场景）",
        "what_it_tests": "危险动作与鼓励表述指向同一事件时，PEAD 是否给出受支持的强提示。",
        "video_parse": parse,
        "issue_locator": locator,
        "relation_choice": "encourages_same",
        "expectations": {
            "coverage": "FULL",
            "findings": {"R_DANGER_PROMOTION": ["SUPPORTED", "FLAG"]},
            "active_finding_policies": ["R_DANGER_PROMOTION"],
            "event_findings_at_least": 1,
            "cues": ["E01", "E02", "E03"],
        },
    }


# ===========================================================================
# Case 2: the same dangerous action with an explicit warning
# ===========================================================================


def _case_warning_context() -> dict:
    refs = ["S002:F001", "S003:F001", "S003:F002"]
    shots = [
        shot("S001", 0, 5000, "安全教育短片开场",
             visual_facts=[fact("F001", 200, 4800, "画面为白底文字板。")],
             speech_transcript=[fact("F002", 300, 4600, "旁白说明这是安全教育短片。",
                                     verbatim="接下来是安全教育内容")],
             quality_block=quality(audio_refs=["S001:F002"], visual_refs=["S001:F001"])),
        shot("S002", 5000, 12000, "素材画面展示危险动作",
             visual_facts=[fact("F001", 5200, 11500, "素材画面中出现相同的危险动作。")],
             quality_block=quality(audio_status="MANUAL_REVIEW", voice_clarity="NOT_APPLICABLE",
                                   audio_evidence="该镜头无口播内容。",
                                   visual_refs=["S002:F001"])),
        shot("S003", 12000, 19000, "旁白明确警示不要模仿",
             speech_transcript=[
                 fact("F001", 12200, 15000, "旁白明确提醒不要模仿该动作。",
                      verbatim="请勿模仿，这非常危险"),
                 fact("F002", 15500, 18500, "旁白说明该行为可能造成严重伤害。",
                      verbatim="可能造成严重伤害"),
             ],
             quality_block=quality(audio_refs=["S003:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
        shot("S004", 19000, 24000, "结尾给出安全提示",
             speech_transcript=[fact("F001", 19200, 23500, "旁白提示观众注意安全。",
                                     verbatim="请注意安全")],
             quality_block=quality(audio_refs=["S004:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
    ]
    parse = video_parse(
        shots=shots,
        events=[
            event("EVT_EDU", 5000, 19000, "education_warning",
                  "安全教育画面展示危险动作并明确警示不要模仿。",
                  ["S002:F001", "S003:F001"], stance="WARNING",
                  target_relation="SAME_EVENT", referent_key="EVT_EDU",
                  counter_refs=["S003:F001", "S003:F002"]),
        ],
        summary=_summary("安全教育短片展示危险动作，并明确警示不要模仿。", refs,
                         fact_catalog(shots)),
        content_analysis=_analysis(
            "素材为文字板与素材画面组合，警示表述完整。",
            ["文字板画面", "素材画面", "旁白警示"],
            fact_catalog(shots), _clean_structure(), refs,
            section_refs={"hook": ["S001:F002"]},
        ),
        video_end_ms=DURATION_MS,
    )
    locator = issue_locator([
        cue("E01", "danger_action", "EVT_EDU", "visual", ["S002:F001"],
            "素材画面中出现相同的危险动作。", needs_human_review=True),
        cue("E02", "warning", "EVT_EDU", "speech", ["S003:F001"],
            "旁白明确警示不要模仿该动作。", verbatim="请勿模仿，这非常危险"),
        cue("E03", "warning", "EVT_EDU", "speech", ["S003:F002"],
            "旁白说明该行为的伤害后果，属于教育警示语境。", verbatim="可能造成严重伤害"),
    ])
    return {
        "title": "危险动作＋明确警示（安全语境，反误报对照）",
        "what_it_tests": "同一危险动作配明确警示时，系统不得把它判成鼓励诱导。"
                         "PEAD 把 warning 排除在鼓励语义之外，因此基线即为 NOT_SUPPORTED/NONE；"
                         "代价是“该片曾出现警示”不会体现在处置结果里。",
        "video_parse": parse,
        "issue_locator": locator,
        "relation_choice": "warns_same",
        "expectations": {
            "coverage": "FULL",
            "findings": {"R_DANGER_PROMOTION": ["NOT_SUPPORTED", "NONE"]},
            "active_finding_policies": [],
            "event_findings_at_least": 0,
            "cues": ["E01", "E02", "E03"],
        },
    }


# ===========================================================================
# Case 3: temporal proximity but unrelated topic (the H1 case)
# ===========================================================================


def _unrelated_scenario(relation_choice: str | None) -> dict:
    """Two cues that merely sit near each other but belong to different events.

    The building blocks are shared by two cases so the only difference a reader
    has to compare is whether the relation service answered.
    """
    refs = ["S002:F001", "S002:F002", "S003:F001"]
    shots = [
        shot("S001", 0, 5000, "生活记录开场",
             visual_facts=[fact("F001", 200, 4800, "画面为户外街景。")],
             speech_transcript=[fact("F002", 300, 4600, "博主说明在记录日常。",
                                     verbatim="记录一下今天")],
             quality_block=quality(audio_refs=["S001:F002"], visual_refs=["S001:F001"])),
        shot("S002", 5000, 12000, "博主演示滑板动作",
             visual_facts=[fact("F001", 5200, 11500, "博主在广场上完成一次滑板翻板动作。")],
             speech_transcript=[fact("F002", 5300, 8000, "博主讲解这个动作的练习要点。",
                                     verbatim="这个动作先练重心")],
             quality_block=quality(audio_refs=["S002:F002"], visual_refs=["S002:F001"])),
        shot("S003", 12000, 19000, "博主推荐附近的咖啡店",
             speech_transcript=[fact("F001", 12200, 18000,
                                     "博主鼓励观众去尝试附近新开的咖啡店，与滑板动作无关。",
                                     verbatim="这家新开的咖啡店你们一定要试试")],
             quality_block=quality(audio_refs=["S003:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
        shot("S004", 19000, 24000, "视频结束",
             speech_transcript=[fact("F001", 19200, 23500, "博主结束视频。",
                                     verbatim="今天就到这里")],
             quality_block=quality(audio_refs=["S004:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
    ]
    parse = video_parse(
        shots=shots,
        events=[
            event("EVT_SKATE", 5000, 12000, "sports_demonstration",
                  "博主演示并讲解滑板动作。", ["S002:F001", "S002:F002"],
                  stance="EDUCATION", target_relation="SAME_EVENT", referent_key="EVT_SKATE"),
            event("EVT_COFFEE", 12000, 19000, "product_recommendation",
                  "博主推荐附近的咖啡店，与滑板动作无关。", ["S003:F001"],
                  stance="UNKNOWN", target_relation="UNCERTAIN", referent_key="EVT_COFFEE"),
        ],
        summary=_summary("博主演示滑板动作，并在后段推荐附近的咖啡店。", refs,
                         fact_catalog(shots)),
        content_analysis=_analysis(
            "素材为户外生活记录，动作演示与推荐属于两个不同话题。",
            ["户外街景", "动作演示", "口播推荐"],
            fact_catalog(shots), _clean_structure(), refs,
            section_refs={"hook": ["S001:F002"]},
        ),
        video_end_ms=DURATION_MS,
    )
    locator = issue_locator([
        cue("E01", "danger_action", "EVT_SKATE", "visual", ["S002:F001"],
            "画面中出现一次滑板动作，未见明显危险行为。", needs_human_review=True),
        cue("E02", "encouragement", "EVT_COFFEE", "speech", ["S003:F001"],
            "博主鼓励观众尝试咖啡店，指向另一个话题。",
            verbatim="这家新开的咖啡店你们一定要试试"),
    ])
    return {"parse": parse, "locator": locator, "relation_choice": relation_choice}


def _case_unrelated_promotion() -> dict:
    scenario = _unrelated_scenario("unrelated")
    return {
        "title": "时间接近但事件不同＋语义判断为无关（H1 错误关联控制）",
        "what_it_tests": "两条线索指向不同事件、且语义判断明确回答 unrelated 时，PEAD 应当"
                         "据此判定不构成诱导。当前实现做不到：assess 在 MISSING_SEMANTIC_RELATION"
                         "分支产出的 finding 的 supporting_ids/counter_ids 都是空的，而"
                         "assess_joint 的每个分支都要求 pair 的两个 id 出现在这两个列表里，"
                         "因此 unrelated 结论被丢弃，结果停在 INSUFFICIENT/REVIEW。"
                         "本用例把这一现状固定下来，修好后应回落到 NOT_SUPPORTED/NONE。",
        "video_parse": scenario["parse"],
        "issue_locator": scenario["locator"],
        "relation_choice": scenario["relation_choice"],
        "expectations": {
            "coverage": "FULL",
            "findings": {"R_DANGER_PROMOTION": ["INSUFFICIENT", "REVIEW"]},
            "active_finding_policies": ["R_DANGER_PROMOTION"],
            "event_findings_at_least": 0,
            "cues": ["E01", "E02"],
        },
    }


def _case_unrelated_without_relation_service() -> dict:
    """Same evidence, but the relation stage is unavailable.

    Documents the conservative fallback: with no semantic judgement the system
    must send the pair to a human instead of reporting either risk or safety.
    """
    scenario = _unrelated_scenario(None)
    return {
        "title": "时间接近但事件不同＋无语义关系服务（保守分流对照）",
        "what_it_tests": "缺少语义关系核验时，系统必须转人工复核，既不能判为诱导，"
                         "也不能因为“没有确认”就判为无风险。",
        "video_parse": scenario["parse"],
        "issue_locator": scenario["locator"],
        "relation_choice": scenario["relation_choice"],
        "expectations": {
            "coverage": "FULL",
            "findings": {"R_DANGER_PROMOTION": ["INSUFFICIENT", "REVIEW"]},
            "active_finding_policies": ["R_DANGER_PROMOTION"],
            "event_findings_at_least": 0,
            "cues": ["E01", "E02"],
        },
    }


# ===========================================================================
# Case 4: news reporting context around violent footage
# ===========================================================================


def _case_news_violence() -> dict:
    refs = ["S002:F001", "S002:F002"]
    shots = [
        shot("S001", 0, 6000, "新闻片头",
             screen_text=[fact("F001", 200, 5800, "屏幕文字显示新闻栏目名称。",
                               verbatim="晚间新闻")],
             speech_transcript=[fact("F002", 300, 5700, "主播播报新闻提要。",
                                     verbatim="来看今天的报道")],
             quality_block=quality(audio_refs=["S001:F002"], visual_refs=["S001:F001"])),
        shot("S002", 6000, 14000, "报道画面出现冲突片段",
             visual_facts=[fact("F001", 6200, 13500, "报道画面中出现人群推搡的冲突片段。")],
             speech_transcript=[fact("F002", 6400, 13200, "主播说明该片段来自现场报道。",
                                     verbatim="这是现场画面")],
             quality_block=quality(audio_refs=["S002:F002"], visual_refs=["S002:F001"])),
        shot("S003", 14000, 24000, "主播说明与结束",
             speech_transcript=[fact("F001", 14200, 23500, "主播说明事件背景后结束报道。",
                                     verbatim="事件原因仍在调查")],
             quality_block=quality(audio_refs=["S003:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
    ]
    parse = video_parse(
        shots=shots,
        events=[
            event("EVT_NEWS", 6000, 14000, "news_report",
                  "新闻报道中出现冲突画面，主播说明其为现场报道。",
                  ["S002:F001", "S002:F002"], stance="REPORTING",
                  target_relation="SAME_EVENT", referent_key="EVT_NEWS",
                  counter_refs=["S002:F002"]),
        ],
        summary=_summary("新闻报道包含冲突现场画面，主播说明了报道语境。", refs,
                         fact_catalog(shots)),
        content_analysis=_analysis(
            "素材为新闻栏目画面，包含现场报道片段。",
            ["新闻片头", "现场报道画面", "主播口播"],
            fact_catalog(shots), _clean_structure(), refs,
            section_refs={"hook": ["S001:F001", "S001:F002"]},
        ),
        video_end_ms=DURATION_MS,
        modalities={"visual": "FULL", "speech": "FULL",
                    "screen_text": "FULL", "sound": "PARTIAL"},
    )
    locator = issue_locator([
        cue("E01", "violence", "EVT_NEWS", "visual", ["S002:F001"],
            "报道画面中出现人群推搡的冲突片段。", needs_human_review=True),
        cue("E02", "news_context", "EVT_NEWS", "speech", ["S002:F002"],
            "主播说明该片段来自现场报道，属于新闻语境。", verbatim="这是现场画面"),
    ])
    return {
        "title": "新闻语境下的暴力画面（语境对照）",
        "what_it_tests": "新闻语境不消除画面事实，但处置应转为需核验而非直接强提示。",
        "video_parse": parse,
        "issue_locator": locator,
        "relation_choice": None,
        "expectations": {
            "coverage": "FULL",
            "findings": {"R_VIOLENCE": ["SUPPORTED", "REVIEW"]},
            "active_finding_policies": ["R_VIOLENCE"],
            "event_findings_at_least": 1,
            "cues": ["E01", "E02"],
        },
    }


# ===========================================================================
# Case 5: privacy exposure from a single modality
# ===========================================================================


def _case_privacy_screen_text() -> dict:
    refs = ["S002:F001"]
    shots = [
        shot("S001", 0, 6000, "教程开场",
             speech_transcript=[fact("F001", 300, 5800, "博主介绍本期教程主题。",
                                     verbatim="本期讲报名流程")],
             quality_block=quality(audio_refs=["S001:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
        shot("S002", 6000, 15000, "画面展示含联系方式的截图",
             screen_text=[fact("F001", 6200, 14500, "画面展示一张含个人手机号的截图。",
                               verbatim="联系：138****5678")],
             quality_block=quality(audio_status="MANUAL_REVIEW", voice_clarity="NOT_APPLICABLE",
                                   audio_evidence="该镜头无口播内容。",
                                   visual_evidence="画面为屏幕录制内容。")),
        shot("S003", 15000, 24000, "教程收尾",
             speech_transcript=[fact("F001", 15200, 23500, "博主总结教程要点。",
                                     verbatim="以上就是全部流程")],
             quality_block=quality(audio_refs=["S003:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
    ]
    parse = video_parse(
        shots=shots,
        events=[
            event("EVT_PRIVACY", 6000, 15000, "screen_recording",
                  "教程截图展示了含个人联系方式的界面。", ["S002:F001"],
                  stance="UNKNOWN", target_relation="UNCERTAIN", referent_key="EVT_PRIVACY"),
        ],
        summary=_summary("教程视频中的截图展示了含个人联系方式的界面。", refs,
                         fact_catalog(shots)),
        content_analysis=_analysis(
            "素材为屏幕录制与口播讲解，包含一张含联系方式的截图。",
            ["屏幕录制画面", "口播讲解", "截图素材"],
            fact_catalog(shots), _clean_structure(), refs,
            section_refs={"hook": ["S001:F001"]},
        ),
        video_end_ms=DURATION_MS,
    )
    locator = issue_locator([
        cue("E01", "pii_candidate", "EVT_PRIVACY", "screen_text", ["S002:F001"],
            "画面截图出现疑似个人手机号，已按脱敏形式记录。",
            verbatim="联系：138****5678", needs_human_review=True),
    ])
    return {
        "title": "隐私暴露（单模态即可触发）",
        "what_it_tests": "仅屏幕文字一类证据即可形成隐私线索，且需保持脱敏。",
        "video_parse": parse,
        "issue_locator": locator,
        "relation_choice": None,
        "expectations": {
            "coverage": "FULL",
            "findings": {"R_PRIVACY_EXPOSURE": ["SUPPORTED", "FLAG"]},
            "active_finding_policies": ["R_PRIVACY_EXPOSURE"],
            "event_findings_at_least": 1,
            "cues": ["E01"],
        },
    }


# ===========================================================================
# Case 6: credential claim that needs external verification
# ===========================================================================


def _case_credential_claim() -> dict:
    refs = ["S002:F001", "S002:F002"]
    shots = [
        shot("S001", 0, 6000, "产品介绍开场",
             speech_transcript=[fact("F001", 300, 5800, "博主介绍将要推荐的产品。",
                                     verbatim="今天推荐一款产品")],
             quality_block=quality(audio_refs=["S001:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
        shot("S002", 6000, 17000, "博主声称专业资质并作营销表述",
             speech_transcript=[
                 fact("F001", 6200, 11000, "博主声称自己具备专业认证资质。",
                      verbatim="我是专业认证人士"),
                 fact("F002", 11500, 16500, "博主对产品效果作出绝对化表述。",
                      verbatim="这是最可靠的选择"),
             ],
             quality_block=quality(audio_refs=["S002:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
        shot("S003", 17000, 24000, "收尾与引导",
             speech_transcript=[fact("F001", 17200, 23500, "博主引导观众了解购买方式。",
                                     verbatim="详情见主页")],
             quality_block=quality(audio_refs=["S003:F001"],
                                   visual_evidence="该镜头无新增视觉判断。")),
    ]
    parse = video_parse(
        shots=shots,
        events=[
            event("EVT_CLAIM", 6000, 17000, "product_promotion",
                  "博主声称专业资质并对产品效果作出绝对化表述。",
                  ["S002:F001", "S002:F002"], stance="UNKNOWN",
                  target_relation="UNCERTAIN", referent_key="EVT_CLAIM"),
        ],
        summary=_summary("博主在推荐产品时声称专业资质，并使用了绝对化表述。", refs,
                         fact_catalog(shots)),
        content_analysis=_analysis(
            "素材为口播推荐，缺少可核验的资质材料画面。",
            ["口播讲解", "产品展示"],
            fact_catalog(shots), _clean_structure(), refs,
            section_refs={"hook": ["S001:F001"]},
        ),
        video_end_ms=DURATION_MS,
        modalities={"visual": "FULL", "speech": "FULL",
                    "screen_text": "PARTIAL", "sound": "FULL"},
    )
    locator = issue_locator([
        cue("E01", "credential_claim", "EVT_CLAIM", "speech", ["S002:F001"],
            "博主声称自己具备专业认证资质，真实性需要外部核验。",
            verbatim="我是专业认证人士", needs_human_review=True),
        cue("E02", "marketing_claim", "EVT_CLAIM", "speech", ["S002:F002"],
            "博主对产品效果作出绝对化表述。", verbatim="这是最可靠的选择"),
    ])
    return {
        "title": "资质声称＋营销绝对化表述（外部核验）",
        "what_it_tests": "资质真伪不能凭视频认定，应转为外部核验而非直接强提示。",
        "video_parse": parse,
        "issue_locator": locator,
        "relation_choice": None,
        "expectations": {
            "coverage": "FULL",
            "findings": {"R_MARKETING_CLAIM": ["SUPPORTED", "VERIFY_EXTERNAL"]},
            "active_finding_policies": ["R_MARKETING_CLAIM"],
            "event_findings_at_least": 1,
            "cues": ["E01", "E02"],
        },
    }


# ===========================================================================
# Case 7: PARTIAL coverage — incomplete observation must not read as "safe"
# ===========================================================================


def _case_partial_coverage() -> dict:
    refs = ["S001:F001"]
    shots = [
        shot("S001", 0, 9000, "视频前段可正常观察",
             visual_facts=[fact("F001", 200, 8800, "画面为室内自拍场景，博主半身出镜。",
                                limitations=["后段音轨损坏，无法确认后续内容。"])],
             quality_block=quality(audio_status="MANUAL_REVIEW", voice_clarity="NOT_APPLICABLE",
                                   audio_evidence="音轨在后段不可辨认。",
                                   visual_refs=["S001:F001"])),
    ]
    parse = video_parse(
        shots=shots,
        events=[],
        summary=_summary("仅前段音画可辨认，后段音轨损坏无法观察。", refs,
                         fact_catalog(shots),
                         limitations=["音轨损坏，后段内容未能观察。"]),
        content_analysis=_analysis(
            "仅前段素材可观察，后段因音轨损坏无法评估。",
            ["室内自拍画面"],
            fact_catalog(shots),
            _clean_structure() | {
                "summary": "仅前段可评估，后段信息缺失。",
                "body": "后段因音轨损坏无法观察。",
                "media_summary": "后段音轨不可辨认。",
            },
            refs,
        ),
        status="PARTIAL",
        video_end_ms=9000,
        modalities={"visual": "FULL", "speech": "UNKNOWN",
                    "screen_text": "PARTIAL", "sound": "PARTIAL"},
        coverage_limitations=["音轨在后段损坏，未能观察口播内容。"],
        time_localization="APPROXIMATE",
    )
    locator = issue_locator([], limitations=["问题定位仅覆盖可观察的前段内容。"])
    return {
        "title": "覆盖不完整（PARTIAL，不得等同安全）",
        "what_it_tests": "coverage 非 FULL 时，未观察到的类别必须转为补充观察而非无风险。",
        "video_parse": parse,
        "issue_locator": locator,
        "relation_choice": None,
        "expectations": {
            "coverage": "PARTIAL",
            "findings": {},
            "active_finding_policies": list(ALL_POLICIES),
            "event_findings_at_least": 0,
            "cues": [],
            "coverage_recheck_policies": list(ALL_POLICIES),
        },
    }


# ===========================================================================
# Case 8: clean negative — full coverage, no cues at all
# ===========================================================================


def _case_clean_negative() -> dict:
    refs = ["S001:F001", "S002:F001"]
    shots = [
        shot("S001", 0, 12000, "宠物日常记录",
             visual_facts=[fact("F001", 300, 11800, "画面为家中的猫在窗台休息。")],
             speech_transcript=[fact("F002", 400, 11600, "博主轻声介绍自家宠物。",
                                     verbatim="它今天很安静")],
             quality_block=quality(audio_refs=["S001:F002"], visual_refs=["S001:F001"])),
        shot("S002", 12000, 24000, "宠物进食画面",
             visual_facts=[fact("F001", 12300, 23500, "画面为猫在进食。")],
             quality_block=quality(audio_status="MANUAL_REVIEW", voice_clarity="NOT_APPLICABLE",
                                   audio_evidence="该镜头无口播内容。",
                                   visual_refs=["S002:F001"])),
    ]
    parse = video_parse(
        shots=shots,
        events=[
            event("EVT_PET", 0, 24000, "daily_life_record",
                  "记录宠物在家中的日常状态。", ["S001:F001", "S002:F001"],
                  stance="UNKNOWN", target_relation="UNCERTAIN", referent_key="EVT_PET"),
        ],
        summary=_summary("视频记录了一只猫在家中的日常状态。", refs, fact_catalog(shots)),
        content_analysis=_analysis(
            "素材为家庭宠物日常记录，未出现需要处置的内容线索。",
            ["宠物画面", "口播旁白"],
            fact_catalog(shots), _clean_structure(), refs,
            section_refs={"hook": ["S001:F001", "S001:F002"]},
        ),
        video_end_ms=DURATION_MS,
    )
    locator = issue_locator([])
    return {
        "title": "普通无风险视频（干净负例）",
        "what_it_tests": "无任何线索时应给出 NOT_SUPPORTED/NONE，且不虚构风险。",
        "video_parse": parse,
        "issue_locator": locator,
        "relation_choice": None,
        "expectations": {
            "coverage": "FULL",
            "findings": {},
            "active_finding_policies": [],
            "event_findings_at_least": 0,
            "cues": [],
        },
    }


CASES = {
    "danger_promotion": _case_danger_promotion,
    "warning_context": _case_warning_context,
    "unrelated_promotion": _case_unrelated_promotion,
    "unrelated_without_relation_service": _case_unrelated_without_relation_service,
    "news_violence": _case_news_violence,
    "privacy_screen_text": _case_privacy_screen_text,
    "credential_claim": _case_credential_claim,
    "partial_coverage": _case_partial_coverage,
    "clean_negative": _case_clean_negative,
}

CASE_ORDER = tuple(CASES)
