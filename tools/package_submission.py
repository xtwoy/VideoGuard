"""Export a standalone source submission without development/demo dependencies.

Run from the repository root with Python 3.11+. Development sources stay intact.
Only allowlisted runtime files and submission templates enter the ZIP.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "deliverables"
PACKAGE_NAME = "VideoGuard-E-source"
TEMPLATES = ROOT / "tools/submission"

BACKEND_FILES = (
    "main.py", "pipeline.py", "database.py", "report.py", "report_style.py",
    "pyproject.toml", "uv.lock", "requirements.txt", ".env.example",
    "config/policies_v03.json", "config/pead_rules_v1.json",
)
FRONTEND_FILES = (
    "package.json", "package-lock.json", "tsconfig.json", "next.config.ts",
    "postcss.config.mjs", ".env.example",
    "app/page.tsx", "app/layout.tsx", "app/globals.css", "app/results.css",
    "app/lib/types.ts", "app/lib/labels.ts",
    "app/components/result-tabs.tsx", "app/components/review-submission.tsx",
    "app/components/time-rail.tsx", "app/components/ui.tsx",
    "app/components/video-result-workspace.tsx",
)


def replace_once(text: str, before: str, after: str) -> str:
    count = text.count(before)
    if count != 1:
        raise ValueError(f"Export transform needs review: {before[:90]!r}, matches={count}")
    return text.replace(before, after, 1)


def remove_python_nodes(text: str, predicate) -> str:
    lines = text.splitlines(keepends=True)
    removals = []
    for node in ast.parse(text).body:
        if predicate(node):
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            removals.append((start - 1, node.end_lineno))
    for start, end in reversed(removals):
        del lines[start:end]
    return "".join(lines)


def production_main(text: str) -> str:
    text = remove_python_nodes(text, lambda node: (
        isinstance(node, ast.ImportFrom) and node.module == "fixtures.demo"
    ) or (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"demo_cases", "create_demo"}
    ))
    text = replace_once(text, "from pipeline import run_live, run_demo", "from pipeline import run_live")
    text = text.replace("5173", "3000").replace("启动静态服务", "启动前端服务")
    text = text.replace("演示版视频不能超过6MB", "视频不能超过6MB")
    return text.replace("演示版视频长度不能超过3分钟", "视频长度不能超过3分钟")


def production_pipeline(text: str) -> str:
    def unwanted(node):
        if isinstance(node, ast.Assign):
            return any(isinstance(t, ast.Name) and t.id.startswith("DEMO_") for t in node.targets)
        if isinstance(node, ast.FunctionDef):
            return node.name == "run_demo"
        if isinstance(node, ast.Import):
            return all(alias.name == "json" for alias in node.names)
        return isinstance(node, ast.ImportFrom) and node.module == "pathlib"
    return remove_python_nodes(text, unwanted).rstrip() + "\n"


def production_workspace(text: str) -> str:
    for before, after in (
        ('import { CaseSceneImage, type CaseIllustrations } from "./case-scene-image";\n', ""),
        ("  illustrations,\n", ""),
        ("  illustrations?: CaseIllustrations;\n", ""),
        ("                planImages={illustrations?.revisionPlans}\n", ""),
        ('aria-label={illustrations ? "场景画面与时间记录" : "原视频与时间定位"}', 'aria-label="原视频与时间定位"'),
        ('<h3>{illustrations ? "场景画面" : "原视频与定位"}</h3>', "<h3>原视频与定位</h3>"),
        ('''            ) : illustrations?.overview.length ? (
              <div className="vg-scene-image-list">
                {illustrations.overview.map((image) => (
                  <CaseSceneImage key={image.id} image={image} />
                ))}
              </div>
''', ""),
        ('''              {illustrations
                ? "场景配图用于界面展示，未参与审核。时间记录来自合成样例。"
                : "时间与内容来自上游观察，定位和判断均需结合原片确认。"}''',
         "              时间与内容来自上游观察，定位和判断均需结合原片确认。"),
    ):
        text = replace_once(text, before, after)
    return text


def production_tabs(text: str) -> str:
    for before, after in (
        ('import { CaseSceneImage } from "./case-scene-image";\n', ""),
        ("  planImages,\n", ""),
        ("}: { report: AuditReport | null; planImages?: Record<string, CaseSceneImage[]> } & Seek) {",
         "}: { report: AuditReport | null } & Seek) {"),
        ("                images={planImages?.[plan.id]}\n", ""),
        ("  images,\n", ""),
        ("}: { plan: AuditRevisionPlan; images?: CaseSceneImage[] } & Seek) {",
         "}: { plan: AuditRevisionPlan } & Seek) {"),
        ('''      {images?.length ? (
        <div className="vg-plan-images">
          {images.map((image) => (
            <CaseSceneImage key={image.id} image={image} placement="issue" />
          ))}
        </div>
      ) : null}
''', ""),
    ):
        text = replace_once(text, before, after)
    return text


TRANSFORMS = {
    "backend/main.py": production_main,
    "backend/pipeline.py": production_pipeline,
    "backend/database.py": lambda text: replace_once(text, "CHECK(mode IN ('LIVE','DEMO'))", "CHECK(mode = 'LIVE')"),
    "backend/report.py": lambda text: replace_once(text,
        'mode = "合成演示，非真实视频审核" if record.get("mode") == "DEMO" else "模型辅助审核"',
        'mode = "模型辅助审核"'),
    "frontend/app/lib/types.ts": lambda text: replace_once(text, 'mode: "LIVE" | "DEMO";', 'mode: "LIVE";'),
    "frontend/app/components/video-result-workspace.tsx": production_workspace,
    "frontend/app/components/result-tabs.tsx": production_tabs,
}


def source_paths() -> list[str]:
    paths = ["THIRD_PARTY.md"]
    paths += ["backend/" + name for name in BACKEND_FILES]
    paths += ["frontend/" + name for name in FRONTEND_FILES]
    paths += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "backend/src").glob("*.py"))]
    paths += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "backend/prompts").glob("*")) if p.suffix in {".md", ".json"}]
    return sorted(paths)


def validate_source(package: Path) -> None:
    forbidden = {"fixtures", "reports", "tests", "design-preview", "case-images", ".git", "node_modules", ".venv", "__pycache__", ".next"}
    needles = ("fixtures.", "/api/demo", "run_demo", '"DEMO"', "DEMO_", "DEMO_SYNTHETIC", "合成样例", "case-scene-image", "design-preview", "mock")
    for path in package.rglob("*"):
        relative = path.relative_to(package)
        if set(relative.parts) & forbidden:
            raise ValueError(f"Development/runtime artifact entered submission: {relative}")
        if not path.is_file():
            continue
        if path.name in {".env", ".env.local"} or path.suffix in {".db", ".sqlite", ".sqlite3", ".pyc", ".png", ".mp4"}:
            raise ValueError(f"Unexpected data file: {relative}")
        if path.suffix in {".py", ".ts", ".tsx"}:
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                if needle.lower() in text.lower():
                    raise ValueError(f"Development reference {needle!r} remains in {relative}")
            if path.suffix == ".py":
                compile(text, str(relative), "exec")


def build(replace: bool = False) -> Path:
    package = (OUTPUT / PACKAGE_NAME).resolve()
    archive = OUTPUT / "VideoGuard-E_源码提交包.zip"
    assert package.is_relative_to(OUTPUT.resolve()) and OUTPUT.resolve().is_relative_to(ROOT)
    if package.exists() and not replace:
        raise FileExistsError(f"Package exists: {package}; use --replace to regenerate this derived output")
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)
    for relative in source_paths():
        source = ROOT / relative
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative in TRANSFORMS:
            target.write_text(TRANSFORMS[relative](source.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(source, target)
    for name in ("README.md", "start_backend.cmd", "start_frontend.cmd", ".gitignore"):
        shutil.copyfile(TEMPLATES / name, package / name)
    validate_source(package)
    files = [{"path": p.relative_to(package).as_posix(), "size": p.stat().st_size,
              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(package.rglob("*")) if p.is_file()]
    manifest = {"name": PACKAGE_NAME, "version": "0.6.0", "file_count": len(files), "files": files}
    (package / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                bundle.write(path, (Path(PACKAGE_NAME) / path.relative_to(package)).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUTPUT / "VideoGuard-E_源码提交包.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"package": str(package), "zip": str(archive), "files": len(files) + 1,
                      "zip_bytes": archive.stat().st_size, "sha256": checksum}, ensure_ascii=False, indent=2))
    return package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace", action="store_true", help="Regenerate the derived submission directory")
    build(parser.parse_args().replace)
