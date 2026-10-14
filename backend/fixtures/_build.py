"""Authoring primitives for VideoGuard-E fixture data.

These helpers only *build plain dicts* in the shapes the three provider
protocols specify. They never call the network and never implement the
project's validation logic — validation lives in pipeline.clean_video_parse,
pipeline.clean_issue_locator and src.audit_report.validate_audit_report, and
the validator tool runs every fixture through those real functions.

Usage:
    from fixtures._build import shot, fact, quality, build_case

Protocol references:
    backend/prompts/video_parse_schema_v2.json    -> video_parse_response.json
    backend/prompts/issue_locator_schema_v1.json  -> issue_locator_response.json
    backend/prompts/audit_report_schema_v1.json   -> audit_report_response.json
"""
from __future__ import annotations

FACT_FIELDS = (
    "visual_facts", "speech_transcript", "subtitle_text",
    "screen_text", "audio_observations",
)

# Which shot field an issue-locator cue modality is expected to cite.
MODALITY_FIELD = {
    "visual": "visual_facts",
    "speech": "speech_transcript",
    "screen_text": "screen_text",
    "sound": "audio_observations",
    "metadata": "visual_facts",
}


def fact(fact_id: str, start_ms: int, end_ms: int, summary: str,
         verbatim: str = "", confidence: str = "HIGH",
         limitations: list[str] | None = None) -> dict:
    """One atomic, time-located observation inside a shot."""
    return {
        "fact_id": fact_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "summary_zh": summary,
        "verbatim_redacted": verbatim,
        "confidence": confidence,
        "limitations": list(limitations or []),
    }


def quality(visual_clarity: str = "CLEAR", speech_clarity: str = "CLEAR",
            audio_status: str = "PASS", voice_clarity: str = "PASS",
            bgm_interference: str = "PASS", clarity: str = "PASS",
            pixelation: str = "PASS", aliasing: str = "PASS",
            audio_evidence: str = "口播清晰，无持续背景噪声。",
            audio_refs: list[str] | None = None,
            visual_evidence: str = "画面清晰，主体可辨认。",
            visual_refs: list[str] | None = None,
            limitations: list[str] | None = None) -> dict:
    """Per-shot audio/visual quality block.

    ``pipeline._validate_quality_refs`` requires every quality evidence_ref to
    belong to the same shot, and requires each of audio/visual to carry either
    evidence_refs or its own limitation list. When a modality has no evidence
    in a shot, a limitation is filled in automatically so the block stays valid.
    """
    audio_refs = list(audio_refs or [])
    visual_refs = list(visual_refs or [])
    audio_limitations = [] if audio_refs else [
        "该镜头没有可定位的音频证据，未据此判断音质。"]
    visual_limitations = [] if visual_refs else [
        "该镜头没有可定位的视觉证据，未据此判断画质。"]
    return {
        "visual_clarity": visual_clarity,
        "speech_clarity": speech_clarity,
        "audio": {
            "status": audio_status,
            "voice_clarity": voice_clarity,
            "bgm_interference": bgm_interference,
            "evidence": audio_evidence,
            "evidence_refs": audio_refs,
            "limitations": audio_limitations,
        },
        "visual": {
            "clarity": clarity,
            "pixelation": pixelation,
            "aliasing_candidate": aliasing,
            "evidence": visual_evidence,
            "evidence_refs": visual_refs,
            "limitations": visual_limitations,
        },
        "limitations": list(limitations or []),
    }


def shot(shot_id: str, start_ms: int, end_ms: int, scene_summary: str,
         continuity: str = "CUT", quality_block: dict | None = None,
         **fields) -> dict:
    """One shot. Pass facts per modality as keyword arguments.

    Example:
        shot("S001", 0, 4000, "开场", visual_facts=[...], speech_transcript=[...])
    """
    unknown = set(fields) - set(FACT_FIELDS)
    if unknown:
        raise ValueError(f"unknown fact fields: {sorted(unknown)}")
    block = {
        "shot_id": shot_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "continuity": continuity,
        "scene_summary": scene_summary,
        "quality": quality_block or quality(),
    }
    for name in FACT_FIELDS:
        block[name] = list(fields.get(name, []))
    return block


def fact_catalog(shots: list[dict]) -> dict[str, tuple[int, int]]:
    """Map ``S001:F001`` -> (start_ms, end_ms) for every fact in the timeline."""
    catalog: dict[str, tuple[int, int]] = {}
    for block in shots:
        shot_id = block["shot_id"]
        for field in FACT_FIELDS:
            for item in block.get(field, []):
                catalog[f"{shot_id}:{item['fact_id']}"] = (item["start_ms"], item["end_ms"])
    return catalog


