"""Check whether a real upstream response satisfies the assumptions PEAD relies on.

    # 1. capture a real response from the pipeline (needs a configured .env)
    python -m fixtures.upstream_capture --video samples/mixed.mp4

    # 2. check the captured snapshot and write the report
    python -m fixtures.upstream_assumptions --write

PEAD's decision mechanism assumes four things about the upstream stages. The
fixture pack *satisfies* those assumptions by construction, so it cannot show
whether a real model does. This script does.

Every statement it makes is about the **upstream**, not about PEAD accuracy:

    A1  events carry a usable referent_key / event_id   (needed for SameTarget)
    A2  event ids are consistent between events and cues (needed for event scoping)
    A3  cue evidence_refs point at facts that exist      (needed for traceability)
    A4  counter-context cues are reported when present   (needed for conflict detection)

A failure here means PEAD degrades in a *known* direction — it falls back to
conservative review rather than inventing a verdict. It never means "the video is
safe". Reporting a failure is therefore useful, not embarrassing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline import clean_issue_locator, clean_video_parse

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "upstream_snapshot.json"
REPORT = HERE.parent / "reports" / "upstream-assumptions.md"

COUNTER_TAGS = {"warning", "education_context", "news_context", "fiction_context"}
PROMOTION_TAGS = {"encouragement", "challenge"}
ACTION_TAGS = {"danger_action", "danger_description"}

ACTIONABLE = {
    "A1": "referent_key 缺失时 PEAD 无法判定 SameTarget，只能转人工复核；"
          "请在事实解析提示词中要求为同一动作/事件填一致的 referent_key。",
    "A2": "事件与线索的事件标识不一致会让事件作用域错乱，"
          "可能把另一场景的警示算到本事件上。",
    "A3": "线索引用了不存在的事实，PEAD 会将其视为不可靠证据并保留人工复核；"
          "请检查提示词中的引用格式要求（S001:F001）。",
    "A4": "反向语境未被报告时，PEAD 看不到反证，会把时间接近的鼓励误判为诱导。"
          "这是最需要关注的一项：请检查提示词是否要求同时报告警示、教育、新闻、影视语境。",
}


def _facts(parsed: dict) -> set[str]:
    """Every fact reference the parse actually produced, as ``S001:F001``."""
    detail = parsed["observation_detail"]
    return {f"{shot['shot_id']}:{fact['fact_id']}"
            for shot in detail["timeline"]["shots"]
            for field in ("visual_facts", "speech_transcript", "subtitle_text",
                          "screen_text", "audio_observations")
            for fact in shot[field]}


def check(parsed: dict, located: dict) -> list[dict]:
    detail = parsed["observation_detail"]
    events = detail["timeline"]["events"]
    facts = _facts(parsed)
    cues = detail.get("risk_cues", [])
    results = []

    # --- A1: every event carries a usable event identity ---------------------
    missing = [e["event_id"] for e in events if not e.get("referent_key")]
    results.append({
        "id": "A1", "title": "事件是否都带可用的指向标识（referent_key）",
        "passed": bool(events) and not missing,
        "metrics": {"events": len(events), "without_referent_key": len(missing)},
        "detail": ("全部事件均带 referent_key。" if not missing
                   else f"缺失 referent_key 的事件：{missing}"),
    })

    # --- A2: cues and events agree on the event identity ---------------------
    known_events = {e["event_id"] for e in events}
    orphan = sorted({c["event_id"] for c in cues if c["event_id"] not in known_events})
    results.append({
        "id": "A2", "title": "线索的事件标识是否与事件列表一致",
        "passed": not orphan,
        "metrics": {"events": len(known_events), "cues": len(cues),
                    "orphan_event_ids": len(orphan)},
        "detail": ("全部线索的事件标识都能在事件列表中找到。" if not orphan
                   else f"线索引用了不存在的事件：{orphan}"),
    })

    # --- A3: cue citations resolve to real facts ----------------------------
    citations = [(c["cue_id"], ref) for c in cues for ref in c.get("evidence_refs", [])]
    dangling = sorted({ref for _, ref in citations if ref not in facts})
    results.append({
        "id": "A3", "title": "线索引用的事实是否都存在",
        "passed": not dangling,
        "metrics": {"citations": len(citations), "distinct_facts": len(facts),
                    "dangling_refs": len(dangling)},
        "detail": ("全部引用均可解析到已解析事实。" if not dangling
                   else f"无法解析的引用：{dangling}"),
    })

    # --- A4: counter-context recorded by the parse reaches the cue stage ------
    # Counter-context lives on the *event* (context.stance / counter_context_refs),
    # not on facts: facts carry no tag field. So the check compares the events the
    # parse marked as cautionary against the counter-tagged cues the locator emits.
    # A gap here means PEAD never sees the counter evidence and can mistake a
    # cautionary clip for promotion, so it is worth reporting rather than hiding.
    cautionary_stances = {"WARNING", "EDUCATION", "REPORTING", "FICTION"}
    cautionary = [e for e in events
                  if e.get("context", {}).get("stance") in cautionary_stances
                  or e.get("context", {}).get("counter_context_refs")]
    counter_cue_events = {c["event_id"] for c in cues if c["tag"] in COUNTER_TAGS}
    unreported = sorted(e["event_id"] for e in cautionary
                        if e["event_id"] not in counter_cue_events)
    results.append({
        "id": "A4", "title": "解析标记的反向语境是否也进入线索",
        "passed": not unreported,
        "metrics": {"cautionary_events": len(cautionary),
                    "events_with_counter_cue": len(counter_cue_events),
                    "counter_tags_in_cues": len({c["tag"] for c in cues} & COUNTER_TAGS),
                    "action_cues": len([c for c in cues if c["tag"] in ACTION_TAGS]),
                    "promotion_cues": len([c for c in cues if c["tag"] in PROMOTION_TAGS])},
        "detail": (("解析没有把任何事件标为警示、教育、报道或影视语境，"
                    "因此无法校验该假设；请确认测试视频确实包含明确的安全提醒。")
                   if not cautionary
                   else ("解析标记的反向语境事件均已进入线索。" if not unreported
                         else f"解析标为反向语境、但线索阶段未报告的事件：{unreported}")),
        "note": ("本项不判定视频是否存在风险——视频是否安全不在本脚本的结论范围内。"
                 "它只回答：解析说它看到了反向语境，线索阶段有没有把它带过来。"),
    })
    return results


def build() -> dict:
    if not SNAPSHOT.exists():
        raise SystemExit(
            f"缺少真实回包快照 {SNAPSHOT}。\n"
            "先运行：python -m fixtures.upstream_capture --video <本机视频路径>")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    duration = snapshot["duration_ms"]
    parsed = clean_video_parse(snapshot["video_parse"], duration)
    located = clean_issue_locator(snapshot["issue_locator"], parsed)
    results = check(parsed, located)
    return {
        "generated_by": "python -m fixtures.upstream_assumptions",
        "snapshot": {"video_name": snapshot.get("video_name"),
                     "sha256": snapshot.get("sha256"),
                     "duration_ms": duration,
                     "captured_at": snapshot.get("captured_at"),
                     "parse_model": snapshot.get("parse_model"),
                     "locator_model": snapshot.get("locator_model")},
        "scope": "本报告只校验上游是否满足 PEAD 的输入假设；"
                 "不评价 PEAD 的准确率，也不判定视频内容是否合规。",
        "coverage": {"coverage": parsed["coverage"],
                     "modalities": parsed["observation_detail"]["coverage"]["modalities"]},
        "results": results,
        "failed": [r["id"] for r in results if not r["passed"]],
    }


def render(report: dict) -> str:
    snapshot = report["snapshot"]
    lines = ["# 上游假设校验（真实模型回包）", "",
             "> 由 `python -m fixtures.upstream_assumptions --write` 生成，请勿手工编辑。",
             "", report["scope"], "",
             f"- 视频：`{snapshot['video_name']}`（{snapshot['duration_ms']} ms，"
             f"sha256 `{(snapshot['sha256'] or '')[:16]}…`）",
             f"- 事实解析模型：`{snapshot['parse_model']}`　"
             f"问题定位模型：`{snapshot['locator_model']}`",
             f"- 采集时间：{snapshot['captured_at']}",
             f"- 观察覆盖：`{report['coverage']['coverage']}`　"
             f"模态：{report['coverage']['modalities']}", "",
             "## 校验结果", "",
             "| 假设 | 结论 | 指标 |", "| --- | --- | --- |"]
    for result in report["results"]:
        lines.append(f"| {result['id']} {result['title']} "
                     f"| {'通过' if result['passed'] else '**未通过**'} "
                     f"| {result['metrics']} |")
    lines.append("")
    for result in report["results"]:
        lines += [f"### {result['id']} {result['title']}", "",
                  f"**{'通过' if result['passed'] else '未通过'}** — {result['detail']}", ""]
        if result.get("note"):
            lines += [result["note"], ""]
        if not result["passed"]:
            lines += [f"影响与处理：{ACTIONABLE[result['id']]}", ""]
    lines += ["## 说明", "",
              "PEAD 依赖以上四项假设。任一项不成立时，PEAD 会**退化为保守复核**，"
              "而不是编造结论——因此未通过项是可定位、可修复的工程问题，"
              "不会被静默地变成\"无风险\"。", "",
              "本报告不含任何准确率、误报率或召回率数字：上游为真实模型输出，"
              "但样本量为 1，且未做人工标注。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build()
    for result in report["results"]:
        mark = "PASS" if result["passed"] else "FAIL"
        print(f"  [{mark}] {result['id']} {result['title']}")
        print(f"         {result['detail']}")
        print(f"         {result['metrics']}")
    print()
    if report["failed"]:
        print(f"未通过：{report['failed']}（PEAD 会退化为保守复核，见报告中的影响说明）")
    else:
        print("四项上游假设均通过。")
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(render(report), encoding="utf-8")
        print(f"已写入 {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
