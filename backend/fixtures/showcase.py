"""Competition showcase cases.

These are deliberately separate from ``fixtures/cases.py``. The engineering fixtures
are allowed to be abstract, templated and adversarial — they exist to pin behaviour.
A showcase case has to survive a different question: *does the conclusion follow from
facts a reader can picture?* So each one below states what is on screen, what is said,
which facts carry the risk label, and why PEAD reached its verdict.

The stage-4 report is authored per case from the same report structure the system
validates, so the demo exercises the validated report path instead of the fallback
template.
"""
from __future__ import annotations

DURATION_MS = 26_000


def _fact(fact_id, start, end, summary, verbatim="", confidence="HIGH"):
    return {"fact_id": fact_id, "start_ms": start, "end_ms": end, "summary_zh": summary,
            "verbatim_redacted": verbatim, "confidence": confidence, "limitations": []}


def _quality(ref, modality="visual"):
    if modality == "visual":
        return {"visual_clarity": "CLEAR", "speech_clarity": "CLEAR",
                "audio": {"status": "PASS", "voice_clarity": "PASS", "bgm_interference": "PASS",
                          "evidence": "现场口播可辨认。", "evidence_refs": [ref], "limitations": []},
                "visual": {"clarity": "PASS", "pixelation": "PASS", "aliasing_candidate": "PASS",
                           "evidence": "画面清晰，主体可辨认。", "evidence_refs": [ref], "limitations": []},
                "limitations": []}
    return {"visual_clarity": "CLEAR", "speech_clarity": "CLEAR",
            "audio": {"status": "PASS", "voice_clarity": "PASS", "bgm_interference": "PASS",
                      "evidence": "口播清晰。", "evidence_refs": [ref], "limitations": []},
            "visual": {"clarity": "PASS", "pixelation": "PASS", "aliasing_candidate": "PASS",
                       "evidence": "画面清晰。", "evidence_refs": [ref], "limitations": []},
            "limitations": []}


def _shot(shot_id, start, end, summary, *, visual=(), speech=(), screen=(), continuity="CUT"):
    first = (visual or speech or screen or ())[0]["fact_id"] if (visual or speech or screen) else "F001"
    return {"shot_id": shot_id, "start_ms": start, "end_ms": end, "continuity": continuity,
            "scene_summary": summary, "quality": _quality(f"{shot_id}:{first}"),
            "visual_facts": list(visual), "speech_transcript": list(speech),
            "subtitle_text": [], "screen_text": list(screen), "audio_observations": []}


def _cue(cue_id, tag, event_id, modality, refs, observation, verbatim="", review=False):
    return {"cue_id": cue_id, "tag": tag, "event_id": event_id, "modality": modality,
            "evidence_refs": refs, "observation": observation, "verbatim_redacted": verbatim,
            "time_confidence": "HIGH", "needs_human_review": review}


def _parse(shots, events, summary, duration, summary_refs):
    catalog = {}
    for shot in shots:
        for field in ("visual_facts", "speech_transcript", "subtitle_text",
                      "screen_text", "audio_observations"):
            for fact in shot.get(field, []):
                catalog[f"{shot['shot_id']}:{fact['fact_id']}"] = (fact["start_ms"], fact["end_ms"])
    ranges = [{"start_ms": catalog[ref][0], "end_ms": catalog[ref][1], "evidence_refs": [ref]}
              for ref in summary_refs if ref in catalog]
    return {
        "schema_version": "videoguard_video_parse_v2",
        "coverage": {"status": "FULL", "video_start_ms": 0, "video_end_ms": duration,
                     "modalities": {"visual": "FULL", "speech": "FULL",
                                    "screen_text": "FULL", "sound": "FULL"},
                     "limitations": [], "time_localization": "RELIABLE"},
        "timeline": {"shots": shots, "events": events},
        "video_summary": {"summary_zh": summary, "evidence_refs": summary_refs,
                          "time_ranges": ranges, "limitations": []},
        "content_analysis": {
            "audio_visual_quality": {
                "summary": "画面与口播均清晰，可作为审核依据。",
                "evidence_refs": summary_refs,
                "time_ranges": ranges,
                "issues": [], "limitations": []}},
    }


