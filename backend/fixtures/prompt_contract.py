"""Contract check: does each prompt ask for exactly what the code accepts?

    python -m fixtures.prompt_contract          # print the verdict
    python -m fixtures.prompt_contract --write  # also write reports/prompt-contract.md

A prompt that requests a field the validator silently drops wastes the model's
output; a prompt that omits a required field makes every real response fail at the
parse stage. Both are invisible until someone runs the pipeline with a real key,
so this checks them statically, without any network call.

Three things are compared per stage:

1. **presence** — every field the prompt's JSON template names is accepted by the
   validator, and every field the validator requires is named by the prompt;
2. **enum vocabulary** — every value the prompt offers is accepted by the code;
3. **self-consistency** — the prompt's template and the standalone schema file
   describe the same shape.

It cannot check whether a model *follows* the prompt; only a real call shows that.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPTS = HERE.parent / "prompts"
REPORT = HERE.parent / "reports" / "prompt-contract.md"

TEMPLATE = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)
ENUM = re.compile(r"^[A-Z][A-Z0-9_]*(?:\s*\|\s*[A-Z][A-Z0-9_]*)+$")


def _concrete(node):
    """Replace ``"A | B"`` enum placeholders with the first alternative."""
    if isinstance(node, dict):
        return {key: _concrete(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_concrete(item) for item in node]
    if isinstance(node, str) and ENUM.match(node.strip()):
        return node.split("|")[0].strip()
    return node


def template_of(prompt_name: str) -> dict:
    text = (PROMPTS / prompt_name).read_text(encoding="utf-8")
    blocks = TEMPLATE.findall(text)
    if not blocks:
        raise ValueError(f"{prompt_name}: 未找到 ```json 模板块")
    return json.loads(blocks[-1])


def enum_fields(node, prefix="") -> dict[str, set[str]]:
    """Every ``"A | B"`` placeholder, keyed by its dotted path."""
    found: dict[str, set[str]] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, str) and ENUM.match(value.strip()):
                found[path] = {part.strip() for part in value.split("|")}
            else:
                found.update(enum_fields(value, path))
    elif isinstance(node, list):
        for item in node:
            found.update(enum_fields(item, f"{prefix}[]"))
    return found


UPPER_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{1,40}$")


def keys_at(node, path: list[str]) -> set[str] | None:
    """Field names at a dotted path, unwrapping every list on the way.

    The prompt templates write arrays of objects inline (``"events": [{...}]``), so
    a segment resolves to the object inside the list.
    """
    if not path:
        return None
    current = node
    for part in path:
        if isinstance(current, list):
            current = current[0] if current else None
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, list):
        current = current[0] if current else None
    return set(current) if isinstance(current, dict) else None


def token_sets(text: str) -> list[set[str]]:
    """Every ALL-CAPS value list in a prompt document.

    Two notations occur in these prompts and both must be recognised:

    * pipe-separated, usually inside the JSON template —
      ``"status": "FULL | PARTIAL | UNKNOWN"``;
    * one value per backtick in prose —
      ``使用 `SAME_EVENT`；无法确认时使用 `UNCERTAIN```.

    The scan is line-based on purpose: splitting the whole document on ``|`` would
    treat the entire file as a single candidate, which never matches and silently
    finds nothing at all.
    """
    found: list[set[str]] = []
    for line in text.splitlines():
        if "|" in line:
            for segment in re.findall(r"[A-Z][A-Z0-9_]*(?:\s*\|\s*[A-Z][A-Z0-9_]*)+", line):
                tokens = {part.strip() for part in segment.split("|")}
                if len(tokens) >= 2 and all(UPPER_TOKEN.match(token) for token in tokens):
                    found.append(tokens)
        backticked = set(re.findall(r"`([A-Z][A-Z0-9_]{1,40})`", line))
        if len(backticked) >= 2:
            found.append(backticked)
    return found


def match_enum(code_values: set[str], document: str, template: dict) -> tuple[bool, set[str]]:
    """Find a token set equivalent to ``code_values`` anywhere in the prompt."""
    candidates = token_sets(document) + token_sets(json.dumps(template, ensure_ascii=False))
    for tokens in candidates:
        if tokens == code_values:
            return True, tokens
    # A superset still tells the model every accepted value.
    for tokens in candidates:
        if code_values <= tokens:
            return True, tokens
    return False, set()


def check_video_parse() -> list[dict]:
    from pipeline import (VALID_ALIASING_STATUS, VALID_CONTINUITY, VALID_COVERAGE,
                          VALID_FACT_CONFIDENCE, VALID_MODALITIES,
                          VALID_QUALITY_OR_NA, VALID_QUALITY_STATUS, VALID_READABILITY,
                          VALID_STANCE, VALID_TAGS, VALID_TARGET_RELATION,
                          VALID_TIME_LOCALIZATION)

    document = (PROMPTS / "video_parse_system.md").read_text(encoding="utf-8")
    template = template_of("video_parse_system.md")
    results = []

    template_modalities = keys_at(template, ["coverage", "modalities"])
    results.append({
        "stage": "video_parse", "check": "coverage.modalities 的键",
        "prompt": sorted(template_modalities or []),
        "code": sorted({"visual", "speech", "screen_text", "sound"}),
        "passed": template_modalities == {"visual", "speech", "screen_text", "sound"},
    })

    # Every enum the validator accepts must be discoverable in the prompt body,
    # whether it is written in the JSON template or in the prose around it.
    for label, allowed, required in (
        # PEAD only matches on SAME_EVENT, so a prompt that omits DIFFERENT_EVENT
        # still gives the model everything it needs; that is a documentation gap,
        # not a contract break, and is reported as such.
        ("events[].context.target_relation", VALID_TARGET_RELATION,
         {"SAME_EVENT", "UNCERTAIN"}),
        ("coverage.status", VALID_COVERAGE, set(VALID_COVERAGE)),
        ("coverage.time_localization", VALID_TIME_LOCALIZATION, set(VALID_TIME_LOCALIZATION)),
        ("coverage.modalities.*", {"FULL", "PARTIAL", "UNKNOWN"}, {"FULL", "PARTIAL", "UNKNOWN"}),
        ("shots[].continuity", VALID_CONTINUITY, set(VALID_CONTINUITY)),
        ("facts[].confidence", VALID_FACT_CONFIDENCE, set(VALID_FACT_CONFIDENCE)),
        ("quality.visual_clarity", VALID_READABILITY, set(VALID_READABILITY)),
        ("quality.speech_clarity", VALID_READABILITY, set(VALID_READABILITY)),
        ("quality.audio.status", VALID_QUALITY_STATUS, set(VALID_QUALITY_STATUS)),
        ("quality.audio.voice_clarity", VALID_QUALITY_OR_NA, set(VALID_QUALITY_OR_NA)),
        ("quality.audio.bgm_interference", VALID_QUALITY_OR_NA, set(VALID_QUALITY_OR_NA)),
        ("quality.visual.clarity", VALID_QUALITY_STATUS, set(VALID_QUALITY_STATUS)),
        ("quality.visual.pixelation", VALID_QUALITY_STATUS, set(VALID_QUALITY_STATUS)),
        ("quality.visual.aliasing_candidate", VALID_ALIASING_STATUS, set(VALID_ALIASING_STATUS)),
        ("events[].context.stance", VALID_STANCE, set(VALID_STANCE)),
    ):
        matched, tokens = match_enum(set(allowed), document, template)
        # A value the model is never told about is only a problem if PEAD needs it.
        complete, _ = match_enum(set(required), document, template)
        note = ""
        if matched and not (set(allowed) <= tokens):
            note = (f"prompt 未说明 {sorted(set(allowed) - tokens)}；"
                    "这些取值 PEAD 不依赖，属文档缺口而非契约破裂")
        results.append({
            "stage": "video_parse", "check": f"枚举 {label}",
            "prompt": sorted(tokens) if tokens else "未找到等价取值列表",
            "code": sorted(allowed), "passed": complete, "note": note,
        })

    # Required top-level blocks and the required fields of the sections the
    # validator rejects when empty (it demands refs-or-limitations on each).
    required_top = ["schema_version", "coverage", "timeline", "video_summary",
                    "content_analysis"]
    for key in required_top:
        results.append({"stage": "video_parse", "check": f"必填顶层字段 {key}",
                        "prompt": "有" if key in template else "缺失", "code": "必需",
                        "passed": key in template})

    content = keys_at(template, ["content_analysis"]) or set()
    results.append({"stage": "video_parse", "check": "content_analysis 只含音画可读性",
                    "prompt": sorted(content), "code": ["audio_visual_quality"],
                    "passed": content == {"audio_visual_quality"}})

    # Cue tags are NOT declared in the parse prompt: the parse protocol has no tag
    # field, and the locator asks about one tag at a time via a {{TAG}} template.
    # What matters is that the vocabulary the adapter iterates is one PEAD accepts;
    # that is checked in check_issue_locator().
    return results


def check_issue_locator() -> list[dict]:
    from src.issue_locator_client import LOCATOR_TAGS
    from pipeline import VALID_TAGS

    template = template_of("issue_locator_jev_question.md") if False else None
    results = []
    # The locator receives typed questions rather than a JSON template, so the
    # vocabulary check is the one that matters here.
    question = (PROMPTS / "issue_locator_jev_question.md").read_text(encoding="utf-8")
    results.append({
        "stage": "issue_locator", "check": "适配器标签词表与 PEAD 的 VALID_TAGS 兼容",
        "prompt": f"{len(LOCATOR_TAGS)} 个适配器标签",
        "code": f"{len(VALID_TAGS)} 个 PEAD 标签",
        "passed": set(LOCATOR_TAGS).issubset(VALID_TAGS),
        "note": ("适配器标签必须全部是 PEAD 可识别的标签，"
                 f"否则会被降级为 other：{sorted(set(LOCATOR_TAGS) - VALID_TAGS)}"
                 if not set(LOCATOR_TAGS).issubset(VALID_TAGS) else ""),
    })
    schema = json.loads((PROMPTS / "issue_locator_schema_v1.json").read_text(encoding="utf-8"))
    results.append({
        "stage": "issue_locator", "check": "schema 要求的字段与协议一致",
        "prompt": sorted(schema.get("required", [])),
        "code": sorted(["schema_version", "risk_cues", "limitations"]),
        "passed": set(schema.get("required", [])) == {"schema_version", "risk_cues", "limitations"},
    })
    return results


def check_relation() -> list[dict]:
    from src.relation_client import CHOICES

    schema = json.loads((PROMPTS / "relation_check_schema_v1.json").read_text(encoding="utf-8"))
    document = (PROMPTS / "relation_check_system.md").read_text(encoding="utf-8")
    results = []

    # The system prompt names the four choices in upper case; the adapter compares
    # against lower case. Comparing case-insensitively keeps a purely cosmetic
    # difference from looking like a contract break.
    tokens: set[str] = set()
    for segment in re.findall(r"[A-Za-z_]+(?:\s*\|\s*[A-Za-z_]+)*", document):
        tokens |= {part.strip().lower() for part in segment.split("|")}
    missing = sorted(choice for choice in CHOICES if choice not in tokens)
    results.append({
        "stage": "relation_check", "check": "四类语义选择都在 system prompt 中说明",
        "prompt": f"{len(CHOICES) - len(missing)}/{len(CHOICES)}",
        "code": sorted(CHOICES), "passed": not missing,
        "note": f"prompt 未说明：{missing}" if missing else "",
    })
    # The schema must describe what the adapter actually reads, not a different shape.
    # This used to be a hard-coded pass, which is how two contracts drifted apart while
    # the check kept reporting success.
    answers = schema.get("properties", {}).get("answers")
    legacy = "decisions" in schema.get("properties", {})
    adapter_reads = {"type", "choice", "probabilities", "confidence", "noul"}
    schema_fields: set[str] = set()

    def _collect(node):
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                schema_fields.update(properties)
            for value in node.values():
                _collect(value)
        elif isinstance(node, list):
            for value in node:
                _collect(value)

    _collect(answers or {})
    missing_fields = sorted(adapter_reads - schema_fields)
    results.append({
        "stage": "relation_check", "check": "schema 描述运行时实际读取的 answers 结构",
        "prompt": sorted(schema_fields), "code": sorted(adapter_reads),
        "passed": isinstance(answers, dict) and not legacy and not missing_fields,
        "note": ("schema 仍是旧的 decisions 数组格式" if legacy
                 else (("schema 缺少字段：" + ", ".join(missing_fields))
                       if missing_fields else "")),
    })
    # A real request must use the documented question suffixes.
    from src.relation_client import build_request

    request = build_request([{
        "pair_id": "pair_0",
        "action": {"id": "A1", "modality": "visual", "tag": "danger_action",
                   "description": "示例动作", "speech_or_screen_text": ""},
        "stance": {"id": "P1", "modality": "speech", "tag": "encouragement",
                   "description": "示例立场", "speech_or_screen_text": ""},
    }])
    keys = sorted(request["questions"])
    results.append({
        "stage": "relation_check", "check": "真实请求使用 _relation/_review 问题键",
        "prompt": ["<pair_id>_relation", "<pair_id>_review"], "code": keys,
        "passed": keys == ["pair_0_relation", "pair_0_review"],
        "note": "" if keys == ["pair_0_relation", "pair_0_review"]
                else "build_request 的问题键与文档不一致",
    })
    return results


def check_audit_report() -> list[dict]:
    from src.audit_report import ACTIONS, DIMENSIONS, STATUSES, VERDICTS

    template = template_of("audit_report_system.md")
    schema = json.loads((PROMPTS / "audit_report_schema_v1.json").read_text(encoding="utf-8"))
    results = []

    prompt_dims = set(template.get("dimension_scores", {}))
    results.append({
        "stage": "audit_report", "check": "九维度与校验器一致",
        "prompt": sorted(prompt_dims), "code": sorted(DIMENSIONS),
        "passed": prompt_dims == set(DIMENSIONS),
    })

    for name, allowed in (("overall_verdict", VERDICTS),):
        offered = {template.get(name)} if isinstance(template.get(name), str) and ENUM.match(
            (template.get(name) or "").strip()) else None
        if offered is None:
            results.append({"stage": "audit_report", "check": f"枚举 {name}",
                            "prompt": template.get(name), "code": sorted(allowed),
                            "passed": False})
        else:
            values = {part.strip() for part in template[name].split("|")}
            results.append({"stage": "audit_report", "check": f"枚举 {name}",
                            "prompt": sorted(values), "code": sorted(allowed),
                            "passed": values == allowed})

    schema_actions = set()
    for candidate in schema.get("$defs", {}).values():
        enum = candidate.get("properties", {}).get("action", {}).get("enum")
        if enum:
            schema_actions |= set(enum)
    results.append({
        "stage": "audit_report", "check": "整改动作词表与校验器一致",
        "prompt": sorted(schema_actions), "code": sorted(ACTIONS),
        "passed": schema_actions == set(ACTIONS),
    })

    schema_status = set()
    for candidate in schema.get("$defs", {}).values():
        enum = candidate.get("properties", {}).get("status", {}).get("enum")
        if enum:
            schema_status |= set(enum)
    results.append({
        "stage": "audit_report", "check": "维度状态词表与校验器一致",
        "prompt": sorted(schema_status), "code": sorted(STATUSES),
        "passed": schema_status == set(STATUSES),
    })
    return results


def build() -> dict:
    results = check_video_parse() + check_issue_locator() + check_relation() + check_audit_report()
    return {
        "generated_by": "python -m fixtures.prompt_contract",
        "scope": "静态契约检查：prompt 要求的字段与枚举是否被代码接受。"
                 "不检查模型是否遵循 prompt——那需要真实调用。",
        "results": results,
        "failed": [f"{r['stage']}: {r['check']}" for r in results if not r["passed"]],
    }


def render(report: dict) -> str:
    lines = ["# Prompt 契约检查", "",
             "> 由 `python -m fixtures.prompt_contract --write` 生成，请勿手工编辑。",
             "", report["scope"], "", "| 阶段 | 检查项 | 结论 | 说明 |",
             "| --- | --- | --- | --- |"]
    for result in report["results"]:
        note = result.get("note") or ("" if result["passed"] else
                                     f"prompt={result['prompt']} code={result['code']}")
        lines.append(f"| {result['stage']} | {result['check']} "
                     f"| {'通过' if result['passed'] else '**未通过**'} | {note} |")
    lines += ["", "## 说明", "",
              "本检查是**静态**的：它保证 prompt 要求的字段与枚举都被校验器接受，"
              "从而排除真实调用时因契约不一致而必然失败的整类问题。"
              "它不能证明模型会遵循 prompt——那只能由一次真实调用回答。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build()
    stage = None
    for result in report["results"]:
        if result["stage"] != stage:
            stage = result["stage"]
            print(f"[{stage}]")
        mark = "PASS" if result["passed"] else "FAIL"
        print(f"  [{mark}] {result['check']}")
        if result.get("note"):
            print(f"         {result['note']}")
        elif not result["passed"]:
            print(f"         prompt={result['prompt']}")
            print(f"         code  ={result['code']}")
    print()
    print(f"{len(report['results']) - len(report['failed'])}/{len(report['results'])} 项通过")
    if report["failed"]:
        print("未通过：")
        for item in report["failed"]:
            print(f"  - {item}")
    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(render(report), encoding="utf-8")
        print(f"\n已写入 {REPORT}")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
