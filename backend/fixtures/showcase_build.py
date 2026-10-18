"""Materialise the showcase cases into fixture JSON.

Two things separate these from ``fixtures/cases.py``:

* the stage-4 report is **validated**, so the demo exercises the real report path
  instead of the deterministic fallback;
* the relation answer is generated from the pairs the pipeline actually asks about,
  instead of a hand-written map that may not match.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from src.audit_report import build_fallback_audit_report, validate_audit_report
from src.relation_client import CHOICES, select_pairs_with_coverage

from . import showcase

HERE = Path(__file__).parent
ROOT = HERE / "showcase"


def _answers(pairs, targeted):
    """Answer every asked pair; only the designated one carries the interesting choice."""
    answers = {}
    for pair in pairs:
        pair_id = pair["pair_id"]
        choice = "unrelated"
        if (pair["action_id"], pair["stance_id"]) == targeted[:2]:
            choice = targeted[2]
        probabilities = {name: 0.02 for name in CHOICES}
        probabilities[choice] = 0.94
        answers[f"{pair_id}_relation"] = {"type": "choice", "choice": choice,
                                          "confidence": 0.94, "probabilities": probabilities}
        answers[f"{pair_id}_review"] = {"type": "noul", "noul": 0.05}
    return {"model": "mock-relation-showcase", "answers": answers}


def compose_report(located, findings, duration_ms, prose):
    """Take the validated report structure and replace its generic prose.

    Only free text is replaced, never evidence, verdicts, scores or plan structure, so
    the protocol guarantees of the fallback builder still hold.
    """
    report = copy.deepcopy(build_fallback_audit_report(located, findings, duration_ms))
    report["executive_summary"] = prose["summary"]
    report["overall_direction"] = prose["direction"]
    if prose.get("limitations"):
        report["limitations"] = list(prose["limitations"])
    policy_of_issue = {issue["finding_ids"][0]: issue
                       for plan in report["revision_plan"] for issue in plan["issues"]
                       if issue.get("source") == "FINDING" and issue.get("finding_ids")}
    for policy_id, description in (prose.get("issues") or {}).items():
        issue = policy_of_issue.get(policy_id)
        if issue is not None:
            issue["description"] = description
    action_of_policy = {}
    for plan in report["revision_plan"]:
        for action in plan["actions"]:
            for issue_id in action.get("related_issue_ids", []):
                for policy_id, issue in policy_of_issue.items():
                    if issue["id"] == issue_id:
                        action_of_policy[policy_id] = action
    for policy_id, (detail, acceptance) in (prose.get("actions") or {}).items():
        action = action_of_policy.get(policy_id)
        if action is not None:
            action["detail"] = detail
            action["acceptance_criteria"] = acceptance
    if validate_audit_report(report, located, findings, duration_ms) is None:
        raise RuntimeError("展示案例的报告未通过协议校验，请检查 prose 或策略输出")
    return report


def build(name: str) -> dict:
    from pipeline import _run_models, clean_issue_locator, clean_video_parse

    case = showcase.CASES[name]()
    duration = case["duration_ms"]
    parsed = clean_video_parse(copy.deepcopy(case["video_parse"]), duration)
    located = clean_issue_locator(copy.deepcopy(case["issue_locator"]), parsed)
    pairs, coverage = select_pairs_with_coverage(located["observations"], duration)
    targeted = case.get("relation_pair")
    relation = _answers(pairs, targeted) if pairs and targeted else None

    first = _run_models(located, duration, relation_fn=lambda _: relation,
                        report_fn=lambda _: {}, allow_relation=relation is not None,
                        allow_report=False)
    findings = first["findings"]
    report = compose_report(located, findings, duration, case["report"])

    second = _run_models(located, duration, relation_fn=lambda _: relation,
                         report_fn=lambda _: report,
                         allow_relation=relation is not None, allow_report=True)
    if second["meta"]["audit_report"] not in {"LIVE", "DEMO_SYNTHETIC"}:
        raise RuntimeError(f"{name}: 报告被拒绝为 {second['meta']['audit_report']}")

    files = {
        "case.json": {"name": name, "title": case["title"], "duration_ms": duration,
                      "what_it_tests": case["what_it_tests"], "story": case["story"],
                      "report_origin": "authored_synthetic",
                      # Declared expectations, checked by the demo test so a behaviour
                      # change cannot silently rewrite what the demo claims to show.
                      "expectations": {
                          "verdict": report["overall_verdict"],
                          "score": report["overall_score"],
                          "active_findings": {f["policy_id"]: [f["judgement"], f["disposition"]]
                                               for f in second["findings"] if f["disposition"] != "NONE"},
                      },
                      "note": "展示用合成数据；报告为按本案例撰写并通过协议校验的合成回包。"},
        "video_parse_response.json": case["video_parse"],
        "issue_locator_response.json": case["issue_locator"],
        "audit_report_response.json": report,
    }
    if relation is not None:
        files["relation_response.json"] = relation
    return {"files": files, "findings": second["findings"],
            "coverage": coverage, "report_status": second["meta"]["audit_report"]}


def write_all() -> list[str]:
    written = []
    for name in showcase.CASE_ORDER:
        built = build(name)
        target = ROOT / name
        target.mkdir(parents=True, exist_ok=True)
        for filename, payload in built["files"].items():
            text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            (target / filename).write_bytes(text.encode("utf-8"))
            written.append(f"{name}/{filename}")
    return written


def main() -> int:
    written = write_all()
    for name in showcase.CASE_ORDER:
        built = build(name)
        active = [f for f in built["findings"] if f["disposition"] != "NONE"]
        summary = ", ".join(f"{f['policy_id']}={f['disposition']}" for f in active) or "无风险线索"
        print(f"  {name:20} {built['report_status']:16} {summary}")
    print(f"wrote {len(written)} files under {ROOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
