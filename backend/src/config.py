"""Single source of truth for PEAD's tunable relation parameters.

These values used to be written in three places — ``pead_engine.MAX_RELATION_GAP_MS``,
``relation_client.RELATION_GAP_MS`` and ``policies_v03.json``'s
``max_relation_gap_ms`` — with nothing checking that they agreed. A divergence
was silent in the worst way: candidate pairs would be selected with one window and
judged with another, so a relation could be dropped or accepted purely because two
constants drifted apart.

This module now owns the values, reads optional overrides from the environment,
records where each value came from, and exposes a check that fails loudly when the
policy file and the code disagree.
"""
from __future__ import annotations

import os

# Defaults. Changing a default here changes behaviour everywhere at once.
DEFAULT_RELATION_GAP_MS = 15_000
DEFAULT_MIN_CHOICE_CONFIDENCE = 0.85
DEFAULT_MAX_REVIEW_PROBABILITY = 0.49


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{name} 必须是整数，当前为 {raw!r}") from None
    if value < 0:
        raise ValueError(f"{name} 必须非负，当前为 {value}")
    return value


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        raise ValueError(f"{name} 必须是数值，当前为 {raw!r}") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} 必须落在 [0, 1]，当前为 {value}")
    return value


def relation_gap_ms() -> int:
    """Maximum gap between two cues still considered related, in milliseconds."""
    return _read_int("RELATION_GAP_MS", DEFAULT_RELATION_GAP_MS)


def min_choice_confidence() -> float:
    """Below this confidence a relation answer is not strong enough to act on."""
    return _read_float("RELATION_MIN_CHOICE_CONFIDENCE", DEFAULT_MIN_CHOICE_CONFIDENCE)


def max_review_probability() -> float:
    """Above this review probability the answer is routed to a human instead."""
    return _read_float("RELATION_MAX_REVIEW_PROBABILITY", DEFAULT_MAX_REVIEW_PROBABILITY)


def describe() -> dict[str, dict]:
    """Every effective value with its origin, for reports and audit trails."""
    gap = relation_gap_ms()
    confidence = min_choice_confidence()
    review = max_review_probability()
    return {
        "relation_gap_ms": {
            "value": gap,
            "source": "环境变量 RELATION_GAP_MS" if os.getenv("RELATION_GAP_MS")
                      else f"默认值 {DEFAULT_RELATION_GAP_MS}",
        },
        "min_choice_confidence": {
            "value": confidence,
            "source": "环境变量 RELATION_MIN_CHOICE_CONFIDENCE"
                      if os.getenv("RELATION_MIN_CHOICE_CONFIDENCE")
                      else f"默认值 {DEFAULT_MIN_CHOICE_CONFIDENCE}",
        },
        "max_review_probability": {
            "value": review,
            "source": "环境变量 RELATION_MAX_REVIEW_PROBABILITY"
                      if os.getenv("RELATION_MAX_REVIEW_PROBABILITY")
                      else f"默认值 {DEFAULT_MAX_REVIEW_PROBABILITY}",
        },
    }


def assert_policy_gap_agrees(policies: dict) -> int:
    """Fail loudly when the policy file's relation window contradicts the code.

    ``policies`` is the flat ``config["policies"]`` mapping (keyed by policy id).
    Returning the agreed value keeps callers from silently choosing one of two.
    """
    entry = policies.get("R_DANGER_PROMOTION")
    if not isinstance(entry, dict):
        raise ValueError("policies 缺少 R_DANGER_PROMOTION 条目")
    configured = entry.get("max_relation_gap_ms")
    if type(configured) is not int or configured < 0:
        raise ValueError("policies.R_DANGER_PROMOTION.max_relation_gap_ms 必须是非负整数")
    effective = relation_gap_ms()
    if configured != effective:
        raise ValueError(
            "关系时间窗不一致：policies_v03.json 配置为 "
            f"{configured}ms，而代码/环境变量的有效值为 {effective}ms。"
            "两者不一致会导致候选对按一个窗口筛选、却按另一个窗口判定；"
            "请把配置改成一致，或设置环境变量 RELATION_GAP_MS。")
    return effective
