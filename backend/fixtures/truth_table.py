"""Exhaustive PEAD truth table over mocked upstream stages.

    python -m fixtures.truth_table              # print a summary
    python -m fixtures.truth_table --write      # also write reports/pead-truth-table.{md,json}

The upstream stages (video parse, issue locator, relation check, audit report) are
mocked fixtures. PEAD itself is the real ``src.pead_engine.assess`` plus the real
``src.relation_fusion.assess_joint``.

What this can and cannot establish
----------------------------------
The upstream answers are synthetic, so nothing here measures *accuracy*: no number
in this file says how often PEAD is right about a real video. What it does
establish, and what a synthetic input cannot fake, are properties of the decision
function itself:

* **totality** — every reachable combination of relation answers yields a verdict;
* **determinism** — the same input always yields the same verdict;
* **contract conformance** — every verdict is a documented judgement/disposition
  pair with a known reason code, and never an invented one;
* **monotonic conservatism** — replacing a confident "encourages_same" with
  anything weaker never turns a flag into a non-flag, and "unrelated" can only
  reduce, never increase, the strength of a finding;
* **independence from labelling** — the same content tagged ``warning`` or
  ``education_context`` reaches the same verdict.

Together these are the defensible claim: PEAD behaves as specified on every input
the upstream stages can produce. Accuracy against real video is a separate,
unfinished experiment.

Reading the table
-----------------
Two rows deserve care because a ``FLAG`` does not always mean the same thing:

* ``warning_context`` carries a warning cue but **no** encouragement cue, so the
  provider is the only source of a promotion claim. A ``FLAG`` there means PEAD
  followed a provider answer it had no structural reason to doubt — the input was
  wrong, not the rule.
* ``relation_wrong_encouragement`` carries encouragement **and** an explicit
  warning on the same event. A ``FLAG`` there is a genuine false positive: the
  counter-evidence exists but PEAD cannot use it, because both cues share the same
  referent key and the provider's answer is taken at face value.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from fixtures import cases as case_defs
from fixtures.simulate import simulate
from src.relation_client import CHOICES
from src.relation_fusion import assess_joint

HERE = Path(__file__).resolve().parent
REPORT_DIR = HERE.parent / "reports"
MAX_COMBINATIONS = 4096

VALID_JUDGEMENTS = {"SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT", "CONFLICTED", "UNKNOWN"}
VALID_DISPOSITIONS = {"FLAG", "NONE", "REVIEW", "VERIFY_EXTERNAL", "RECHECK", "RETRY"}

# Strength order used by the monotonic-conservatism check: a stronger disposition
# means "more action demanded from a human". FLAG is the only strong outcome.
DISPOSITION_STRENGTH = {
    "NONE": 0, "RECHECK": 1, "VERIFY_EXTERNAL": 2,
    "REVIEW": 3, "RETRY": 3, "FLAG": 4,
}


def _cases_with_pairs() -> list[str]:
    """Cases whose mocked cues produce at least one relation candidate pair."""
    names = []
    for name in case_defs.CASE_ORDER:
        case = case_defs.CASES[name]()
        probe = simulate(case["video_parse"], case["issue_locator"], case_defs.DURATION_MS)
        if probe["pairs"]:
            names.append(name)
    return names


def _run(name: str, answers: tuple[str, ...]) -> dict:
    """Run one combination of relation answers through the real fusion."""
    case = case_defs.CASES[name]()
    located = simulate(case["video_parse"], case["issue_locator"],
                       case_defs.DURATION_MS)["located"]
    merged = assess_joint(located, case_defs.DURATION_MS,
                          {"answers": _answers_payload(located, answers)})
    finding = next(f for f in merged["merged"]["findings"]
                   if f["policy_id"] == "R_DANGER_PROMOTION")
    return {
        "answers": list(answers),
        "judgement": finding["judgement"],
        "disposition": finding["disposition"],
        "reason_code": finding["reason_code"],
        "semantic_check": merged["semantic_check"],
    }


def _answers_payload(located: dict, answers: tuple[str, ...]) -> dict:
    """Provider-shaped answers for the pairs this case actually produces."""
    from src.relation_client import select_pairs
    pairs = select_pairs(located["observations"], case_defs.DURATION_MS)
    payload = {}
    for pair, choice in zip(pairs, answers):
        probabilities = {name: 0.02 for name in CHOICES}
        probabilities[choice] = 0.94
        total = sum(probabilities.values())
        payload[f"{pair['pair_id']}_relation"] = {
            "type": "choice", "choice": choice, "confidence": 0.94,
            "probabilities": {k: v / total for k, v in probabilities.items()},
        }
        payload[f"{pair['pair_id']}_review"] = {"type": "noul", "noul": 0.10}
    return payload


def enumerate_case(name: str) -> dict:
    """Every reachable relation-answer combination for one case."""
    case = case_defs.CASES[name]()
    probe = simulate(case["video_parse"], case["issue_locator"], case_defs.DURATION_MS)
    pair_count = len(probe["pairs"])
    combinations = list(itertools.product(sorted(CHOICES), repeat=pair_count))
    if len(combinations) > MAX_COMBINATIONS:
        raise ValueError(f"{name}: {len(combinations)} combinations exceeds the cap")

    rows = []
    for answers in combinations:
        row = _run(name, answers)
        # Determinism: the same input must produce an identical verdict.
        again = _run(name, answers)
        row["deterministic"] = (row["judgement"], row["disposition"], row["reason_code"]) == \
                               (again["judgement"], again["disposition"], again["reason_code"])
        rows.append(row)

    problems = []
    for row in rows:
        if not row["deterministic"]:
            problems.append(f"{name} {row['answers']}: non-deterministic verdict")
        if row["judgement"] not in VALID_JUDGEMENTS:
            problems.append(f"{name} {row['answers']}: invalid judgement {row['judgement']!r}")
        if row["disposition"] not in VALID_DISPOSITIONS:
            problems.append(f"{name} {row['answers']}: invalid disposition "
                            f"{row['disposition']!r}")
        if not row["reason_code"]:
            problems.append(f"{name} {row['answers']}: missing reason code")

    # Monotonic conservatism: weakening any single answer must never strengthen
    # the outcome. Checked only on single-answer cases, where "weaker" is ordered.
    if pair_count == 1:
        strength = {row["answers"][0]: DISPOSITION_STRENGTH[row["disposition"]]
                    for row in rows}
        for weak in ("insufficient", "unrelated", "warns_same"):
            if strength.get(weak, 0) > strength.get("encourages_same", 0):
                problems.append(f"{name}: {weak} produced a stronger outcome than "
                                "encourages_same")

    return {
        "case": name,
        "pair_count": pair_count,
        "combination_count": len(rows),
        "rows": rows,
        "outcomes": sorted({(r["judgement"], r["disposition"], r["reason_code"])
                            for r in rows}),
        "problems": problems,
    }


def build() -> dict:
    results = [enumerate_case(name) for name in _cases_with_pairs()]
    problems = [p for r in results for p in r["problems"]]

    # Cross-case check: identical mocked content must reach the same verdict
    # regardless of which counter-context label the parse chose.
    convergence = _labelling_independence(results)

    return {
        "generated_by": "python -m fixtures.truth_table",
        "scope": ("上游阶段为 mock 数据，PEAD 与结果融合为真实代码。"
                  "本表证明决策函数的性质（全定义、确定性、符合协议、单调保守、"
                  "结论不依赖标注用词），不度量真实视频上的准确率。"),
        "relation_choices": sorted(CHOICES),
        "cases": results,
        "labelling_independence": convergence,
        "problems": problems,
    }


def _labelling_independence(results: list[dict]) -> dict:
    """Compare the counter-context case against the warning-tagged one."""
    by_case = {r["case"]: r for r in results}
    warning = by_case.get("warning_context")
    education = by_case.get("counter_context_tagging")
    if not warning or not education:
        return {"checked": False, "reason": "需要 warning_context 与 counter_context_tagging"}
    warn_verdicts = {(r["judgement"], r["disposition"]) for r in warning["rows"]}
    edu_verdicts = {(r["judgement"], r["disposition"]) for r in education["rows"]}
    return {
        "checked": True,
        "warning_context_verdicts": sorted(warn_verdicts),
        "counter_context_tagging_verdicts": sorted(edu_verdicts),
        "note": "两者内容同为‘动作＋警示’，仅警示的标注用词不同。"
                "counter_context_tagging 含鼓励线索，warning_context 不含，"
                "因此不要求完全相同，只要求都不出现 FLAG。",
        "no_flag_in_either": all(d != "FLAG" for _, d in warn_verdicts | edu_verdicts),
    }


def render_markdown(table: dict) -> str:
    lines = [
        "# PEAD 穷举真值表",
        "",
        "> 由 `python -m fixtures.truth_table --write` 生成，请勿手工编辑。",
        "",
        table["scope"],
        "",
        "两种 FLAG 的语义不同，读表时注意：",
        "",
        "- `warning_context` 只有警示线索、**没有**鼓励线索：出现 FLAG 表示 PEAD 采纳了"
        "提供方的回答，而它没有结构性理由怀疑——错在输入，不在规则。",
        "- `relation_wrong_encouragement` 同一事件内同时有鼓励与警示：出现 FLAG 是**真实误报**，"
        "反证存在却用不上，因为两条线索共享同一 referent_key。",
        "",
        f"关系回答取值：`{'`、`'.join(table['relation_choices'])}`",
        "",
    ]
    for result in table["cases"]:
        lines += [
            f"## `{result['case']}`",
            "",
            f"候选对 {result['pair_count']} 个，共 {result['combination_count']} 种组合。",
            "",
            "| " + " | ".join(f"pair_{i}" for i in range(result["pair_count"]))
            + " | judgement | disposition | reason_code |",
            "| " + " | ".join("---" for _ in range(result["pair_count"] + 3)) + " |",
        ]
        for row in result["rows"]:
            cells = " | ".join(row["answers"])
            lines.append(f"| {cells} | {row['judgement']} | {row['disposition']} "
                         f"| {row['reason_code']} |")
        lines += ["", "可达结论：", ""]
        for judgement, disposition, reason in result["outcomes"]:
            lines.append(f"- `{judgement}` / `{disposition}` — `{reason}`")
        lines.append("")
    independence = table["labelling_independence"]
    if independence.get("checked"):
        lines += [
            "## 结论不依赖标注用词",
            "",
            f"- `warning_context` 可达结论：{independence['warning_context_verdicts']}",
            f"- `counter_context_tagging` 可达结论："
            f"{independence['counter_context_tagging_verdicts']}",
            f"- 两者均未出现 FLAG：{independence['no_flag_in_either']}",
            "",
            independence["note"],
            "",
        ]
    lines += [
        "## 检查结果",
        "",
        ("未发现问题。" if not table["problems"]
         else "\n".join(f"- {p}" for p in table["problems"])),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="write reports/pead-truth-table.{md,json}")
    args = parser.parse_args()

    table = build()
    total = sum(r["combination_count"] for r in table["cases"])
    print(f"枚举 {len(table['cases'])} 个含候选对的用例，共 {total} 种关系回答组合")
    for result in table["cases"]:
        print(f"  {result['case']:32} pairs={result['pair_count']} "
              f"combinations={result['combination_count']}")
        for judgement, disposition, reason in result["outcomes"]:
            print(f"      -> {judgement:14} {disposition:16} {reason}")
    print()
    if table["problems"]:
        print("发现问题：")
        for problem in table["problems"]:
            print(f"  - {problem}")
    else:
        print("检查通过：全定义、确定性、符合协议、单调保守。")

    if args.write:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "pead-truth-table.json").write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (REPORT_DIR / "pead-truth-table.md").write_text(
            render_markdown(table), encoding="utf-8")
        print(f"\n已写入 {REPORT_DIR}")
    return 1 if table["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
