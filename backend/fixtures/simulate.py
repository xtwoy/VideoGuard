"""Offline simulation of the VideoGuard-E model chain over fixture cases.

This mirrors the orchestration in ``pipeline._run_models`` but substitutes the
three provider calls with values read from fixture files. It exists so the
fixture tooling can compute what the *real* pipeline would conclude without any
network access, and so a reviewer can see each stage's contribution.

It does not re-implement validation: every stage is routed through the real
``clean_video_parse`` / ``clean_issue_locator`` / ``validate_response`` /
``assess_joint`` / ``validate_audit_report`` functions.
"""
from __future__ import annotations

import copy
from typing import Any

from pipeline import clean_issue_locator, clean_video_parse
from src.audit_report import build_fallback_audit_report, validate_audit_report
from src.pead_engine import build_event_findings
from src.relation_client import build_request, select_pairs, validate_response
from src.relation_fusion import assess_joint


def relation_pairs(located: dict, duration_ms: int) -> list[dict]:
    """The candidate action/stance pairs the real pipeline would send."""
    return select_pairs(located["observations"], duration_ms)


def simulate(parse_raw: dict, locator_raw: dict, duration_ms: int,
             relation_raw: dict | None = None) -> dict:
    """Run the deterministic chain and return every intermediate stage.

    ``relation_raw`` is the provider-shaped relation response (or None to model
    "no relation service configured"). Validation statuses are reported exactly
    the way pipeline._run_models reports them.
    """
    parsed = clean_video_parse(parse_raw, duration_ms)
    located = clean_issue_locator(locator_raw, parsed)

    pairs = relation_pairs(located, duration_ms)
    relation_status = "NOT_NEEDED"
    decisions: list[dict] = []
    if pairs:
        if relation_raw is None:
            relation_status = "SKIPPED_NO_KEY"
        else:
            decisions = validate_response(build_request(pairs), relation_raw)
            relation_status = "LIVE"

    relation_response = relation_raw if relation_status == "LIVE" else None
    merged = assess_joint(located, duration_ms, relation_response,
                          relation_failed=False)
    findings = merged["merged"]["findings"]
    for finding in findings:
        finding["id"] = finding["policy_id"]
    event_findings = build_event_findings(located["observations"], findings, duration_ms)

    # The report stage is modelled as unavailable, so the report comes from the
    # project's own deterministic builder. That guarantees the fixture stays
    # protocol-valid and keeps the fixture independent of provider wording.
    report = None
    report_error = ""
    try:
        report = build_fallback_audit_report(located, findings, duration_ms)
    except Exception as error:  # recorded, never hidden
        report_error = f"{type(error).__name__}: {error}"

    if not pairs:
        semantic_check = merged["semantic_check"]
    elif relation_status == "SKIPPED_NO_KEY":
        semantic_check = "SKIPPED_NO_KEY"
    else:
        semantic_check = merged["semantic_check"]

    return {
        "parsed": parsed,
        "located": located,
        "pairs": pairs,
        "relation_status": relation_status,
        "relation_decisions": decisions,
        "merged": merged,
        "findings": findings,
        "event_findings": event_findings,
        "audit_report": report,
        "audit_report_error": report_error,
        "semantic_check": semantic_check,
    }


def narrative_report(state: dict, duration_ms: int, *,
                     executive_summary: str,
                     overall_direction: str,
                     dimension_summaries: dict[str, str] | None = None,
                     item_summaries: dict[str, str] | None = None,
                     limitations: list[str] | None = None) -> dict:
    """Return a protocol-valid report with case-specific narrative text.

    Starts from the deterministic builder output (so references, coverage and
    finding mapping are correct by construction), then replaces only prose
    fields. Everything is re-validated before being returned.
    """
    if state["audit_report"] is None:
        raise ValueError(f"no baseline report to derive from: {state['audit_report_error']}")
    report = copy.deepcopy(state["audit_report"])
    report.pop("_source", None)
    report["executive_summary"] = executive_summary[:1000]
    report["overall_direction"] = overall_direction[:1600]
    if limitations is not None:
        report["limitations"] = [item[:240] for item in limitations][:20]
    for key, text in (dimension_summaries or {}).items():
        if key in report["dimension_scores"]:
            report["dimension_scores"][key]["summary"] = text[:180]
    for key, text in (item_summaries or {}).items():
        for dimension in report["dimension_scores"].values():
            for item in dimension["items"]:
                if item["key"] == key:
                    item["summary"] = text[:240]
    validated = validate_audit_report(report, state["located"], state["findings"], duration_ms)
    if validated is None:
        raise ValueError("narrative report failed protocol validation")
    return validated
