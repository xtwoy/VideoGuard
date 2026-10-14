"""Replaceable OpenAI-compatible adapters for video parsing and audit reporting."""
from __future__ import annotations
import json, os
from pathlib import Path

MAX_BASE64_VIDEO_BYTES=10_000_000  # Official limit is *less than* 10 MB encoded video.


def build_video_parse_messages(video_url: str, system_prompt: str, user_prompt: str)->list[dict]:
    if not video_url.startswith(("https://","data:;base64,")):
        raise ValueError("Use an authorized HTTPS URL or a size-checked Base64 video")
    if video_url.startswith("data:;base64,"):
        encoded=video_url.split(",",1)[1]
        if not encoded or len(encoded.encode("utf-8"))>=MAX_BASE64_VIDEO_BYTES:
            raise ValueError("Base64 video must be nonempty and encoded payload smaller than 10 MB")
    return [
        {"role":"system","content":system_prompt},
        {"role":"user","content":[{"type":"video_url","video_url":{"url":video_url}},
                                  {"type":"text","text":user_prompt}]}
    ]

def _client():
    from openai import OpenAI
    key=os.getenv("VIDEO_MODEL_API_KEY")
    base=os.getenv("VIDEO_MODEL_BASE_URL")
    if not key or not base:
        raise RuntimeError("Set VIDEO_MODEL_API_KEY and VIDEO_MODEL_BASE_URL")
    return OpenAI(api_key=key,base_url=base,timeout=120,max_retries=1)

def parse_video(video_url: str, duration_ms: int, title: str="")->dict:
    home=Path(__file__).resolve().parents[1]
    system=(home/"prompts/video_parse_system.md").read_text(encoding="utf-8")
    user=(home/"prompts/video_parse_user.md").read_text(encoding="utf-8").replace(
        "{{VIDEO_TITLE}}",title).replace("{{DURATION_MS}}",str(duration_ms))
    chunks=_client().chat.completions.create(
        model=os.environ["VIDEO_PARSE_MODEL"],
        messages=build_video_parse_messages(video_url,system,user),
        stream=True,stream_options={"include_usage":True},
        modalities=["text"],
        response_format={"type":"json_object"},
        extra_body={"reasoning_effort":"low"})
    buf=[]
    for chunk in chunks:
        for choice in (getattr(chunk,"choices",None) or []):
            val=getattr(choice.delta,"content",None)
            if isinstance(val,str): buf.append(val)
    return json.loads("".join(buf))

def generate_audit_report(audit_context: dict)->dict:
    home=Path(__file__).resolve().parents[1]
    system=(home/"prompts/audit_report_system.md").read_text(encoding="utf-8")
    user=(home/"prompts/audit_report_user.md").read_text(encoding="utf-8").replace(
        "{{AUDIT_CONTEXT_JSON}}",json.dumps(audit_context,ensure_ascii=False))
    result=_client().chat.completions.create(
        model=os.environ["AUDIT_REPORT_MODEL"], messages=[
            {"role":"system","content":system},
            {"role":"user","content":user}],
        response_format={"type":"json_object"})
    return json.loads(result.choices[0].message.content)

