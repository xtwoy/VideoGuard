"""Real-HTTP smoke check against a running VideoGuard-E backend.

This is NOT a unit test and it is NOT a model-quality experiment.
It drives the actual HTTP surface (not TestClient) so that the upload path,
ffprobe dependency and failure handling are exercised for real.

Usage:
    # terminal 1
    python -m uvicorn main:app --host 127.0.0.1 --port 8000
    # terminal 2
    python tests/smoke_live.py --base http://127.0.0.1:8000

Exit code 0 means every check passed. Requires ffmpeg/ffprobe on PATH only to
build the temporary sample video; if absent, an existing file can be given via
--video instead.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

FAILURES: list[str] = []
CHECKS = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if condition:
        print(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL  {name}  {detail}")


def make_sample(directory: Path, seconds: int = 4) -> Path:
    """A tiny real MP4 with an audio track, so ffprobe has real metadata."""
    target = directory / "smoke_sample.mp4"
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=15:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(target),
    ]
    subprocess.run(command, check=True, capture_output=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--video", default="", help="use an existing video instead of generating one")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    with tempfile.TemporaryDirectory() as tmp:
        if args.video:
            sample = Path(args.video).resolve()
        else:
            try:
                sample = make_sample(Path(tmp))
            except (FileNotFoundError, subprocess.CalledProcessError) as error:
                print(f"cannot build a sample video ({error}); pass --video <file>", file=sys.stderr)
                return 2

        print(f"target : {base}")
        print(f"sample : {sample} ({sample.stat().st_size} bytes)")

        # trust_env=False keeps this local check immune to broken proxy
        # variables that some Windows shells leave in the environment.
        with httpx.Client(base_url=base, timeout=120, trust_env=False) as client:
            print("\n[1] service availability")
            try:
                health = client.get("/api/health")
            except httpx.HTTPError as error:
                print(f"  FAIL  backend unreachable: {error}", file=sys.stderr)
                return 2
            check("health returns 200", health.status_code == 200, health.text)
            check("health payload ok", health.json().get("ok") is True)

            pead_health = health.json().get("pead", {})
            check("health exposes PyArg solver", pead_health.get("solver", {}).get("name") == "PyArg")

            # Opening :8000 in a browser is a common mistake; it must explain
            # where the UI actually lives instead of returning a bare 404.
            root = client.get("/")
            check("backend root explains where the UI is",
                  root.status_code == 200 and "5173" in root.text, root.text[:120])

            print("\n[2] synthetic demo path (never a real video audit)")
            demo = client.post("/api/demo")
            check("demo returns 200", demo.status_code == 200, demo.text)
            payload = demo.json()
            result = payload.get("result", {})
            check("demo mode is DEMO", payload.get("mode") == "DEMO")
            check("ten policies evaluated", len(result.get("findings", [])) == 10)
            check("event audit records present", len(result.get("event_findings", [])) == 5)
            check(
                "video parse marked synthetic",
                result.get("meta", {}).get("video_parse") == "DEMO_SYNTHETIC",
                json.dumps(result.get("meta", {}), ensure_ascii=False),
            )
            check(
                "missing relation service is a skip, not a failure",
                result.get("meta", {}).get("relation_check") == "SKIPPED_NO_KEY",
                json.dumps(result.get("meta", {}), ensure_ascii=False),
            )

            graph = result.get("pead_audit", {})
            check("demo uses PyArg", graph.get("solver", {}).get("name") == "PyArg")
            check("demo records rule firings", bool(graph.get("rule_firings")))
            fingerprint = graph.get("ruleset", {}).get("sha256")
            check("demo and health agree on rule snapshot", bool(fingerprint) and fingerprint == pead_health.get("ruleset_sha256"))
            stored_demo = client.get(f"/api/reviews/{payload['id']}").json()
            check("stored graph preserves decision trace", stored_demo.get("result", {}).get("pead_audit") == graph)

            print("\n[3] exported HTML report")
            report = client.get(f"/api/reviews/{payload['id']}/report")
            check("report returns 200", report.status_code == 200)
            # The same endpoint feeds the in-app iframe, so it must render inline;
            # forcing attachment would leave the embedded view blank.
            check("report renders inline for the embedded view",
                  "inline" in report.headers.get("content-disposition", ""))
            check("report is self-contained html", report.headers.get("content-type", "").startswith("text/html"))
            body = report.text
            check("report states it is synthetic", "合成演示" in body)
            check("report exposes selected rules", "规则命中与冲突追踪" in body)
            check("report carries same rule fingerprint", bool(fingerprint) and fingerprint in body)
            check("report carries findings", "危险行为诱导" in body)
            check("report carries the nine-dimension scores", "维度评分" in body)
            check("report carries the revision plan", "问题定位与整改" in body)
            check("report leaks no internal stage code", "RELATION_CHECK_UNAVAILABLE" not in body)
            check("report leaks no internal policy id", "R_DANGER_PROMOTION" not in body)

            print("\n[4] upload validation (must reject before any model call)")
            no_consent = client.post(
                "/api/reviews",
                files={"video": (sample.name, sample.read_bytes(), "video/mp4")},
                data={"title": "smoke", "consent": "false"},
            )
            check("missing consent is rejected", no_consent.status_code == 400, no_consent.text)
            wrong_type = client.post(
                "/api/reviews",
                files={"video": ("bad.exe", b"MZ\x90\x00", "application/octet-stream")},
                data={"title": "smoke", "consent": "true"},
            )
            check("wrong extension is rejected", wrong_type.status_code == 415, wrong_type.text)
            empty = client.post(
                "/api/reviews",
                files={"video": ("empty.mp4", b"", "video/mp4")},
                data={"title": "smoke", "consent": "true"},
            )
            check("empty upload is rejected", empty.status_code == 400, empty.text)

            print("\n[5] real video through the live path")
            live = client.post(
                "/api/reviews",
                files={"video": (sample.name, sample.read_bytes(), "video/mp4")},
                data={"title": "smoke", "consent": "true"},
            )
            if live.status_code == 200:
                record = live.json()
                check("live upload completed", record.get("status") == "DONE", live.text)
                check("real duration was probed", record.get("duration_ms", 0) > 3000,
                      str(record.get("duration_ms")))
                check("sha256 recorded", len(record.get("sha256", "")) == 64)
                print("  NOTE  real model call succeeded; results are live model output.")
            elif live.status_code == 502:
                detail = live.json().get("detail", {})
                check("unconfigured credentials fail closed", True)
                check("failure exposes a review id", bool(detail.get("review_id")), live.text)
                saved = client.get(f"/api/reviews/{detail['review_id']}")
                check("failure is persisted", saved.status_code == 200)
                if saved.status_code == 200:
                    stored = saved.json()
                    check("failed record is marked ERROR", stored.get("status") == "ERROR")
                    check("failed run is not reported as safe",
                          stored.get("result", {}).get("coverage") == "ERROR")
                    check("failed run stores no findings",
                          stored.get("result", {}).get("findings") == [])
                    check("real duration was probed before failure",
                          stored.get("duration_ms", 0) > 3000, str(stored.get("duration_ms")))
                print("  NOTE  no usable video-model configuration: this run proves the fail-closed path only.")
            elif live.status_code == 422:
                check("ffprobe must be installed", False, live.text)
            else:
                check("live upload has a known outcome", False,
                      f"{live.status_code} {live.text[:200]}")

            print("\n[6] missing record handling")
            check("unknown id returns 404", client.get("/api/reviews/does-not-exist").status_code == 404)

    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    if FAILURES:
        print("failed: " + ", ".join(FAILURES))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
