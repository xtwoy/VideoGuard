"""Write the static fixture JSON files for every curated case.

    python -m fixtures.generate            # rewrite fixtures in place
    python -m fixtures.generate --check    # fail if files are out of date

Output per case (backend/fixtures/cases/<case>/):

    video_parse_response.json      raw stage-1 provider response
    issue_locator_response.json    raw stage-2 provider response
    relation_response.json         raw stage-3 provider response (if pairs exist)
    audit_report_response.json     stage-4 response, protocol-valid by construction
    expectations.json              human-owned assertions
    case.json                      title / purpose / summary of the run

``manifest.json`` indexes every case. Regenerating is deterministic: the same
case definitions always produce byte-identical files, so `--check` can be used
as a drift guard in tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fixtures import cases as case_defs
from fixtures._build import relation_response
from fixtures.simulate import simulate

HERE = Path(__file__).resolve().parent
CASE_ROOT = HERE / "cases"
MANIFEST = HERE / "manifest.json"
CHECKING = False


STALE: list[str] = []


def _dump(path: Path, payload: object) -> bytes:
    """Write pretty JSON, or record the path as stale when --check is active.

    Serialisation is deterministic, so byte comparison doubles as the drift
    guard used by tests.
    """
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    data = text.encode("utf-8")
    if CHECKING:
        if not path.exists() or path.read_bytes() != data:
            STALE.append(str(path.relative_to(HERE)))
        return data
    path.write_bytes(data)
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _finding_summary(state: dict) -> dict[str, dict[str, str]]:
    return {
        finding["policy_id"]: {
            "judgement": finding["judgement"],
            "disposition": finding["disposition"],
            "reason_code": finding["reason_code"],
            "supporting_ids": list(finding.get("supporting_ids", [])),
            "counter_ids": list(finding.get("counter_ids", [])),
        }
        for finding in state["findings"]
        if finding["disposition"] != "NONE" or finding["judgement"] != "NOT_SUPPORTED"
    }


def build_case(name: str) -> dict:
    """Materialise one case; returns its manifest entry."""
    case = case_defs.CASES[name]()
    duration = case_defs.DURATION_MS

    relation_raw = None
    if case["relation_choice"] and case["relation_choice"] != "none":
        # Pair ids are assigned by the real selection step, so ask it first.
        probe = simulate(case["video_parse"], case["issue_locator"], duration,
                         relation_raw=None)
        if not probe["pairs"]:
            raise ValueError(f"{name}: relation_choice set but no candidate pairs exist")
        choices = {pair["pair_id"]: case["relation_choice"] for pair in probe["pairs"]}
        relation_raw = relation_response(choices)

    state = simulate(case["video_parse"], case["issue_locator"], duration,
                     relation_raw=relation_raw)

    report_deriver = case.get("narrative")
    if report_deriver is not None:
        report = report_deriver(state, duration)
    else:
        report = state["audit_report"]
    if report is not None:
        report = dict(report)
        report.pop("_source", None)

    directory = CASE_ROOT / name
    directory.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}
    digests["video_parse_response.json"] = _sha256(
        _dump(directory / "video_parse_response.json", case["video_parse"]))
    digests["issue_locator_response.json"] = _sha256(
        _dump(directory / "issue_locator_response.json", case["issue_locator"]))
    if relation_raw is not None:
        digests["relation_response.json"] = _sha256(
            _dump(directory / "relation_response.json", relation_raw))
    digests["audit_report_response.json"] = _sha256(
        _dump(directory / "audit_report_response.json", report))
    digests["expectations.json"] = _sha256(
        _dump(directory / "expectations.json", case["expectations"]))
    digests["case.json"] = _sha256(_dump(directory / "case.json", {
        "name": name,
        "title": case["title"],
        "what_it_tests": case["what_it_tests"],
        "duration_ms": duration,
        "relation_choice": case["relation_choice"],
        "relation_status": state["relation_status"],
        "semantic_check": state["semantic_check"],
        "candidate_pairs": [pair["pair_id"] for pair in state["pairs"]],
    }))

    return {
        "name": name,
        "title": case["title"],
        "what_it_tests": case["what_it_tests"],
        "duration_ms": duration,
        "coverage": state["located"]["coverage"],
        "relation_status": state["relation_status"],
        "semantic_check": state["semantic_check"],
        "candidate_pair_count": len(state["pairs"]),
        "cue_count": len(state["located"]["observations"]),
        "active_findings": _finding_summary(state),
        "event_finding_count": len(state["event_findings"]),
        "audit_verdict": report["overall_verdict"] if report else None,
        "audit_score": report["overall_score"] if report else None,
        "audit_report_error": state["audit_report_error"],
        "files": digests,
    }


def build_manifest(entries: list[dict]) -> dict:
    return {
        "generated_by": "python -m fixtures.generate",
        "schema_versions": {
            "video_parse": "videoguard_video_parse_v2",
            "issue_locator": "videoguard_issue_locator_v1",
            "audit_report": "videoguard_audit_report_v1",
        },
        "duration_ms": case_defs.DURATION_MS,
        "case_order": list(case_defs.CASE_ORDER),
        "cases": entries,
    }


def _write_all() -> dict:
    CASE_ROOT.mkdir(parents=True, exist_ok=True)
    # Remove stale case directories so a renamed or deleted case cannot leave
    # misleading fixture files behind.
    expected = set(case_defs.CASE_ORDER)
    for directory in CASE_ROOT.iterdir():
        if directory.is_dir() and directory.name not in expected:
            for child in sorted(directory.rglob("*"), reverse=True):
                child.rmdir() if child.is_dir() else child.unlink()
            directory.rmdir()
    entries = [build_case(name) for name in case_defs.CASE_ORDER]
    manifest = build_manifest(entries)
    _dump(MANIFEST, manifest)
    return manifest


def stale_files() -> list[str]:
    """Recompute every fixture in memory and return the paths that differ.

    Used by the CLI ``--check`` flag and by the regression tests, so the
    checked-in JSON can never silently drift from the case definitions.
    """
    global CHECKING
    STALE.clear()
    CHECKING = True
    try:
        entries = [build_case(name) for name in case_defs.CASE_ORDER]
        manifest = build_manifest(entries)
        expected = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if not MANIFEST.exists() or MANIFEST.read_bytes() != expected:
            STALE.append("manifest.json")
        return list(STALE)
    finally:
        CHECKING = False


def _check_all() -> int:
    stale = stale_files()
    if stale:
        print("stale fixture files:")
        for item in stale:
            print(f"  {item}")
        print("run: python -m fixtures.generate")
        return 1
    print(f"all fixtures up to date ({len(case_defs.CASE_ORDER)} cases)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="verify fixtures match the case definitions")
    args = parser.parse_args()
    if args.check:
        return _check_all()
    manifest = _write_all()
    print(f"wrote {len(manifest['cases'])} cases to {CASE_ROOT}")
    for entry in manifest["cases"]:
        verdict = entry["audit_verdict"] or "(report failed)"
        score = entry["audit_score"] if entry["audit_score"] is not None else "-"
        print(f"  {entry['name']:22} verdict={verdict:16} score={str(score):>3} "
              f"pairs={entry['candidate_pair_count']} active={len(entry['active_findings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
