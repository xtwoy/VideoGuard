"""Curated, offline demonstrations using frozen inputs and production orchestration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pipeline import _run_models, clean_issue_locator, clean_video_parse

CASE_ROOT = Path(__file__).parent / "cases"
DEMO_CASES = (
    {"id": "danger_promotion", "title": "危险动作与鼓励模仿", "description": "展示同一事件内的支持证据、风险标注与整改建议。"},
    {"id": "warning_context", "title": "安全警示语境", "description": "展示危险画面与鼓励模仿的区别，警示不等同于诱导。"},
    {"id": "relation_wrong_encouragement", "title": "警示与模型判断冲突", "description": "模拟关系模型回答鼓励，但同一事件存在警示，查看 PEAD 如何保留冲突。"},
    {"id": "relation_override_conflict", "title": "跨事件误关联", "description": "模拟模型把不同事件的动作与话语关联，查看事件约束如何生效。"},
    {"id": "privacy_screen_text", "title": "屏幕文字隐私暴露", "description": "展示单模态证据、时间定位与隐私整改建议。"},
    {"id": "credential_claim", "title": "营销及资质声称", "description": "展示可观察线索与需外部核验的资质问题。"},
    {"id": "partial_coverage", "title": "观察不完整", "description": "展示音轨或观察缺失时的补充观察处置。"},
    {"id": "clean_negative", "title": "普通宠物日常", "description": "展示没有风险线索时的报告，不将其解释为合规保证。"},
)


def run_fixture_demo(case_id: str) -> dict:
    """Never call providers; never load arbitrary paths supplied by a client."""
    entry = next((item for item in DEMO_CASES if item["id"] == case_id), None)
    if entry is None:
        raise ValueError("未知演示场景")
    root = CASE_ROOT / case_id
    hashes = {}

    def read(name: str):
        data = (root / name).read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        return json.loads(data)

    info = read("case.json")
    parsed = clean_video_parse(read("video_parse_response.json"), info["duration_ms"])
    located = clean_issue_locator(read("issue_locator_response.json"), parsed)
    relation = read("relation_response.json") if (root / "relation_response.json").exists() else None
    report = read("audit_report_response.json")
    result = _run_models(
        located, info["duration_ms"],
        relation_fn=lambda _: relation, report_fn=lambda _: report,
        allow_relation=relation is not None, allow_report=report is not None,
    )
    result["meta"].update({
        "video_parse": "DEMO_SYNTHETIC", "issue_locator": "DEMO_SYNTHETIC",
        "demo_case": case_id, "demo_title": entry["title"], "fixture_sha256": hashes,
        "note": "上游输入为冻结合成数据；PEAD、规则求解及报告校验真实执行，未调用外部模型。",
    })
    for stage in ("relation_check", "audit_report"):
        if result["meta"][stage] == "LIVE":
            result["meta"][stage] = "DEMO_SYNTHETIC"
    return {"result": result, "duration_ms": info["duration_ms"], "title": entry["title"]}
