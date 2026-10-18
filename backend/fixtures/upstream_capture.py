"""Capture one real upstream response so PEAD's input assumptions can be checked.

    python -m fixtures.upstream_capture --video samples/mixed.mp4 --title "演示片段"

Requires a configured ``backend/.env`` (VIDEO_MODEL_* for parsing and
ISSUE_LOCATOR_* for the locator) and ``ffprobe`` on PATH. The video is uploaded
to the provider exactly as the live pipeline does — nothing is sent anywhere else,
and no fixture data is used.

Output: ``fixtures/upstream_snapshot.json`` — the raw parse and locator responses
plus the video's hash, so the snapshot is traceable to one concrete file. The
snapshot is what ``fixtures.upstream_assumptions`` checks, and it can be re-frozen
later for a reproducible ablation run.

**Recommended clip design** (one short self-recorded video that exercises all four
assumptions at once):

1. two clearly different events, so event scoping has something to separate;
2. in one event, a risky-looking action together with a plainly encouraging or
   challenging line, so a promotion relation is possible;
3. in the other event, an explicit cautionary line ("请勿模仿" / "这样很危险"),
   so counter-context reporting can be observed;
4. your own voice only, no third-party footage, and no real personal data.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "upstream_snapshot.json"

MAX_UPLOAD_BYTES = 6_000_000
ALLOWED_SUFFIXES = {".mp4", ".mov", ".webm"}


def _require_env(names: list[str]) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "缺少环境变量：" + "、".join(missing) +
            "\n请在 backend/.env 中配置后再运行（可参考 .env.example）。"
            "\n本脚本不会用任何 mock 数据代替真实调用。")


def locator_payload(parsed: dict) -> dict:
    """The part of `clean_video_parse` output the locator actually accepts.

    `clean_video_parse` returns a wrapper whose `observation_detail` holds the
    timeline; handing the wrapper to `locate_issues` yields no events, so the
    locator returns empty cues *without calling the model*. Keeping the extraction
    in one named place makes that easy to test.
    """
    detail = parsed.get("observation_detail")
    if not isinstance(detail, dict):
        raise ValueError("清洗结果缺少 observation_detail，不能送去问题定位")
    return detail


def capture(video: Path, title: str) -> dict:
    # Imported late so --help works without the project's dependencies loaded.
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    from main import probe_duration_ms, validate_video
    from pipeline import clean_video_parse
    from src.issue_locator_client import locate_issues
    from src.model_gateway import parse_video

    _require_env(["VIDEO_MODEL_API_KEY", "VIDEO_MODEL_BASE_URL", "VIDEO_PARSE_MODEL"])
    _require_env(["ISSUE_LOCATOR_API_KEY", "ISSUE_LOCATOR_ENDPOINT"])

    contents = video.read_bytes()
    name = validate_video(video.name, contents)          # same checks as the API
    duration_ms = probe_duration_ms(contents, video.suffix.lower())
    encoded = base64.b64encode(contents).decode("ascii")
    if len(encoded) >= 10_000_000:
        raise SystemExit("视频 Base64 后超过 10MB，无法作为视频输入，请先压缩或剪短。")

    print(f"调用事实解析：{video.name}（{len(contents)} 字节，{duration_ms} ms）")
    parse_raw = parse_video("data:;base64," + encoded, duration_ms, title)
    # Run the production cleaner before the second provider call. Keeping the raw
    # reply for forensics is fine, but forwarding it would skip the boundary that
    # trims unknown fields: a stray sensitive value in `context` would otherwise be
    # sent to the locator service as-is, while the live path drops it.
    parsed = clean_video_parse(parse_raw, duration_ms)
    print("调用问题定位 …")
    locator_raw = locate_issues(locator_payload(parsed))

    return {
        "video_name": name,
        "sha256": hashlib.sha256(contents).hexdigest(),
        "duration_ms": duration_ms,
        "title": title,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parse_model": os.getenv("VIDEO_PARSE_MODEL"),
        "locator_model": os.getenv("ISSUE_LOCATOR_MODEL") or "(未配置)",
        "note": "真实模型回包快照；调用问题定位前已用 clean_video_parse 清洗。"
                "校验脚本只读取本文件，不会再次调用模型。",
        "video_parse": parse_raw,
        "parsed_sha256": hashlib.sha256(
            json.dumps(parsed["observation_detail"], sort_keys=True, ensure_ascii=False)
            .encode("utf-8")).hexdigest(),
        "issue_locator": locator_raw,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="本机合法授权视频的绝对或相对路径")
    parser.add_argument("--title", default="", help="可选视频标题，最多 100 字符")
    parser.add_argument("--out", type=Path, default=SNAPSHOT)
    args = parser.parse_args()

    video = Path(args.video).expanduser()
    if not video.is_file():
        raise SystemExit(f"找不到视频文件：{video}")
    if video.suffix.lower() not in ALLOWED_SUFFIXES:
        raise SystemExit(f"仅支持 {sorted(ALLOWED_SUFFIXES)}，收到 {video.suffix!r}")
    if video.stat().st_size > MAX_UPLOAD_BYTES:
        print(f"提示：文件 {video.stat().st_size} 字节，超过原型 6MB 上限，"
              "校验脚本仍会尝试，但真实上传接口会拒绝。", file=sys.stderr)

    snapshot = capture(video, args.title[:100])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\n已写入 {args.out}")
    print("下一步：python -m fixtures.upstream_assumptions --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
