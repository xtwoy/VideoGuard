"""Validate an extracted source submission in its own installed environment.

Run with the extracted backend's Python after uv sync, npm ci and npm run build.
No provider calls or replacement model responses are used by these checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def verify(package: Path, frontend_port: int) -> dict:
    package = package.resolve()
    backend = package / "backend"
    manifest = json.loads((package / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        actual = hashlib.sha256((package / item["path"]).read_bytes()).hexdigest()
        assert actual == item["sha256"], item["path"]
    for name in list(os.environ):
        if name.endswith("API_KEY") or name in {"VIDEO_MODEL_BASE_URL", "AUDIT_REPORT_MODEL"}:
            os.environ.pop(name)
    assert not (backend / ".env").exists(), "Validation expects an unconfigured extraction"
    sys.path.insert(0, str(backend))
    from fastapi.testclient import TestClient
    import main

    checks = []
    with tempfile.TemporaryDirectory(prefix="videoguard-source-") as temporary:
        work = Path(temporary)
        os.environ["VIDEOGUARD_DB"] = str(work / "reviews.db")
        client = TestClient(main.app)
        response = client.get("/api/health")
        assert response.status_code == 200 and response.json()["ok"]
        assert response.json()["pead"]["solver"]["name"] == "PyArg"
        checks.append("backend health and actual PyArg solver available")
        expected = {"/api/health", "/api/reviews", "/api/reviews/{review_id}", "/api/reviews/{review_id}/report"}
        assert set(main.app.openapi()["paths"]) == expected
        assert client.get("/api/demo/cases").status_code == 404
        assert client.post("/api/demo").status_code == 404
        assert client.get("/api/reviews/missing").status_code == 404
        checks.append("only formal API routes exposed")

        clip = work / "input.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=160x90:r=10", "-t", "1", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)], check=True, capture_output=True)
        data = clip.read_bytes()
        assert main.probe_duration_ms(data, ".mp4") > 0
        def upload(content, consent="true", filename="input.mp4"):
            return client.post("/api/reviews", data={"title": "环境校验", "consent": consent}, files={"video": (filename, content, "video/mp4")})
        assert upload(data, consent="false").status_code == 400
        assert upload(b"").status_code == 400
        assert upload(data, filename="invalid.exe").status_code == 415
        assert upload(b"invalid-container").status_code == 422
        checks.append("video metadata and upload validation through real ffprobe")

        response = upload(data)
        assert response.status_code == 502, response.text
        review_id = response.json()["detail"]["review_id"]
        record = client.get(f"/api/reviews/{review_id}").json()
        assert record["mode"] == "LIVE" and record["status"] == "ERROR"
        assert record["result"]["meta"]["video_parse"] == "ERROR"
        report = client.get(f"/api/reviews/{review_id}/report")
        assert report.status_code == 200 and "text/html" in report.headers["content-type"]
        assert (work / "reviews.db").is_file()
        checks.append("missing service configuration produces persisted error and readable HTML report")

        node = shutil.which("node")
        assert node
        frontend = package / "frontend"
        command = [node, str(frontend / "node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1", "--port", str(frontend_port)]
        with (work / "frontend.log").open("wb") as log:
            server = subprocess.Popen(command, cwd=frontend, stdout=log, stderr=log)
            try:
                url = f"http://127.0.0.1:{frontend_port}"
                for _ in range(80):
                    if server.poll() is not None:
                        raise RuntimeError((work / "frontend.log").read_text(encoding="utf-8", errors="replace"))
                    try:
                        with urllib.request.urlopen(url, timeout=2) as page:
                            html = page.read().decode("utf-8")
                            assert page.status == 200 and "视频内容审核工作台" in html
                        break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.25)
                else:
                    raise RuntimeError("Frontend did not become ready")
                try:
                    urllib.request.urlopen(url + "/design-preview", timeout=5)
                    raise AssertionError("Development preview must be absent")
                except urllib.error.HTTPError as error:
                    assert error.code == 404
                checks.append("built frontend starts, home returns 200, development preview returns 404")
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)

    return {"passed": checks, "provider_api_calls": 0, "real_video_model_assessment": "not performed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--frontend-port", type=int, default=13007)
    args = parser.parse_args()
    print(json.dumps(verify(args.package, args.frontend_port), ensure_ascii=False, indent=2))
