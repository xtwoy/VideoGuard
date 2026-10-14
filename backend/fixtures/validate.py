"""Validate every fixture case against the live pipeline and its expectations.

    python -m fixtures.validate            # assert fixtures behave as documented
    python -m fixtures.validate --matrix   # also print the policy coverage matrix

For each case this re-runs the deterministic chain (``fixtures.simulate``), which
routes the fixture JSON through the project's real validators, and then checks the
hand-written expectations. It also asserts structural invariants that hold for
every case, so a schema change cannot silently produce a plausible-looking
fixture.

Two cases currently cannot produce an audit report: ``unrelated_promotion`` and
``partial_coverage`` both make ``build_fallback_audit_report`` raise, because the
deterministic builder drops every cue when a finding has no event of its own.
The validator records that as an observed defect and fails if it ever changes,
so the fixture pack doubles as a regression pin for the bug.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fixtures import cases as case_defs
from fixtures.simulate import simulate

HERE = Path(__file__).resolve().parent
CASE_ROOT = HERE / "cases"

# Findings that the deterministic builder cannot currently turn into a report.
# See fixtures/README.md: the builder drops every cue of a finding that has no
# event of its own (src/audit_report.py, the `event_id` filter), so the report
# it builds fails its own protocol check and it raises instead of degrading.
KNOWN_REPORT_FAILURES = {
    "unrelated_promotion",
    "unrelated_without_relation_service",
    "partial_coverage",
}

VALID_JUDGEMENTS = {"SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT", "CONFLICTED", "UNKNOWN"}
VALID_DISPOSITIONS = {"FLAG", "NONE", "REVIEW", "VERIFY_EXTERNAL", "RECHECK", "RETRY"}


class CaseFailure(AssertionError):
    pass


def load(name: str, filename: str) -> dict:
    path = CASE_ROOT / name / filename
    if not path.exists():
        raise CaseFailure(f"{name}: missing fixture file {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_case(name: str) -> dict:
    """Run one case and assert its expectations. Returns metrics for the matrix."""
    expectations = load(name, "expectations.json")
    relation_path = CASE_ROOT / name / "relation_response.json"
    relation_raw = json.loads(relation_path.read_text(encoding="utf-8")) if relation_path.exists() else None

    state = simulate(load(name, "video_parse_response.json"),
                     load(name, "issue_locator_response.json"),
                     case_defs.DURATION_MS, relation_raw=relation_raw)
    located, findings = state["located"], state["findings"]

    # --- structural invariants, true for every case -------------------------
    if len(findings) != len(case_defs.ALL_POLICIES):
        raise CaseFailure(f"{name}: expected one finding per policy, got {len(findings)}")
    for finding in findings:
        if finding["judgement"] not in VALID_JUDGEMENTS:
            raise CaseFailure(f"{name}: bad judgement {finding['judgement']!r}")
        if finding["disposition"] not in VALID_DISPOSITIONS:
            raise CaseFailure(f"{name}: bad disposition {finding['disposition']!r}")
    if located["coverage"] != expectations["coverage"]:
        raise CaseFailure(f"{name}: coverage {located['coverage']} != "
                          f"expected {expectations['coverage']}")
    got_cues = [cue["id"] for cue in located["observations"]]
    if got_cues != expectations["cues"]:
        raise CaseFailure(f"{name}: cues {got_cues} != expected {expectations['cues']}")

    # --- structural invariants, true for every case -------------------------
    by_policy = {finding["policy_id"]: finding for finding in findings}
    for policy_id, (judgement, disposition) in expectations["findings"].items():
        actual = by_policy[policy_id]
        if (actual["judgement"], actual["disposition"]) != (judgement, disposition):
            raise CaseFailure(
                f"{name}: {policy_id} is "
                f"{actual['judgement']}/{actual['disposition']}, "
                f"expected {judgement}/{disposition}")
    active = sorted(finding["policy_id"] for finding in findings
                    if finding["disposition"] != "NONE")
    if active != sorted(expectations["active_finding_policies"]):
        raise CaseFailure(f"{name}: active findings {active} != "
                          f"expected {sorted(expectations['active_finding_policies'])}")
    if len(state["event_findings"]) < expectations["event_findings_at_least"]:
        raise CaseFailure(f"{name}: {len(state['event_findings'])} event findings, "
                          f"expected at least {expectations['event_findings_at_least']}")

    # --- case-specific invariants -------------------------------------------
    recheck = expectations.get("coverage_recheck_policies")
    if recheck:
        wrong = [pid for pid in recheck
                 if by_policy[pid]["disposition"] not in {"RECHECK", "REVIEW", "RETRY"}
                 or by_policy[pid]["judgement"] == "NOT_SUPPORTED"]
        if wrong:
            raise CaseFailure(f"{name}: incomplete coverage read as safe for {wrong}")

    # --- the report contract ------------------------------------------------
    report = state["audit_report"]
    if name in KNOWN_REPORT_FAILURES:
        if report is not None:
            raise CaseFailure(
                f"{name}: the deterministic report builder now succeeds. Remove it "
                "from KNOWN_REPORT_FAILURES and record the produced verdict.")
        if not state["audit_report_error"].startswith("ValueError"):
            raise CaseFailure(f"{name}: unexpected report error "
                              f"{state['audit_report_error']!r}")
    else:
        if report is None:
            raise CaseFailure(f"{name}: report builder failed: {state['audit_report_error']}")
        if report["overall_verdict"] not in {"PUBLISHABLE", "NEEDS_REVISION",
                                             "BLOCKED", "MANUAL_REVIEW"}:
            raise CaseFailure(f"{name}: bad verdict {report['overall_verdict']!r}")
        flagged = any(finding["disposition"] == "FLAG" for finding in findings)
        if flagged and report["overall_verdict"] not in {"BLOCKED", "NEEDS_REVISION"}:
            raise CaseFailure(f"{name}: FLAG present but verdict is "
                              f"{report['overall_verdict']}")

    return {
        "name": name,
        "coverage": located["coverage"],
        "relation_status": state["relation_status"],
        "pairs": len(state["pairs"]),
        "cues": len(located["observations"]),
        "event_findings": len(state["event_findings"]),
        "active": active,
        "verdict": report["overall_verdict"] if report else None,
        "report_ok": report is not None,
    }


def policy_matrix() -> dict[str, list[str]]:
    """Which case exercises each policy with a non-NONE disposition."""
    matrix: dict[str, list[str]] = {policy: [] for policy in case_defs.ALL_POLICIES}
    for name in case_defs.CASE_ORDER:
        state = simulate(load(name, "video_parse_response.json"),
                         load(name, "issue_locator_response.json"),
                         case_defs.DURATION_MS, relation_raw=None)
        for finding in state["findings"]:
            if finding["disposition"] != "NONE":
                matrix[finding["policy_id"]].append(name)
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", action="store_true",
                        help="print which case exercises each policy")
    args = parser.parse_args()

    failures: list[str] = []
    metrics: list[dict] = []
    for name in case_defs.CASE_ORDER:
        try:
            metrics.append(validate_case(name))
            print(f"  PASS  {name}")
        except CaseFailure as failure:
            failures.append(str(failure))
            print(f"  FAIL  {name}: {failure}")

    print()
    for item in metrics:
        verdict = item["verdict"] or "(report failed, pinned)"
        print(f"  {item['name']:22} coverage={item['coverage']:8} "
              f"relation={item['relation_status']:16} pairs={item['pairs']} "
              f"event_findings={item['event_findings']} verdict={verdict}")

    if args.matrix:
        print("\npolicy coverage across cases (non-NONE dispositions only):")
        for policy, names in policy_matrix().items():
            marker = " " if names else "!"
            print(f" {marker} {policy:22} {', '.join(names) if names else '(not exercised)'}")

    print()
    if failures:
        print(f"{len(failures)} case(s) failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"all {len(case_defs.CASE_ORDER)} fixture cases behave as documented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
