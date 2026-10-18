"""Capture the actual production UI using HTTP and Chrome's headless CLI.

No WebSocket, CDP connection, browser automation server, or provider call.
Start the API, `next start`, and a reports HTTP server before running this module.
"""
from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import zipfile
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "assets" / "demo"
EXPORTS = ROOT / "backend" / "reports" / "demo-showcase"
WORK = ROOT / "backend" / "data" / "demo-capture"
CAPTIONS = {
    "01-upload.png": "上传与演示入口", "02-overview.png": "危险诱导：结论概览",
    "03-conflict-evidence.png": "跨事件误关联：问题与证据", "04-revision-plan.png": "隐私暴露：整改建议",
    "05-shot-timeline.png": "分镜时间线", "06-warning-contrast.png": "同一动作不同立场：警示对照",
    "07-argumentation.png": "独立工程样例：PEAD 论证攻防", "08-html-report.png": "可独立打开的 HTML 报告",
    "09-mobile-overview.png": "移动端 390px：结论概览",
    "10-mobile-audit.png": "移动端 390px：问题与证据",
}


def fetch(url: str, *, post: bool = False) -> bytes:
    if urlparse(url).scheme not in {"http", "https"}:
        raise ValueError("Only HTTP/HTTPS URLs are supported")
    with urlopen(Request(url, method="POST" if post else "GET"), timeout=30) as response:
        return response.read()


def screenshot(browser: Path, url: str, name: str, *, height: int = 1200, required: str | None,
               width: int = 1600) -> dict:
    target = OUTPUT / name
    process = subprocess.run([
        str(browser), "--headless=new", "--no-sandbox", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", "--hide-scrollbars",
        f"--user-data-dir={WORK / ('chrome-' + uuid.uuid4().hex)}",
        "--virtual-time-budget=15000",
        f"--window-size={width},{height}", f"--screenshot={target}", "--dump-dom", url,
    ], capture_output=True, timeout=60)
    dom = process.stdout.decode("utf-8", errors="replace")
    (WORK / f"{target.stem}.dom.html").write_text(dom, encoding="utf-8")
    (WORK / f"{target.stem}.stderr.log").write_bytes(process.stderr)
    if process.returncode or not target.exists():
        raise RuntimeError(f"Screenshot failed: {name}; inspect {WORK}")
    if required is not None and required not in dom:
        raise RuntimeError(f"UI was not ready for {name}: missing {required!r}; inspect {WORK}")
    content = target.read_bytes()
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError(f"Not a PNG: {name}")
    print(f"captured {name} ({len(content)} bytes)", flush=True)
    return {"file": str(target.relative_to(ROOT)).replace("\\", "/"), "url": url,
            "sha256": hashlib.sha256(content).hexdigest(), "viewport": [width, height]}


