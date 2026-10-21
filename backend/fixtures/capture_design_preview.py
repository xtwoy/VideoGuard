"""Capture UI previews and the data-derived engineering diagram.

Start `next dev --hostname 127.0.0.1 --port 3000`, then run this module.
The preview labels frozen synthetic inputs. The independent argumentation page
recomputes its engineering fixture results; no external model is called.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlencode
import uuid

ROOT = Path(__file__).resolve().parents[2]
EXPORTS = ROOT / "backend/reports/demo-showcase"
OUTPUT = ROOT / "docs/assets/demo"
WORK = ROOT / "backend/data/design-capture"
SCENE_MANIFEST = ROOT / "frontend/public/case-images/manifest.json"
CAPTIONS = {
    "01-upload.png": "正式工作台：视频上传与审核设置",
    "02-overview.png": "危险诱导：结论与处理方向",
    "03-conflict-evidence.png": "跨事件冲突：判断依据与事件证据",
    "04-revision-plan.png": "隐私暴露：处理动作与验收标准",
    "05-shot-timeline.png": "分镜：时间顺序与观察记录",
    "06-warning-contrast.png": "同一动作、劝阻口播：无诱导支持证据",
    "07-argumentation.png": "独立工程测试：结构冲突击倒模型支持候选",
    "08-html-report.png": "更新后的独立 HTML 报告",
    "09-mobile-overview.png": "390px 视口：结论概览",
    "10-mobile-audit.png": "390px 视口：问题与证据",
}


def capture(browser: Path, base: str, name: str, case: str | None, tab: str, height: int, mobile: bool = False) -> dict:
    route = "/design-preview?" + urlencode({"case": case, "tab": tab}) if case else "/"
    if name == "08-html-report.png":
        route = "/design-preview/report?" + urlencode({"case": case})
    page_url = base + route
    target = OUTPUT / name
    canvas = 520 if mobile else 1600
    harness = None
    visit = page_url
    if mobile:
        public = ROOT / "frontend/public"
        public.mkdir(exist_ok=True)
        harness = public / f"__design_capture_{uuid.uuid4().hex}.html"
        harness.write_text(
            '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#e6eef9}'
            'body{display:flex;justify-content:center;padding-top:14px}'
            'iframe{display:block;border:1px solid #cbd9ef;border-radius:12px;background:white}</style>'
            f'<iframe title="390px viewport" src="{escape(route, quote=True)}" width="390" height="{height}"></iframe>',
            encoding="utf8")
        visit = base + "/" + harness.name
    try:
        run = subprocess.run([
            str(browser), "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-crash-reporter",
            "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
            f"--user-data-dir={WORK / ('chrome-' + uuid.uuid4().hex)}",
            "--virtual-time-budget=10000", f"--window-size={canvas},{height}",
            f"--screenshot={target}", "--dump-dom", visit,
        ], capture_output=True, timeout=60)
        dom = run.stdout.decode("utf8", errors="replace")
        (WORK / f"{target.stem}.html").write_text(dom, encoding="utf8")
        (WORK / f"{target.stem}.stderr.log").write_bytes(run.stderr)
        if run.returncode or not target.is_file() or target.stat().st_size < 20_000:
            raise RuntimeError(f"Capture failed: {name}")
        if not mobile and case and "合成" not in dom:
            raise RuntimeError(f"Missing synthetic-input disclosure: {name}")
        if not case and ("合成场景" in dom or "/api/demo" in dom):
            raise RuntimeError("The formal upload page must have no demo entry")
        print(f"captured {name}", flush=True)
        result = {"file": str(target.relative_to(ROOT)).replace("\\", "/"), "url": page_url,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "viewport": [390 if mobile else 1600, height], "image_canvas": [canvas, height],
                "source": "formal_upload" if not case else "development_preview_synthetic"}
        if name == "01-upload.png":
            result["capture_state"] = "Empty formal upload form; no video selected or review submitted"
        if case and name != "08-html-report.png":
            result["scene_illustrations"] = scene_status(case)
        return result
    finally:
        if harness:
            harness.unlink(missing_ok=True)


def scene_status(case: str | None = None) -> dict:
    manifest = json.loads(SCENE_MANIFEST.read_text(encoding="utf8"))
    ids = manifest["cases"][case]["overview"] if case else list(manifest["assets"])
    assets = []
    for key in ids:
        asset = manifest["assets"][key]
        artifact = ROOT / "frontend/public" / asset["src"].lstrip("/") if asset["src"] else None
        assets.append({"id": key, "status": "provided" if artifact else "pending",
                       "src": asset["src"], "source": asset["source"],
                       "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact else None})
    return {"role": manifest["role"], "assets": assets}


def scene_summary() -> str:
    assets = scene_status()["assets"]
    provided = sum(asset["status"] == "provided" for asset in assets)
    pending = len(assets) - provided
    return f"已接入 {provided} 张场景配图" + (f"，另有 {pending} 张可选素材待补" if pending else "") + "。来源与摘要见 manifest.json。"


def write_gallery(records: dict, base: str) -> None:
    reports = "".join(
        f'<article><h2>{escape(r["video_name"].replace("合成示例｜", ""))}</h2>'
        f'<p>冻结合成输入，非真实视频识别结果</p><a href="{escape(key)}.html">查看离线报告</a>'
        f'<a class="preview" href="{base}/design-preview?case={escape(key)}">交互设计预览</a></article>'
        for key, r in records.items())
    shots = "".join(
        f'<article><a href="screenshots/{key}"><img loading="lazy" src="screenshots/{key}" alt="{escape(value)}"></a>'
        f'<h2>{escape(value)}</h2></article>' for key, value in CAPTIONS.items())
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' file:; style-src 'unsafe-inline'">
<title>视鉴 · 审核结果与界面材料</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f6fc;color:#2c466d;font:14px/1.9 'Microsoft YaHei UI','Microsoft YaHei',sans-serif}
main{max-width:1200px;margin:auto;padding:42px 28px}header{padding-bottom:26px;border-bottom:1px solid #dce7f5}.brand{font-size:22px;font-weight:700;color:#28558f}.brand span{font:12px 'Segoe UI';color:#8a9fbf;margin-left:12px}h1{font-size:28px;margin:24px 0 10px}h2{font-size:14px;font-weight:600;margin:0 0 11px}p{font-size:12px;color:#7c91af}.notice{padding:14px 17px;border:1px solid #ecdfc7;border-radius:9px;background:#fffaf0;color:#92713d;font-size:12px;margin:20px 0}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:17px}article{min-width:0;padding:20px;border:1px solid #dfe8f5;border-radius:11px;background:white}a{color:#3e76c6;font-size:12px;text-decoration:none}a:hover{text-decoration:underline}.preview{margin-left:16px;color:#7e98bb}img{display:block;width:100%;height:215px;object-fit:contain;object-position:top;background:#f5f8fd;border-radius:6px;margin-bottom:16px}@media(max-width:800px){.grid{grid-template-columns:1fr}main{padding:25px 18px}}footer{margin-top:30px;padding-top:18px;border-top:1px solid #dce7f5;font-size:12px;color:#8297b4}
</style><main><header><div class="brand">视鉴<span>VideoGuard-E</span></div><h1>审核结论、证据与处理建议</h1><p>2026-10-20 工作台更新；2026-10-21 攻防图更新 · 离线评审材料</p></header>
<div class="notice">本目录使用冻结合成样例，不代表真实视频识别效果。正式首页只提供真实视频上传；交互设计预览仅在本地开发服务中可用。独立工程攻防页与这些展示样例不是同次运行。</div>
<p>''' + escape(scene_summary()) + '''右侧场景预览与左侧整改卡使用对应配图。配图不参与合成结论生成，也不代表原视频帧。</p>
<h1>审核报告</h1><p>''' + str(len(records)) + ''' 个场景，分别保留原有判断结果与输入来源。</p><div class="grid">''' + reports + '''</div><h1>独立工程验证</h1><p><a href="pead-argumentation.html">查看 PEAD 论证攻防页面</a> · <a href="pead-argumentation.json">下载本轮论证记录</a>（工程合成输入，与上述展示场景分别运行）</p><h1>界面截图</h1><p>点击图片查看完整尺寸；移动端截图使用真实 390px iframe 视口。07 为 2026-10-21 重新求解工程样例后截取的配图视图。</p><div class="grid">''' + shots + '''</div><footer>生成记录见 manifest.json；五套展示记录与判断结果未被改写。</footer></main></html>'''
    (EXPORTS / "index.html").write_text(page, encoding="utf8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", default="http://127.0.0.1:3000")
    parser.add_argument("--browser", type=Path, default=Path("C:/Program Files/Google/Chrome/Application/chrome.exe"))
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=1,
                        help="Concurrent browser captures; default 1 keeps local preview responsive")
    parser.add_argument("--argumentation-only", action="store_true",
                        help="Only recompute and capture 07; keep the other nine screenshots")
    args = parser.parse_args()
    if not args.ui.startswith(("http://127.0.0.1:", "http://localhost:")):
        parser.error("Use a local development server")
    for directory in (WORK, OUTPUT, EXPORTS / "screenshots"):
        directory.mkdir(parents=True, exist_ok=True)
    tasks = [
        ("01-upload.png", None, "brief", 1100, False),
        ("02-overview.png", "rooftop_parkour", "brief", 1350, False),
        ("03-conflict-evidence.png", "cross_event_link", "audit", 1450, False),
        ("04-revision-plan.png", "id_card_screen", "summary", 1800, False),
        ("05-shot-timeline.png", "rooftop_parkour", "shots", 1250, False),
        ("06-warning-contrast.png", "rooftop_warning", "brief", 1350, False),
        ("08-html-report.png", "rooftop_parkour", "brief", 1500, False),
        ("09-mobile-overview.png", "rooftop_parkour", "brief", 1800, True),
        ("10-mobile-audit.png", "cross_event_link", "audit", 2000, True),
    ]
    previous = json.loads((EXPORTS / "manifest.json").read_text(encoding="utf8"))
    if args.argumentation_only:
        snapshots = [item for item in previous["screenshots"] if not item["file"].endswith("07-argumentation.png")]
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            snapshots = list(executor.map(lambda item: capture(args.browser, args.ui.rstrip("/"), *item), tasks))
    from fixtures.argumentation_capture import capture as capture_argumentation
    snapshots.append(capture_argumentation(args.browser))
    snapshots.sort(key=lambda item: item["file"])
    previous.update(scope="正式上传页未选择视频；开发预览使用冻结展示记录。" + scene_summary() + "右侧场景图与左侧整改卡按案例匹配，未重新求解这五套案例；07 独立工程样例重新执行 PEAD/PyArg 并由 Chrome 截图。未调用外部审核模型。",
                    transport="HTTP page navigation; Chrome headless CLI; no browser remote-debugging protocol",
                    captured_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), screenshots=snapshots)
    previous.pop("reference_media", None)
    previous["scene_illustrations"] = scene_status()
    for case in previous["cases"]:
        case["demo_url"] = args.ui.rstrip("/") + "/design-preview?" + urlencode({"case": case["id"]})
    (EXPORTS / "manifest.json").write_text(json.dumps(previous, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    for file in OUTPUT.glob("*.png"):
        shutil.copyfile(file, EXPORTS / "screenshots" / file.name)
    records = json.loads((EXPORTS / "records.json").read_text(encoding="utf8"))
    write_gallery(records, args.ui.rstrip("/"))
    (EXPORTS / "README.txt").write_text("视鉴审核结果与界面材料\n\n打开 index.html 查看 5 份离线报告、10 张截图及开发预览链接。\n结果样例为冻结合成输入，不代表真实视频识别；正式首页没有演示入口。\n01 展示未选择视频的正式上传页。" + scene_summary() + "\n结果页右侧场景图与左侧问题画面按案例匹配；手机图使用正常卡片比例的 v4。\n配图用于静态界面展示，不参与合成结论生成，不是原视频帧。\n07 由独立工程样例重新求解，完整论证记录见 pead-argumentation.json；不是五套展示案例的同次运行。\n交互预览需启动本地 next dev 服务；生产环境的 design-preview 页面返回 404。\n原始 records.json 未被修改；截图来源、性质与 SHA-256 见 manifest.json。\n", encoding="utf8")


if __name__ == "__main__":
    main()