def _event(event_id, start, end, summary, refs, stance="UNKNOWN", target="SAME_EVENT", event_type="other"):
    return {"event_id": event_id, "start_ms": start, "end_ms": end, "event_type": event_type,
            "referent_key": event_id, "summary": summary, "evidence_refs": refs,
            "context": {"stance": stance, "target_relation": target, "counter_context_refs": []},
            "uncertainties": []}


# ---------------------------------------------------------------------------
# Case 1: rooftop parkour, explicitly encouraging imitation
# ---------------------------------------------------------------------------
def _case_rooftop_parkour():
    duration = 26_000
    shots = [
        _shot("S001", 0, 6_000, "俯拍居民楼天台，可见楼间空隙与护栏",
              visual=[_fact("F001", 500, 5_500,
                            "俯拍一栋居民楼天台，金属护栏高约一米，外侧没有任何防护网，楼间空隙宽约两米。")],
              speech=[_fact("F002", 800, 5_000, "博主开场，语气兴奋。", "今天带你们看点刺激的")]),
        _shot("S002", 6_000, 15_000, "男子翻越护栏跨过楼间空隙",
              visual=[_fact("F001", 6_200, 14_500,
                            "一名年轻男子翻过天台护栏，跨过两栋楼之间约两米宽的间隙落到相邻楼顶，脚下是十二层楼的高度。")],
              continuity="CUT"),
        _shot("S003", 15_000, 22_000, "男子面对镜头说话",
              speech=[_fact("F001", 15_200, 18_500, "男子面向镜头，鼓动观众尝试同一动作。",
                            "你们也试试，胆大一点就行，别怕")]),
        _shot("S004", 22_000, 26_000, "男子从楼梯口离开天台",
              visual=[_fact("F001", 22_200, 25_800, "男子走向天台楼梯口，画面结束。")]),
    ]
    events = [_event("EVT_ROOFTOP", 6_000, 22_000,
                     "男子翻越天台护栏跨楼，随后面向镜头鼓励观众模仿。",
                     ["S002:F001", "S003:F001"], stance="ENCOURAGEMENT",
                     event_type="danger_demonstration")]
    parse = _parse(shots, events,
                   "男子在十二层天台翻越护栏跨楼，并明确鼓励观众模仿同一动作。",
                   duration, ["S002:F001", "S003:F001"])
    locator = {"schema_version": "videoguard_issue_locator_v1", "limitations": [], "risk_cues": [
        _cue("E01", "danger_action", "EVT_ROOFTOP", "visual", ["S002:F001"],
             "画面中男子翻越天台护栏跳过楼间空隙，下方为十二层高度。"),
        _cue("E02", "encouragement", "EVT_ROOFTOP", "speech", ["S003:F001"],
             "同一男子随后面对镜头，鼓动观众尝试同样的动作。",
             "你们也试试，胆大一点就行，别怕"),
    ]}
    return {
        "title": "天台跨楼动作 + 明确鼓励模仿",
        "what_it_tests": "同一事件内的画面动作与口播鼓励，构成危险行为诱导。",
        "story": "俯拍十二层天台；男子翻越护栏跳过楼间两米空隙；随后对着镜头说"
                 "\u201c你们也试试，胆大一点就行\u201d。画面事实只描述动作与环境，"
                 "风险解释留给问题定位与 PEAD。",
        "duration_ms": duration,
        "video_parse": parse,
        "issue_locator": locator,
        "relation_pair": ("E01", "E02", "encourages_same"),
        "report": {
            "summary": "视频在十二层天台拍摄，男子翻越护栏跳过楼间空隙，随后明确鼓励观众模仿。"
                       "画面中的高度、缺失防护与口播中的鼓动共同指向危险行为诱导。",
            "direction": "先对鼓励模仿的口播与整段跨楼动作做下架或移除处理，再评估是否保留动作回放；"
                         "不建议以\u201c挑战\u201d或\u201c教程\u201d形式重新发布同一素材。",
            "issues": {"R_DANGER_PROMOTION": (
                "6 秒处男子翻越天台护栏跨过楼间空隙，下方为十二层高度；15 秒处同一男子"
                "面向镜头鼓励观众尝试，构成本事件内的诱导表述。")},
            "actions": {"R_DANGER_PROMOTION": (
                "移除或遮挡 00:15-00:18 的鼓动口播，并对 00:06-00:15 的跨楼动作做下架处理。",
                "回看画面确认护栏、楼间空隙与楼层高度，确认整改后不再出现可模仿的完整动作链。")},
            "limitations": ["画面为合成演示素材，未对真实平台内容做识别验证。",
                            "楼层高度由画面推断，未做实地测量。"],
        },
    }


