"""Curated, offline demonstrations using the authored showcase cases.

The showcase cases are deliberately separate from ``fixtures/cases.py``: those are
engineering fixtures (templated, adversarial, sometimes deliberately unrealistic),
while these five carry a concrete story, fact-level evidence and a stage-4 report that
passes the real validator. A demo therefore exercises the validated report path rather
than the deterministic fallback.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pipeline import _run_models, clean_issue_locator, clean_video_parse

from . import showcase

CASE_ROOT = Path(__file__).parent / "showcase"


def _entries() -> tuple[dict, ...]:
    entries = []
    for name in showcase.CASE_ORDER:
        case = showcase.CASES[name]()
        entries.append({"id": name, "title": case["title"],
                        "description": case["what_it_tests"]})
    return tuple(entries)


DEMO_CASES = _entries()


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
        "report_origin": info.get("report_origin", "authored_synthetic"),
        "note": "上游输入为按案例撰写的合成数据；PEAD、规则求解及报告校验真实执行，未调用外部模型。",
    })
    for stage in ("relation_check", "audit_report"):
        if result["meta"][stage] == "LIVE":
            result["meta"][stage] = "DEMO_SYNTHETIC"
    return {"result": result, "duration_ms": info["duration_ms"], "title": entry["title"]}