def screenshot_narrow(browser: Path, reports: str, page_url: str, name: str, *,
                      width: int, height: int, required: str) -> dict:
    """Capture a true narrow viewport.

    Chrome headless clamps ``--window-size`` to a minimum width, so a narrow window
    does not produce a narrow CSS viewport and media queries never fire. Hosting the
    page in a fixed-width iframe gives the page the iframe's width instead. The
    harness is served from the same static reports server the other captures use,
    and is removed afterwards.

    ``--dump-dom`` returns the harness document, not the iframe's, so the marker is
    checked against a size floor instead of the DOM: a blank or error page renders
    far smaller than a full result sheet.
    """
    harness = EXPORTS.parent / f"_frame-{name}.html"
    harness.write_text(
        "<!doctype html><meta charset=\"utf-8\"><style>html,body{margin:0;background:#eff1ef}"
        "iframe{border:0;display:block}</style>"
        f"<iframe src=\"{escape(page_url, quote=True)}\" width=\"{width}\" height=\"{height}\" "
        "title=\"preview\"></iframe>",
        encoding="utf-8")
    url = f"{reports}/{harness.name}"
    try:
        result = screenshot(browser, url, name, height=height + 20, width=width + 20,
                            required=None)
    finally:
        harness.unlink(missing_ok=True)
    size = (OUTPUT / name).stat().st_size
    if size < 20_000:
        raise RuntimeError(f"{name} looks blank ({size} bytes); the harness page probably did not load")
    result["note"] = f"iframe viewport (390px class); marker {required!r} not DOM-checked"
    result["viewport"] = [width, height]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", type=Path, default=Path("C:/Program Files/Google/Chrome/Application/chrome.exe"))
    parser.add_argument("--ui", default="http://127.0.0.1:5173")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--reports", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    for url in (args.ui, args.api, args.reports):
        if urlparse(url).scheme not in {"http", "https"}:
            parser.error("Only HTTP/HTTPS URLs are supported")
    if not args.browser.is_file():
        parser.error("Chrome binary not found; supply --browser")
    for directory in (OUTPUT, EXPORTS, WORK):
        directory.mkdir(parents=True, exist_ok=True)
    fetch(f"{args.api}/api/health")
    fetch(args.ui)
    catalog = json.loads(fetch(f"{args.api}/api/demo/cases"))["cases"]
    records = {}
    for case in catalog:
        record = json.loads(fetch(f"{args.api}/api/demo?{urlencode({'case': case['id']})}", post=True))
        assert record["mode"] == "DEMO"
        records[case["id"]] = record
        (EXPORTS / f"{case['id']}.html").write_bytes(fetch(f"{args.api}/api/reviews/{record['id']}/report"))
    (EXPORTS / "records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def page(case: str, tab: str = "brief") -> str:
        return f"{args.ui}/?{urlencode({'api': args.api, 'review': records[case]['id'], 'tab': tab})}"

    shots = [screenshot(args.browser, f"{args.ui}/?{urlencode({'api': args.api})}", "01-upload.png",
                        height=1000, required="提交视频审核")]
    for case, tab, name, height in (
        ("rooftop_parkour", "brief", "02-overview.png", 1250),
        ("cross_event_link", "audit", "03-conflict-evidence.png", 1250),
        ("id_card_screen", "summary", "04-revision-plan.png", 1660),
        ("rooftop_parkour", "shots", "05-shot-timeline.png", 1000),
        # 同一动作、不同立场的对照，比"观察不完整"更能说明结论来自论证
        ("rooftop_warning", "brief", "06-warning-contrast.png", 1200),
    ):
        shots.append(screenshot(args.browser, page(case, tab), name, height=height,
                                required="PEAD 证据约束与论证裁决"))
    shots.append(screenshot(args.browser, f"{args.reports}/pead-argumentation.html", "07-argumentation.png",
                            height=1220, required="RELATION_MISSING"))
    shots.append(screenshot(args.browser, f"{args.api}/api/reviews/{records['rooftop_parkour']['id']}/report",
                            "08-html-report.png", height=1500, required="合成演示，非真实视频审核"))
    shots.append(screenshot_narrow(args.browser, args.reports, page("rooftop_parkour", "brief"),
                                   "09-mobile-overview.png", width=390, height=1500, required="结论概览"))
    shots.append(screenshot_narrow(args.browser, args.reports, page("cross_event_link", "audit"),
                                   "10-mobile-audit.png", width=390, height=1600, required="问题与证据"))
    manifest = {"scope": "合成输入；真实 PEAD 执行；实际生产前端截图；没有外部模型调用。",
                "transport": "HTTP/HTTPS; Chrome headless CLI (no WebSocket)",
                "cases": [{**case, "review_id": records[case['id']]["id"], "demo_url": page(case["id"])} for case in catalog],
                "screenshots": shots}
    (EXPORTS / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_index(catalog)
    print(f"Demo pack: {EXPORTS / 'index.html'}", flush=True)
    return 0


def write_index(catalog: list[dict]) -> None:
    (EXPORTS / "screenshots").mkdir(exist_ok=True)
    for name in CAPTIONS:
        shutil.copyfile(OUTPUT / name, EXPORTS / "screenshots" / name)
    shutil.copyfile(EXPORTS.parent / "pead-argumentation.html", EXPORTS / "pead-argumentation.html")
    cards = "\n".join(f'<article><h2>{escape(case["title"])}</h2><p>{escape(case["description"])}</p>'
                      f'<a href="{case["id"]}.html">打开离线审核报告 →</a></article>' for case in catalog)
    gallery = "\n".join(f'<article><h2>{escape(title)}</h2><a href="screenshots/{name}">'
                        f'<img loading="lazy" src="screenshots/{name}" alt="{escape(title)}"></a></article>'
                        for name, title in CAPTIONS.items())
    (EXPORTS / "index.html").write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' file:; style-src 'unsafe-inline'">
<title>视鉴 · PEAD 场景演示包</title><style>
body{font:15px/1.8 'Microsoft YaHei',sans-serif;background:#f7f8fa;color:#172033;margin:0}
main{max-width:1000px;margin:50px auto;padding:24px}h1{font-size:32px}small,a{color:#4f46e5}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
article{background:white;border:1px solid #e4e7ec;border-radius:12px;padding:24px}h2{font-size:18px}
img{display:block;width:100%;height:230px;object-fit:cover;object-position:top;border:1px solid #e4e7ec}
p{color:#667085}a{font-weight:700;text-decoration:none}</style><main>
<small>VIDEOGUARD-E / PEAD DEMONSTRATION</small><h1>''' + str(len(catalog)) + ''' 个场景，看清审核依据</h1>
<p>上游为冻结合成输入，PEAD 及报告校验真实执行。以下报告可离线打开；未调用外部模型，也未分析原视频。</p>
<div class="grid">''' + cards + '</div><h1>实际页面截图</h1><p>点击缩略图查看原尺寸。'
        '<a href="pead-argumentation.html">打开完整攻防演示 →</a></p><div class="grid">'
        + gallery + '</div></main></html>\n', encoding="utf-8")
    (EXPORTS / "README.txt").write_text(
        "视鉴 VideoGuard-E 场景演示包\n\n"
        f"解压后打开 index.html。包含 {len(catalog)} 份合成场景审核报告、{len(CAPTIONS)} 张实际页面截图（含 2 张移动端）、完整攻防页面与 JSON 记录。\n"
        "离线浏览无需安装依赖；请保留 screenshots 子目录。\n"
        "输入为人工编写的合成数据，PEAD 与报告校验真实执行，未调用外部模型或分析原视频。攻防演示页使用独立工程 fixture，与五个展示视频场景不是同一次输入。\n"
        "manifest.json 中的 HTTP 审核链接需要原本地服务和数据库，离线报告不需要。\n",
        encoding="utf-8")
    with zipfile.ZipFile(EXPORTS.parent / "VideoGuard-E-demo-pack.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EXPORTS.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(EXPORTS).as_posix())


if __name__ == "__main__":
    raise SystemExit(main())
