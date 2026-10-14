"""JEV adapter isolated behind the internal issue-locator contract."""
from __future__ import annotations

import json
import math
import os
import urllib.request
from pathlib import Path

from src.redaction import redact

ENDPOINT_ENV = "ISSUE_LOCATOR_ENDPOINT"
MODEL_ENV = "ISSUE_LOCATOR_MODEL"
KEY_ENV = "ISSUE_LOCATOR_API_KEY"
MIN_CONFIDENCE = 0.80
LOCATOR_TAGS = (
    "danger_action", "danger_description", "encouragement", "challenge", "warning",
    "violence", "news_context", "fiction_context", "education_context", "pii_candidate",
    "credential_claim", "marketing_claim", "absolute_claim", "self_harm_action",
    "self_harm_instruction", "sexual_content", "sexual_minor_risk", "hate_or_harassment",
    "fraud_or_scam", "financial_inducement", "controlled_goods",
    "controlled_goods_promotion", "minor_risk",
)


def _question_template() -> dict[str, str]:
    """Load the JEV question contract; JEV does not consume chat prompts."""
    path=Path(__file__).resolve().parents[1] / "prompts" / "issue_locator_jev_question.md"
    text=path.read_text(encoding="utf-8")
    sections={}
    current=None
    for line in text.splitlines():
        if line.startswith("## "):
            current=line[3:].strip()
            sections[current]=[]
        elif current is not None:
            sections[current].append(line)
    required=("`instructions`", "`criteria.true`", "`criteria.false`")
    if any(name not in sections for name in required):
        raise RuntimeError("问题定位 JEV 模板缺少必需段落")
    return {name:"\n".join(sections[name]).strip() for name in required}


def _event_state(detail: dict) -> list[dict]:
    timeline = detail.get("timeline") if isinstance(detail, dict) else None
    shots = timeline.get("shots") if isinstance(timeline, dict) else []
    events = timeline.get("events") if isinstance(timeline, dict) else []
    facts: dict[str, dict] = {}
    for shot in shots if isinstance(shots, list) else []:
        if not isinstance(shot, dict):
            continue
        shot_id = shot.get("shot_id")
        for field, modality in (("visual_facts", "visual"), ("speech_transcript", "speech"),
                                ("subtitle_text", "screen_text"), ("screen_text", "screen_text"),
                                ("audio_observations", "sound")):
            for fact in shot.get(field, []) if isinstance(shot.get(field), list) else []:
                if isinstance(fact, dict) and isinstance(shot_id, str) and isinstance(fact.get("fact_id"), str):
                    facts[f"{shot_id}:{fact['fact_id']}"] = {
                        "modality": modality,
                        "start_ms": fact.get("start_ms"),
                        "end_ms": fact.get("end_ms"),
                        "summary": redact(str(fact.get("summary_zh") or ""))[:500],
                        "verbatim": redact(str(fact.get("verbatim_redacted") or ""))[:350],
                    }
    state=[]
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict) or not isinstance(event.get("event_id"), str):
            continue
        refs=[ref for ref in event.get("evidence_refs", []) if ref in facts]
        if refs:
            state.append({"event_id":event["event_id"], "summary":redact(str(event.get("summary") or ""))[:600],
                         "context":event.get("context", {}),
                         "facts":[{"ref":ref, **facts[ref]} for ref in refs]})
    return state


def build_jev_request(video_parse_detail: dict) -> dict:
    """Build JEV's documented SystemOne state/questions request."""
    events=_event_state(video_parse_detail)
    template=_question_template()
    questions={}
    for event in events:
        for tag in LOCATOR_TAGS:
            questions[f"{event['event_id']}__{tag}"]={
                "type":"noul",
                "instructions":template["`instructions`"].replace("{{EVENT_ID}}",event["event_id"]).replace("{{TAG}}",tag),
                "criteria":{"true":template["`criteria.true`"].replace("{{TAG}}",tag),
                            "false":template["`criteria.false`"].replace("{{TAG}}",tag)}
            }
    return {"model":os.getenv(MODEL_ENV, ""),"state":{"events":events},"questions":questions}


def adapt_jev_response(request: dict, response: dict) -> dict:
    """Validate every requested answer before projecting risk cues.

    A missing/invalid answer is a failed observation, never a negative answer.
    Legitimate probabilities below the cue threshold remain valid negatives.
    """
    questions = request.get("questions")
    if not isinstance(questions, dict):
        raise ValueError("问题定位请求缺少 questions 对象")
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
        raise ValueError("问题定位响应缺少 answers 对象")
    answers = response["answers"]
    if set(answers) != set(questions):
        # Do not include provider content, fact text or credentials in errors.
        raise ValueError("问题定位回答必须完整匹配请求的问题 ID")
    for name, answer in answers.items():
        if not isinstance(answer, dict) or answer.get("type") != "noul":
            raise ValueError("问题定位回答必须为 noul 类型")
        probability = answer.get("noul")
        if (type(probability) not in (int, float) or not 0.0 <= probability <= 1.0
                or not math.isfinite(probability)):
            raise ValueError("问题定位 noul 必须为 [0, 1] 内的有限数值")
    state_events={e["event_id"]:e for e in request.get("state", {}).get("events", [])}
    cues=[]
    # Use request order so provider map ordering cannot change cue IDs.
    for name in questions:
        answer = answers[name]
        try:
            event_id, tag=name.rsplit("__", 1)
            event=state_events[event_id]
            probability=answer["noul"]
            if tag not in LOCATOR_TAGS:
                raise ValueError("问题定位请求包含未知标签")
            if probability < MIN_CONFIDENCE:
                continue
            primary=event["facts"][0]
            cues.append({"cue_id":f"C{len(cues)+1:03d}","tag":tag,"event_id":event_id,
                         "modality":primary["modality"],"evidence_refs":[x["ref"] for x in event["facts"]],
                         "observation":primary["summary"],"verbatim_redacted":primary["verbatim"],
                         "time_confidence":"HIGH" if probability >= 0.93 else "MEDIUM",
                         "needs_human_review":probability < 0.93})
        except (AttributeError, KeyError, IndexError, TypeError, ValueError):
            raise ValueError("问题定位请求的问题与事件事实无法对应") from None
    if len(cues) > 80:
        raise ValueError("问题定位风险线索超过协议上限，不能静默截断")
    return {"schema_version":"videoguard_issue_locator_v1","risk_cues":cues,"limitations":[]}


def locate_issues(video_parse_detail: dict, timeout: int = 25) -> dict:
    request=build_jev_request(video_parse_detail)
    if not request["questions"]:
        return {"schema_version":"videoguard_issue_locator_v1","risk_cues":[],"limitations":["没有可供定位的事件证据。"]}
    key=os.getenv(KEY_ENV); endpoint=os.getenv(ENDPOINT_ENV); model=os.getenv(MODEL_ENV)
    if not key or not endpoint or not model:
        raise RuntimeError("未配置问题定位服务")
    body=json.dumps({**request,"model":model},ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(endpoint,data=body,method="POST",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=timeout) as result:
        response=json.loads(result.read().decode("utf-8"))
    return adapt_jev_response(request,response)