# ---------------------------------------------------------------------------
# Case 2: identical action, but the stance is a warning
# ---------------------------------------------------------------------------
def _case_rooftop_warning():
    case = _case_rooftop_parkour()
    duration = case["duration_ms"]
    shots = [shot for shot in case["video_parse"]["timeline"]["shots"]]
    shots[2] = _shot("S003", 15_000, 22_000, "男子面对镜头明确劝阻模仿",
                     speech=[_fact("F001", 15_200, 19_500,
                                   "男子面向镜头明确劝阻观众模仿，并说明风险。",
                                   "千万别学我，这里没有任何防护，摔下去就是重伤")])
    events = [_event("EVT_ROOFTOP", 6_000, 22_000,
                     "男子翻越天台护栏跨楼，随后明确劝阻观众模仿。",
                     ["S002:F001", "S003:F001"], stance="WARNING",
                     event_type="danger_demonstration")]
    parse = _parse(shots, events,
                   "男子在十二层天台翻越护栏跨楼，但明确劝阻观众模仿。",
                   duration, ["S002:F001", "S003:F001"])
    locator = {"schema_version": "videoguard_issue_locator_v1", "limitations": [], "risk_cues": [
        _cue("E01", "danger_action", "EVT_ROOFTOP", "visual", ["S002:F001"],
             "画面中男子翻越天台护栏跳过楼间空隙，下方为十二层高度。"),
        _cue("E02", "warning", "EVT_ROOFTOP", "speech", ["S003:F001"],
             "同一男子随后面对镜头劝阻观众模仿。",
             "千万别学我，这里没有任何防护，摔下去就是重伤"),
    ]}
    return {
        "title": "同一跨楼动作 + 明确劝阻模仿",
        "what_it_tests": "动作事实相同、立场相反时，PEAD 不应判为诱导。",
        "story": "与上一案例使用同一组画面事实，只把 15 秒后的口播换成劝阻。"
                 "用于说明结论差异来自立场论证，而不是画面差异。",
        "duration_ms": duration,
        "video_parse": parse,
        "issue_locator": locator,
        "relation_pair": ("E01", "E02", "warns_same"),
        "report": {
            "summary": "画面与上一案例相同：男子在十二层天台翻越护栏跨楼。区别在于他随后"
                       "明确劝阻观众模仿并说明风险，因此不构成危险行为诱导。",
            "direction": "本条按\u201c危险行为诱导\u201d策略不构成风险；动作本身的危险性"
                         "属平台其他规范范畴，建议按现行安全条款人工判断是否保留。",
            "issues": {},
            "actions": {},
            "limitations": ["画面为合成演示素材。",
                            "本条仅覆盖\u201c危险行为诱导\u201d策略，不评价其他安全条款。"],
        },
    }


