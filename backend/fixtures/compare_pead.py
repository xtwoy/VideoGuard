"""Same-input ablation of PEAD decision constraints, using synthetic LLM replies.

No provider is called. Both arms share parsing, protocol validation, pair
selection and confidence gates. The control arm never calls the PEAD engine.
Only R_DANGER_PROMOTION is evaluated; these are mechanism tests, not accuracy
measurements on videos. Run from backend: python -m fixtures.compare_pead --write
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import itertools
import json
from collections import Counter
from pathlib import Path

from fixtures import cases
from fixtures.truth_table import _answers_payload
from pipeline import clean_issue_locator, clean_video_parse
from src import config
from src.relation_client import CHOICES, build_request, select_pairs, semantic_gate, validate_response
from src.relation_fusion import assess_joint

POLICY = "R_DANGER_PROMOTION"
MODE = "MOCK_SYNTHETIC"
ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
# These are declared test-design expectations, not labels observed in videos.
SCENARIOS = {
    "danger_promotion": ("明确鼓励同一危险动作", "FLAG"),
    "warning_context": ("明确警示不要模仿", "NONE"),
    "unrelated_promotion": ("模型确认鼓励话语与动作无关", "NONE"),
    "unrelated_without_relation_service": ("关联未核验，保留复核", "REVIEW"),
    "news_violence": ("新闻画面未提供危险诱导线索", "NONE"),
    "relation_override_conflict": ("不同事件，模型却自信回答鼓励同一动作", "REVIEW"),
    "relation_wrong_encouragement": ("同一事件有警示，模型却自信答错", "REVIEW"),
    "counter_context_tagging": ("鼓励与教育警示的立场冲突", "REVIEW"),
    "partial_coverage": ("观察不完整，不能放行", "REVIEW"),
    "clean_negative": ("完整观察且无诱导线索", "NONE"),
}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def load_input(name: str) -> dict:
    home = ROOT / "fixtures" / "cases" / name
    relation = home / "relation_response.json"
    return {
        "duration_ms": cases.DURATION_MS,
        "video_parse": json.loads((home / "video_parse_response.json").read_text(encoding="utf-8")),
        "issue_locator": json.loads((home / "issue_locator_response.json").read_text(encoding="utf-8")),
        "relation": json.loads(relation.read_text(encoding="utf-8")) if relation.exists() else None,
    }


def simple_mapping(located: dict, duration_ms: int, relation: dict | None) -> dict:
    """Competitive control: validate, gate, and review ambiguous/mixed replies.

    It maps the SAME upstream relation replies without same-event evidence or
    counter-context constraints. Missing service, partial coverage, invalid
    replies and disagreement already require review in this control.
    """
    if located["coverage"] != "FULL":
        return {"disposition": "REVIEW", "reason": "INCOMPLETE_COVERAGE"}
    pairs = select_pairs(located["observations"], duration_ms)
    if not pairs:
        return {"disposition": "NONE", "reason": "NO_PROMOTION_PAIRS"}
    if relation is None:
        return {"disposition": "REVIEW", "reason": "RELATION_UNAVAILABLE"}
    decisions = validate_response(build_request(pairs), relation)
    stances = [semantic_gate(item) for item in decisions]
    if any(item in {"REVIEW", "insufficient"} for item in stances):
        return {"disposition": "REVIEW", "reason": "AMBIGUOUS_OR_INVALID_ANSWER"}
    positives = [item == "encourages_same" for item in stances]
    if any(positives) and not all(positives):
        return {"disposition": "REVIEW", "reason": "MIXED_RELATION_ANSWERS"}
    if all(positives):
        return {"disposition": "FLAG", "reason": "MODEL_ENCOURAGEMENT"}
    return {"disposition": "NONE", "reason": "MODEL_WARNING_OR_UNRELATED"}


def bucket(disposition: str) -> str:
    return disposition if disposition in {"FLAG", "NONE"} else "REVIEW"


def compare_input(name: str, frozen: dict, reference: str | None = None) -> dict:
    before = digest(frozen)
    parsed = clean_video_parse(copy.deepcopy(frozen["video_parse"]), frozen["duration_ms"])
    located = clean_issue_locator(copy.deepcopy(frozen["issue_locator"]), parsed)
    shared = {"located": located, "duration_ms": frozen["duration_ms"],
              "relation": frozen["relation"]}
    shared_hash = digest(shared)
    control = simple_mapping(copy.deepcopy(located), frozen["duration_ms"],
                             copy.deepcopy(frozen["relation"]))
    treatment = assess_joint(copy.deepcopy(located), frozen["duration_ms"],
                             copy.deepcopy(frozen["relation"]))
    finding = next(f for f in treatment["merged"]["findings"] if f["policy_id"] == POLICY)
    if before != digest(frozen) or shared_hash != digest(shared):
        raise AssertionError("A comparison arm modified the shared input")
    row = {
        "name": name, "mode": MODE, "input_sha256": before,
        "without_pead_input_sha256": shared_hash, "with_pead_input_sha256": shared_hash,
        "reference_action": reference,
        "without_pead": control,
        "with_pead": {"judgement": finding["judgement"],
                      "disposition": finding["disposition"], "reason": finding["reason_code"],
                      "supporting_ids": finding["supporting_ids"], "counter_ids": finding["counter_ids"]},
        "changed": bucket(control["disposition"]) != bucket(finding["disposition"]),
    }
    if reference is not None:
        row["without_pead_meets_synthetic_expectation"] = bucket(control["disposition"]) == reference
        row["with_pead_meets_synthetic_expectation"] = bucket(finding["disposition"]) == reference
    return row


def summarize(rows: list[dict]) -> dict:
    return {
        "count": len(rows), "changed": sum(row["changed"] for row in rows),
        "without_pead": dict(sorted(Counter(bucket(r["without_pead"]["disposition"]) for r in rows).items())),
        "with_pead": dict(sorted(Counter(bucket(r["with_pead"]["disposition"]) for r in rows).items())),
    }


def build() -> tuple[dict, dict]:
    inputs = {name: load_input(name) for name in SCENARIOS}
    curated = []
    enumeration = []
    for name, (description, reference) in SCENARIOS.items():
        row = compare_input(name, inputs[name], reference)
        row["scenario"] = description
        curated.append(row)
        parsed = clean_video_parse(copy.deepcopy(inputs[name]["video_parse"]), cases.DURATION_MS)
        located = clean_issue_locator(copy.deepcopy(inputs[name]["issue_locator"]), parsed)
        pairs = select_pairs(located["observations"], cases.DURATION_MS)
        if not pairs:
            continue
        for answers in itertools.product(sorted(CHOICES), repeat=len(pairs)):
            frozen = {**inputs[name], "relation": {"answers": _answers_payload(located, answers)}}
            alternate = compare_input(name, frozen)
            alternate["relation_choices"] = list(answers)
            enumeration.append(alternate)
    summary = summarize(curated)
    for arm in ("without_pead", "with_pead"):
        summary[f"{arm}_meets_synthetic_expectation"] = sum(
            row[f"{arm}_meets_synthetic_expectation"] for row in curated)
    source_files = ("fixtures/compare_pead.py", "fixtures/truth_table.py", "fixtures/cases.py",
                    "pipeline.py", "src/pead_engine.py", "src/relation_fusion.py",
                    "src/relation_client.py", "src/config.py", "config/policies_v03.json")
    report = {
        "schema_version": "videoguard_mock_pead_comparison_v1", "mode": MODE,
        "focus_policy": POLICY, "external_api_calls": 0,
        "parameters": config.describe(),
        "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_files},
        "scope": "合成结构化输入下的决策约束消融；不是视频识别准确率评估。",
        "control": "共享解析/协议校验/候选对/置信门限；简单映射含缺服务、低可信与混合回答复核。",
        "treatment": "相同输入经过现有 PEAD 引擎及关系融合；保持已有阈值。",
        "reference_note": "reference_action 是预先写明的合成场景处置预期，不是独立视频人工标注。",
        "bucket_note": "FLAG/NONE 保留；REVIEW、RECHECK、VERIFY_EXTERNAL、RETRY 统一计入复核桶，原始处置仍逐条保留。",
        "curated_summary": summary, "curated_cases": curated,
        "enumeration_summary": summarize(enumeration), "enumeration": enumeration,
        "limitations": [
            "仅比较危险行为诱导策略，不代表所有风险策略或整个应用。",
            "合成用例用于展示机制且选择并不随机，不能据此计算真实视频的准确率或泛化增益。",
            "未运行真实模型，不测视频感知、实际时间定位、API 延迟或费用。",
            "同一事件内的警示被模型高可信误答为鼓励时，当前 PEAD 仍可能 FLAG；反例保留。",
            "穷举仅覆盖当前合成用例产生的候选对及四种高可信关系回答，不覆盖所有可能输入。",
        ],
    }
    return report, {"mode": MODE, "inputs": inputs,
                    "sha256": {name: digest(value) for name, value in inputs.items()}}


def markdown(report: dict) -> str:
    summary = report["curated_summary"]
    lines = ["# PEAD Mock 同输入对照验证", "", f"**模式：{MODE}。没有调用真实 LLM，也没有分析原视频。**", "",
             report["scope"], "", "## 对照条件", "", report["control"], "", report["treatment"], "",
             report["reference_note"], "", report["bucket_note"], "", "## 场景结果", "",
             "| 场景 | 合成处置预期 | 无 PEAD | 有 PEAD | PEAD 原因 |",
             "|---|---|---|---|---|"]
    for row in report["curated_cases"]:
        lines.append(f"| {row['scenario']} | {row['reference_action']} | {row['without_pead']['disposition']} "
                     f"| {row['with_pead']['disposition']} | {row['with_pead']['reason']} |")
    lines.extend(["", f"场景数：{summary['count']}；处置桶不同：{summary['changed']}。",
                  f"符合合成处置预期：无 PEAD {summary['without_pead_meets_synthetic_expectation']}，"
                  f"有 PEAD {summary['with_pead_meets_synthetic_expectation']}。这是测试预期计数，不是视频准确率。",
                  "", "## 各组处置数量", "", "| 组别 | 强提示 FLAG | 暂无动作 NONE | 复核桶 |", "|---|---|---|---|"])
    for arm in ("without_pead", "with_pead"):
        counts = summary[arm]
        lines.append(f"| {arm} | {counts.get('FLAG', 0)} | {counts.get('NONE', 0)} | {counts.get('REVIEW', 0)} |")
    enumeration = report["enumeration_summary"]
    lines.extend(["", "## 关系回答穷举", "",
                  f"在有候选对的场景上，枚举 {enumeration['count']} 种关系回答组合；"
                  f"其中 {enumeration['changed']} 种的处置桶不同。差异数量不等于改善数量。",
                  "具体每一组答案、处置、理由和输入哈希见同名 JSON；不对替换回答后的组合计算准确率。",
                  "", "## 局限", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(["", "## 复现", "", "从 backend 运行 `python -m fixtures.compare_pead --write`。",
                  "再次运行 `python -m fixtures.compare_pead --check` 应确认输出无漂移。",
                  "输入快照保存在 mock-pead-inputs.json；两个分支共用同一输入哈希。",
                  "关系穷举回包由 fixtures.truth_table 的固定生成器产生。",
                  "输出不含时间戳或运行耗时，便于逐字节复现。", ""])
    return "\n".join(lines)


def artifacts(report: dict, inputs: dict) -> dict[str, str]:
    dump = lambda value: json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["mode", "name", "scenario", "reference_action", "without_pead", "with_pead",
                     "without_pead_reason", "with_pead_reason", "input_sha256"])
    for row in report["curated_cases"]:
        writer.writerow([MODE, row["name"], row["scenario"], row["reference_action"],
                         row["without_pead"]["disposition"], row["with_pead"]["disposition"],
                         row["without_pead"]["reason"], row["with_pead"]["reason"], row["input_sha256"]])
    return {"mock-pead-comparison.json": dump(report), "mock-pead-inputs.json": dump(inputs),
            "mock-pead-comparison.md": markdown(report), "mock-pead-comparison.csv": stream.getvalue()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--write", action="store_true", help="write reproducible reports")
    action.add_argument("--check", action="store_true", help="check committed reports for drift")
    parser.add_argument("--output-dir", type=Path, default=REPORT_DIR)
    args = parser.parse_args()
    report, inputs = build()
    outputs = artifacts(report, inputs)
    if args.write:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, value in outputs.items():
            (args.output_dir / name).write_text(value, encoding="utf-8", newline="")
    if args.check:
        stale = [name for name, value in outputs.items()
                 if not (args.output_dir / name).is_file()
                 or (args.output_dir / name).read_bytes() != value.encode("utf-8")]
        if stale:
            print("Mock report drift: " + ", ".join(stale))
            return 1
    print(markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