def trace(refs: list[str], ranges: list[tuple[int, int, list[str]]] | None = None,
          limitations: list[str] | None = None) -> dict:
    """Section-level traceability block.

    ``pipeline._clean_analysis_trace`` requires every declared ref to appear in
    some time range, and every range to cite at least one ref it covers.
    """
    return {
        "evidence_refs": list(refs),
        "time_ranges": [
            {"start_ms": start, "end_ms": end, "evidence_refs": list(item_refs)}
            for start, end, item_refs in (ranges or [])
        ],
        "limitations": list(limitations or []),
    }


def event(event_id: str, start_ms: int, end_ms: int, event_type: str,
          summary: str, refs: list[str], stance: str = "UNKNOWN",
          target_relation: str = "UNCERTAIN", counter_refs: list[str] | None = None,
          referent_key: str | None = None, uncertainties: list[str] | None = None) -> dict:
    """A parsed event plus its stance/target context."""
    return {
        "event_id": event_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "event_type": event_type,
        "referent_key": referent_key if referent_key is not None else event_id,
        "summary": summary,
        "evidence_refs": list(refs),
        "context": {
            "stance": stance,
            "target_relation": target_relation,
            "counter_context_refs": list(counter_refs or []),
        },
        "uncertainties": list(uncertainties or []),
    }


def analysis_issue(issue_id: str, category: str, severity: str, summary: str,
                   start_ms: int, end_ms: int, refs: list[str],
                   limitations: list[str] | None = None) -> dict:
    return {
        "id": issue_id,
        "category": category,
        "severity": severity,
        "summary": summary,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "evidence_refs": list(refs),
        "limitations": list(limitations or []),
    }


def cue(cue_id: str, tag: str, event_id: str, modality: str, refs: list[str],
        observation: str, verbatim: str = "", time_confidence: str = "HIGH",
        needs_human_review: bool = False) -> dict:
    """One issue-locator risk cue. Only tags in pipeline.VALID_TAGS survive."""
    return {
        "cue_id": cue_id,
        "tag": tag,
        "event_id": event_id,
        "modality": modality,
        "evidence_refs": list(refs),
        "observation": observation,
        "verbatim_redacted": verbatim,
        "time_confidence": time_confidence,
        "needs_human_review": needs_human_review,
    }


def video_parse(shots: list[dict], events: list[dict], summary: dict,
                content_analysis: dict, status: str = "FULL",
                video_end_ms: int = 0, modalities: dict | None = None,
                coverage_limitations: list[str] | None = None,
                time_localization: str = "RELIABLE") -> dict:
    """Assemble a videoguard_video_parse_v2 response."""
    return {
        "schema_version": "videoguard_video_parse_v2",
        "coverage": {
            "status": status,
            "video_start_ms": 0,
            "video_end_ms": video_end_ms,
            "modalities": modalities or {
                "visual": "FULL", "speech": "FULL",
                "screen_text": "FULL", "sound": "FULL",
            },
            "limitations": list(coverage_limitations or []),
            "time_localization": time_localization,
        },
        "timeline": {"shots": shots, "events": events},
        "video_summary": summary,
        "content_analysis": content_analysis,
    }


def issue_locator(cues: list[dict], limitations: list[str] | None = None) -> dict:
    return {
        "schema_version": "videoguard_issue_locator_v1",
        "risk_cues": cues,
        "limitations": list(limitations or []),
    }


RELATION_CHOICES = ("encourages_same", "warns_same", "unrelated", "insufficient")


def relation_response(choices: dict[str, str], model: str = "mock-relation-1",
                      confidence: float = 0.94, needs_review: float = 0.10) -> dict:
    """Build a provider-shaped relation response from ``{pair_id: choice}``.

    Pair ids are assigned by src.relation_client.select_pairs (``pair_0`` …), so
    callers pass the ids the real selection step produced. Answers are written
    in the exact shape src.relation_client.validate_response parses.
    """
    answers: dict[str, dict] = {}
    for pair_id, choice in choices.items():
        if choice not in RELATION_CHOICES:
            raise ValueError(f"invalid relation choice: {choice!r}")
        probabilities = {name: 0.02 for name in RELATION_CHOICES}
        probabilities[choice] = confidence
        total = sum(probabilities.values())
        answers[f"{pair_id}_relation"] = {
            "type": "choice",
            "choice": choice,
            "confidence": confidence,
            "probabilities": {name: value / total for name, value in probabilities.items()},
        }
        answers[f"{pair_id}_review"] = {"type": "noul", "noul": needs_review}
    return {"model": model, "answers": answers}