# ---------------------------------------------------------------------------
# Case 3: model links a kitchen stunt with an unrelated cycling remark
# ---------------------------------------------------------------------------
def _case_cross_event():
    duration = 24_000
    shots = [
        _shot("S001", 0, 6_000, "室内厨房，先热油",
              speech=[_fact("F001", 500, 5_500, "博主在厨房介绍做菜步骤。", "先把油烧热再下锅")]),
        _shot("S002", 6_000, 12_000, "男子撑灶台跳过火焰",
              visual=[_fact("F001", 6_300, 11_500,
                            "一名男子单手撑住灶台边缘，从正在燃烧的灶眼上方跳过去，火焰高度约二十厘米。")]),
        _shot("S003", 12_000, 18_000, "切换到户外骑行画面",
              visual=[_fact("F001", 12_300, 17_500, "画面切到户外，一名骑手在公路上骑行。")],
              speech=[_fact("F002", 12_800, 16_800, "骑行男子对着镜头说话。",
                            "这个动作我练了三个月，别模仿")]),
        _shot("S004", 18_000, 24_000, "回到厨房收尾",
              speech=[_fact("F001", 18_200, 23_500, "博主总结这次拍摄。", "以上就是今天的分享")]),
    ]
    events = [
        _event("EVT_STOVE", 6_000, 12_000, "厨房内男子撑灶台跳过燃烧的灶眼。",
               ["S002:F001"], event_type="danger_demonstration"),
        _event("EVT_BIKE", 12_000, 18_000, "户外骑行，骑手提醒观众不要模仿。",
               ["S003:F001", "S003:F002"], stance="WARNING", event_type="other"),
    ]
    parse = _parse(shots, events,
                   "厨房里男子跳过燃烧灶眼；随后切到户外骑行画面，骑手提醒不要模仿。",
                   duration, ["S002:F001", "S003:F002"])
    locator = {"schema_version": "videoguard_issue_locator_v1", "limitations": [], "risk_cues": [
        _cue("E01", "danger_action", "EVT_STOVE", "visual", ["S002:F001"],
             "男子在厨房撑住灶台跳过燃烧的灶眼。"),
        _cue("E02", "warning", "EVT_BIKE", "speech", ["S003:F002"],
             "另一场景中的骑手提醒观众不要模仿。"),
    ]}
    return {
        "title": "跨事件误关联（厨房动作 × 骑行提醒）",
        "what_it_tests": "模型把两个不同场景的事件关联成同一件事时，结构证据能否否决。",
        "story": "厨房里男子跳过燃烧的灶眼；镜头随后切到户外骑行，骑手说\u201c这个动作我练了三个月，"
                 "别模仿\u201d。关系模型错误地把这句话当成对厨房动作的评价。",
        "duration_ms": duration,
        "video_parse": parse,
        "issue_locator": locator,
        # 故意让关系模型给出错误链接：把不同事件说成同一事件
        "relation_pair": ("E01", "E02", "encourages_same"),
        "report": {
            "summary": "厨房镜头中男子跳过燃烧灶眼（EVT_STOVE）；随后画面切到户外骑行（EVT_BIKE），"
                       "骑手的提醒属于另一场景。关系模型把两句关联为同一事件，被事件与指代约束否决。",
            "direction": "本事件按\u201c关系冲突\u201d转人工复核：需确认厨房动作是否有其他鼓励表述，"
                         "并核对骑行画面是否与厨房内容属于同一次拍摄。",
            "issues": {"R_DANGER_PROMOTION": (
                "厨房动作与骑行提醒分属两个事件，模型的关系回答与结构化证据冲突，"
                "因此不采信\u201c同一事件\u201d的关联。")},
            "actions": {"R_DANGER_PROMOTION": (
                "回看 00:06-00:12 与 00:12-00:18 两段，确认两者是否为同一次拍摄与同一主体。",
                "确认后重新提交；若确属两次拍摄，应拆分为两个独立素材审核。")},
            "limitations": ["画面为合成演示素材。",
                            "关系模型回答为构造的错误关联，用于验证结构约束。"],
        },
    }


