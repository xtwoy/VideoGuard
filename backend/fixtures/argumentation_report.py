"""Argumentation report: how PEAD's grounded semantics actually decides.

    python -m fixtures.argumentation_report            # print a summary
    python -m fixtures.argumentation_report --write    # write reports/pead-argumentation.md

Every scenario here runs the real ``src.evidence_graph.decide`` with a real
``RuleSet`` and the real PyArg solver. The observations are fixture data, so
nothing in this report measures accuracy on real video. What it does show is the
decision *mechanism*: which arguments exist, which attacks point where, and which
grounded label each argument receives — including the cases where the model's own
answer is defeated by a structural constraint.

Scenarios are chosen to cover every grounded outcome and both attack directions:

    LOCAL_PROMOTION beaten by COUNTER_CONTEXT   bidirectional conflict -> OUT
    REFERENT_CONFLICT beating MODEL_PROMOTION   model overruled       -> OUT
    COUNTER_REFERENT_CONFLICT beating MODEL_COUNTER
                                                model overruled       -> OUT
    no attacks at all                           pure support          -> IN
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from fixtures import cases as case_defs
from pipeline import clean_issue_locator, clean_video_parse
from src.evidence_graph import decide
from src.pead_rules import load_rules

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent / "reports" / "pead-argumentation.md"
GAP_MS = 15_000


def _cross_referent_parse() -> dict:
    """Dangerous action in one event, encouragement in another.

    This is the shape a provider gets wrong: it sees the two cues close together
    and asserts they describe the same event, while the parse recorded different
    referents.
    """
    parse = copy.deepcopy(case_defs.CASES["danger_promotion"]()["video_parse"])
    parse["timeline"]["events"][0]["evidence_refs"] = ["S002:F001"]
    parse["timeline"]["events"].append({
        "event_id": "EVT_SUB", "start_ms": 12_000, "end_ms": 19_000,
        "event_type": "speech_act", "referent_key": "EVT_SUB",
        "summary": "鼓励表述指向另一件事。", "evidence_refs": ["S003:F001"],
        "context": {"stance": "ENCOURAGEMENT", "target_relation": "UNCERTAIN",
                    "counter_context_refs": []},
        "uncertainties": [],
    })
    return parse


def _cross_referent_locator() -> dict:
    locator = copy.deepcopy(case_defs.CASES["danger_promotion"]()["issue_locator"])
    locator["risk_cues"][1]["event_id"] = "EVT_SUB"
    locator["risk_cues"] = locator["risk_cues"][:2]
    return locator


def _run(parse_raw: dict, locator_raw: dict, decisions: list[tuple[str, str, str]]) -> dict:
    parsed = clean_video_parse(parse_raw, case_defs.DURATION_MS)
    located = clean_issue_locator(locator_raw, parsed)
    rows = [{"action_id": a, "stance_id": s, "stance": v, "valid": True}
            for a, s, v in decisions]
    finding, graph = decide(located["observations"], case_defs.DURATION_MS,
                            located["coverage"], GAP_MS, rows,
                            require_relation=True, ruleset=load_rules())
    return {"finding": finding, "graph": graph,
            "cue_ids": [o["id"] for o in located["observations"]]}


def scenarios() -> list[dict]:
    same_event_parse = case_defs.CASES["counter_context_tagging"]()["video_parse"]
    same_event_locator = case_defs.CASES["counter_context_tagging"]()["issue_locator"]
    danger_parse = case_defs.CASES["danger_promotion"]()["video_parse"]
    danger_locator = case_defs.CASES["danger_promotion"]()["issue_locator"]

    return [
        {"name": "同事件：「鼓励」支持论证被「反向语境」击倒",
         "why": "同一事件内既出现鼓励又出现安全提醒。两个论证互相攻击，"
                "但反向语境论证没有攻击者，因此被接受，支持论证被击倒。",
         "run": _run(same_event_parse, same_event_locator, []),
         "expect_labels": {"IN": 2, "OUT": 1}},

        {"name": "跨事件：模型断言同一事件，被结构冲突击倒",
         "why": "解析记录了两个不同事件，模型仍回答 encourages_same。"
                "REFERENT_CONFLICT 论证攻击 MODEL_PROMOTION 并将其击倒，"
                "因此不采纳模型结论。",
         "run": _run(_cross_referent_parse(), _cross_referent_locator(),
                     [("E01", "E02", "encourages_same")]),
         "expect_labels": {"IN": 1, "OUT": 1}},

        {"name": "跨事件：模型的反向论证本身被击倒",
         "why": "模型回答 warns_same，声称警示针对同一事件；"
                "但两者事件不同，COUNTER_REFERENT_CONFLICT 成立并击倒 MODEL_COUNTER。"
                "此时既无支持也无有效反证，落到保守复核。",
         "run": _run(_cross_referent_parse(), _cross_referent_locator(),
                     [("E01", "E02", "warns_same")]),
         "expect_labels": {"IN": 1, "OUT": 1}},

        {"name": "无攻击：纯支持（可正常标注关注）",
         "why": "动作与鼓励同属一个事件且无反向语境，支持论证无攻击者，"
                "因此被接受并输出关注标注。",
         "run": _run(danger_parse, danger_locator,
                     [("E01", "E02", "encourages_same"),
                      ("E01", "E03", "encourages_same")]),
         "expect_labels": {"IN": 4, "OUT": 0}},
    ]


def build() -> dict:
    results = []
    problems = []
    for scenario in scenarios():
        graph = scenario["run"]["graph"]
        counts: dict[str, int] = {}
        for argument in graph["arguments"]:
            counts[argument["label"]] = counts.get(argument["label"], 0) + 1
        expected = scenario["expect_labels"]
        if any(counts.get(label, 0) != expected.get(label, 0) for label in expected):
            problems.append(f"{scenario['name']}: 标签统计 {counts} 与期望 {expected} 不符")
        if not graph["attacks"] and expected.get("OUT", 0) > 0:
            problems.append(f"{scenario['name']}: 期望有被击倒的论证，但图中没有攻击边")
        results.append({
            "name": scenario["name"],
            "why": scenario["why"],
            "cue_ids": scenario["run"]["cue_ids"],
            "finding": scenario["run"]["finding"],
            "arguments": graph["arguments"],
            "attacks": graph["attacks"],
            "labels": counts,
            "cycles": graph["event_decisions"][0]["argument_labels"]["cycles"]
            if graph["event_decisions"] else [],
            "solver": graph["solver"],
            "ruleset": graph["ruleset"],
            "semantics": graph["semantics"],
        })
    return {"generated_by": "python -m fixtures.argumentation_report",
            "scope": "上游观察为 fixture 数据；证据图构造、规则集与 PyArg 求解为真实代码。"
                     "本报告展示决策机制，不度量真实视频上的准确率。",
            "scenarios": results, "problems": problems}


def render(report: dict) -> str:
    lines = ["# PEAD 论证攻防报告", "",
             "> 由 `python -m fixtures.argumentation_report --write` 生成，请勿手工编辑。",
             "", report["scope"], ""]
    first = report["scenarios"][0]
    lines += [f"求解器：{first['solver']['name']} {first['solver']['version']}"
              f"（{first['solver']['distribution']}）+ {first['solver']['graph_library']} "
              f"{first['solver']['graph_version']}，语义 `{first['semantics']}`，"
              f"回退策略 `fallback={first['solver']['fallback']}`。",
              f"规则集：`{first['ruleset']['id']}` v{first['ruleset']['version']}，"
              f"指纹 `{first['ruleset']['sha256'][:16]}…`。", ""]
    for index, scenario in enumerate(report["scenarios"], 1):
        lines += [f"## {index}. {scenario['name']}", "", scenario["why"], "",
                  f"线索：`{'`、`'.join(scenario['cue_ids'])}`", "",
                  "| 论证 | 极性 | 类型 | grounded 标签 | 前提 |",
                  "| --- | --- | --- | --- | --- |"]
        for argument in scenario["arguments"]:
            lines.append(
                f"| `{argument['id']}` | {argument['polarity']} | {argument['kind']} "
                f"| **{argument['label']}** | {', '.join(argument['premise_ids'])} |")
        lines.append("")
        if scenario["attacks"]:
            lines += ["攻击关系：", ""]
            for attack in scenario["attacks"]:
                lines.append(f"- `{attack['source']}` → `{attack['target']}`")
        else:
            lines.append("攻击关系：无（该事件内没有相互冲突的论证）")
        lines += ["",
                  f"裁决：**{scenario['finding']['judgement']} / "
                  f"{scenario['finding']['disposition']}** "
                  f"（`{scenario['finding']['reason_code']}`）",
                  "",
                  f"标签统计：{scenario['labels']}"
                  + (f"，存在循环 {scenario['cycles']}" if scenario["cycles"] else ""),
                  ""]
    lines += ["## 检查结果", "",
              ("未发现问题。" if not report["problems"]
               else "\n".join(f"- {p}" for p in report["problems"])), ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build()
    for scenario in report["scenarios"]:
        finding = scenario["finding"]
        print(f"  {scenario['name']}")
        print(f"      裁决 {finding['judgement']}/{finding['disposition']} "
              f"({finding['reason_code']})  标签 {scenario['labels']}  "
              f"攻击 {len(scenario['attacks'])} 条")
    print()
    if report["problems"]:
        print("发现问题：")
        for problem in report["problems"]:
            print(f"  - {problem}")
    else:
        print("检查通过：每个场景的标签与攻击符合预期。")
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(render(report), encoding="utf-8")
        print(f"\n已写入 {REPORT}")
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
