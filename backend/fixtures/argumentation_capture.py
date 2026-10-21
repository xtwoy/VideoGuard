"""Recompute the engineering report, then capture its actual browser rendering."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import threading
import uuid

from fixtures import argumentation_html as view

ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass


def capture(browser: Path, *, height: int = 1220) -> dict:
    report = view.build()
    if report["problems"]:
        raise RuntimeError("Engineering fixture checks failed: " + "; ".join(report["problems"]))
    html, data = view.render(report).encode("utf8"), view.report_json(report)
    view.REPORT.write_bytes(html)
    view.REPORT_DATA.write_bytes(data)
    exports = ROOT / "backend/reports/demo-showcase"
    for artifact in (view.REPORT, view.REPORT_DATA):
        shutil.copyfile(artifact, exports / artifact.name)
    work = ROOT / "backend/data/design-capture"
    work.mkdir(parents=True, exist_ok=True)
    target = ROOT / "docs/assets/demo/07-argumentation.png"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(view.REPORT.parent)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/pead-argumentation.html#figure"
    try:
        result = subprocess.run([
            str(browser), "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-crash-reporter",
            "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
            f"--user-data-dir={work / ('argumentation-' + uuid.uuid4().hex)}",
            "--virtual-time-budget=3000", f"--window-size=1600,{height}", f"--screenshot={target}",
            "--dump-dom", url,
        ], capture_output=True, timeout=60)
        dom = result.stdout.decode("utf8", errors="replace")
        (work / "07-argumentation.html").write_text(dom, encoding="utf8")
        (work / "07-argumentation.stderr.log").write_bytes(result.stderr)
        if result.returncode or "模型支持候选" not in dom or "合成测试输入" not in dom:
            raise RuntimeError("Argumentation capture failed; inspect backend/data/design-capture")
        if not target.is_file() or target.stat().st_size < 20_000:
            raise RuntimeError("Argumentation screenshot is missing or blank")
    finally:
        server.shutdown()
        server.server_close()
    shutil.copyfile(target, exports / "screenshots" / target.name)
    print("captured 07-argumentation.png from recomputed engineering data", flush=True)
    return {
        "file": "docs/assets/demo/07-argumentation.png", "url": url,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "viewport": [1600, height], "image_canvas": [1600, height],
        "source": "independent_engineering_fixture", "retained_historical_capture": False,
        "captured_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "artifact": "backend/reports/pead-argumentation.html",
        "artifact_sha256": hashlib.sha256(html).hexdigest(),
        "data_artifact": "backend/reports/pead-argumentation.json",
        "data_sha256": hashlib.sha256(data).hexdigest(),
        "featured_scenario": 2, "input_type": "authored_synthetic",
        "solver_executed": True, "external_model_called": False,
        "note": "Chrome captured the #figure view; loopback HTTP server existed only during capture.",
    }