# ---------------------------------------------------------------------------
# Case 4: ID card visible on a phone screen
# ---------------------------------------------------------------------------
def _case_id_card():
    duration = 20_000
    shots = [
        _shot("S001", 0, 7_000, "桌面开箱，手机屏幕朝向镜头",
              visual=[_fact("F001", 500, 6_500, "桌面上放着快递盒与一部手机，手机屏幕朝向镜头。")]),
        _shot("S002", 7_000, 14_000, "手机相册展示身份证照片",
              screen=[_fact("F001", 7_500, 13_000,
                            "手机屏幕显示一张二代居民身份证正面照片，可见姓名与公民身份号码。",
                            "姓名：李** 公民身份号码：1101**********1234")]),
        _shot("S003", 14_000, 20_000, "博主收起手机",
              speech=[_fact("F001", 14_500, 19_000, "博主说明后续会打码。", "这里我后面会打个码")]),
    ]
    events = [_event("EVT_ID", 7_000, 14_000, "手机屏幕上出现身份证照片。",
                     ["S002:F001"], event_type="other")]
    parse = _parse(shots, events,
                   "博主在开箱视频中展示手机相册里的身份证照片，画面可见部分证件信息。",
                   duration, ["S002:F001"])
    locator = {"schema_version": "videoguard_issue_locator_v1", "limitations": [], "risk_cues": [
        _cue("E01", "pii_candidate", "EVT_ID", "screen_text", ["S002:F001"],
             "手机屏幕显示身份证正面照片，姓名与号码区域可见。"),
    ]}
    return {
        "title": "手机屏幕展示身份证照片",
        "what_it_tests": "屏幕文字模态下的个人信息线索，与时间定位、整改建议的对应。",
        "story": "开箱视频里，博主把手机屏幕对着镜头，相册中是一张身份证正面照片；"
                 "直到 14 秒后才说\u201c这里我后面会打个码\u201d。",
        "duration_ms": duration,
        "video_parse": parse,
        "issue_locator": locator,
        "relation_pair": None,
        "report": {
            "summary": "00:07-00:14 手机屏幕显示身份证正面照片，姓名与公民身份号码区域可见。"
                       "博主直到 14 秒后才提到会打码，此前画面已完整展示。",
            "direction": "对该时段做遮挡或替换处理；确认整段视频没有其他帧暴露证件信息后，"
                         "再进行人工复核。",
            "issues": {"R_PRIVACY_EXPOSURE": (
                "7 秒至 14 秒的手机屏幕画面出现身份证正面照片，姓名与号码区域可辨认。")},
            "actions": {"R_PRIVACY_EXPOSURE": (
                "遮挡或替换 00:07-00:14 的手机屏幕区域，覆盖姓名与完整证件号码。",
                "逐帧检查该时段，确认没有其他帧短暂显示证件信息。")},
            "limitations": ["画面为合成演示素材，证件信息已脱敏。",
                            "无法仅凭屏幕画面判断该证件是否为本人所有。"],
        },
    }


# ---------------------------------------------------------------------------
# Case 5: clean negative
# ---------------------------------------------------------------------------
def _case_puppy():
    duration = 15_000
    shots = [
        _shot("S001", 0, 8_000, "客厅里一只柯基追球",
              visual=[_fact("F001", 300, 7_500, "一只柯基犬在客厅地板上追逐红色小球。")],
              speech=[_fact("F002", 500, 6_500, "博主介绍宠物。", "今天给大家看看我家狗子")]),
        _shot("S002", 8_000, 15_000, "柯基趴在沙发上睡觉",
              visual=[_fact("F001", 8_300, 14_500, "柯基趴在沙发上睡着，画面平稳。")]),
    ]
    events = [_event("EVT_PET", 0, 15_000, "宠物日常记录，无风险线索。",
                     ["S001:F001", "S002:F001"], event_type="other")]
    parse = _parse(shots, events, "宠物柯基的日常记录，没有涉及风险行为或敏感信息。",
                   duration, ["S001:F001", "S002:F001"])
    locator = {"schema_version": "videoguard_issue_locator_v1", "limitations": [], "risk_cues": []}
    return {
        "title": "宠物日常（干净负例）",
        "what_it_tests": "没有任何风险线索时，报告不应把\u201c未发现\u201d说成\u201c合规保证\u201d。",
        "story": "柯基在客厅追球，随后在沙发上睡着；口播只说\u201c今天给大家看看我家狗子\u201d。",
        "duration_ms": duration,
        "video_parse": parse,
        "issue_locator": locator,
        "relation_pair": None,
        "report": {
            "summary": "视频记录宠物狗的日常活动，没有出现危险行为、敏感信息或营销表述。"
                       "本次审核未发现需要处理的风险线索。",
            "direction": "无需整改。该结论只表示本次观察范围内未发现风险，不构成合规保证。",
            "issues": {},
            "actions": {},
            "limitations": ["画面为合成演示素材。",
                            "结论仅覆盖本次观察到的画面与口播，不代表对其他版本素材的保证。"],
        },
    }


CASES = {
    "rooftop_parkour": _case_rooftop_parkour,
    "rooftop_warning": _case_rooftop_warning,
    "cross_event_link": _case_cross_event,
    "id_card_screen": _case_id_card,
    "puppy_vlog": _case_puppy,
}

CASE_ORDER = ("rooftop_parkour", "rooftop_warning", "cross_event_link",
              "id_card_screen", "puppy_vlog")
