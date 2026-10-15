"""Event-scoped evidence and defeasible-argument graph for dangerous promotion.

Only observed facts are used. Model decisions are arguments about those facts,
not independent observations. Provenance aliases cannot inflate corroboration.
All numbers are timestamps/limits, not learned or calibrated risk probabilities.
"""
from __future__ import annotations

from collections import Counter

from src.argumentation import grounded

POLICY = "R_DANGER_PROMOTION"
ENGINE_VERSION = "pead-evidence-graph-v1"
ACTION_TAGS = {"danger_action", "danger_description"}
PROMOTION_TAGS = {"encouragement", "challenge"}
COUNTER_TAGS = {"warning", "education_context", "news_context", "fiction_context"}
MODALITIES = {"visual", "speech", "screen_text", "sound", "metadata"}


def _located(item: dict, duration: int) -> bool:
    start, end = item.get("start_ms"), item.get("end_ms")
    return type(start) is int and type(end) is int and 0 <= start < end <= duration


def _near(a: dict, b: dict, gap: int, duration: int) -> bool:
    return (_located(a, duration) and _located(b, duration)
            and max(0, a["start_ms"] - b["end_ms"], b["start_ms"] - a["end_ms"]) <= gap)


def _event(item: dict) -> str:
    key = item.get("referent_key")
    return key if isinstance(key, str) and key else "unresolved:" + item["id"]


def canonicalize(observations: list[dict], duration: int) -> dict:
    counts = Counter(item.get("id") for item in observations
                     if isinstance(item, dict) and isinstance(item.get("id"), str))
    atoms, aliases, signatures, invalid = [], {}, {}, []
    relevant_invalid = False
    for raw in sorted((o for o in observations if isinstance(o, dict)), key=lambda x: str(x.get("id", ""))):
        relevant = raw.get("tag") in ACTION_TAGS | PROMOTION_TAGS | COUNTER_TAGS
        oid = raw.get("id")
        no_time = raw.get("start_ms") is None and raw.get("end_ms") is None
        if (not isinstance(oid, str) or not oid or counts[oid] != 1
                or raw.get("modality") not in MODALITIES or not (no_time or _located(raw, duration))):
            invalid.append(oid if isinstance(oid, str) else "(missing ID)")
            relevant_invalid |= relevant
            continue
        if not relevant:
            continue
        refs = raw.get("source_refs", [])
        refs = sorted(set(r for r in refs if isinstance(r, str) and r)) if isinstance(refs, list) else []
        atom = {key: raw.get(key) for key in ("id", "modality", "tag", "start_ms", "end_ms", "referent_key", "time_confidence")}
        atom["source_refs"] = refs
        # Unknown provenance is never assumed identical solely from text.
        signature = (atom["tag"], atom["modality"], _event(atom), atom["start_ms"], atom["end_ms"],
                     tuple(refs) if refs else ("unknown:" + oid,))
        if signature in signatures:
            aliases[oid] = signatures[signature]
            representative = next(a for a in atoms if a["id"] == signatures[signature])
            if atom.get("time_confidence") in {"LOW", "UNAVAILABLE"}:
                representative["time_confidence"] = atom["time_confidence"]
        else:
            aliases[oid] = oid
            signatures[signature] = oid
            atoms.append(atom)
    source_groups = {}
    for atom in atoms:
        if atom["source_refs"]:
            for ref in atom["source_refs"]:
                source_groups.setdefault(ref, []).append(atom["id"])
    return {"atoms": atoms, "aliases": dict(sorted(aliases.items())), "invalid_ids": sorted(set(invalid)),
            "relevant_invalid": relevant_invalid,
            "source_groups": {ref: sorted(ids) for ref, ids in sorted(source_groups.items())}}


def decide(observations: list[dict], duration_ms: int, coverage: str, gap_ms: int,
           relation_decisions: list[dict] | None = None, *, require_relation: bool = True,
           counterfactual_limit: int = 8) -> tuple[dict, dict]:
    """Return the policy finding and its complete deterministic decision graph.

    relation_decisions already contain gated stances and immutable evidence-ID
    pairs; pair indexes are never reassigned during counterfactual evaluation.
    """
    prepared = canonicalize(observations, duration_ms)
    atoms, aliases = prepared["atoms"], prepared["aliases"]
    by_id = {atom["id"]: atom for atom in atoms}
    normalized_decisions = {}
    for decision in relation_decisions or []:
        a, s = aliases.get(decision["action_id"]), aliases.get(decision["stance_id"])
        if a in by_id and s in by_id:
            normalized_decisions.setdefault((a, s), set()).add(decision["stance"])
    events = {}
    for action in (atom for atom in atoms if atom["tag"] in ACTION_TAGS):
        key = _event(action)
        events.setdefault(key, []).append(action)
    event_rows, argument_nodes, attack_edges, certificates = [], [], [], []
    for event, actions in sorted(events.items()):
        arguments, attacks, graph_notes = [], set(), []
        argument_lookup = {}

        def add(kind, action, stance=None, *, origin="RULE", polarity="SUPPORT", source=""):
            premises = sorted({action["id"]} | ({stance["id"]} if stance else set()))
            argument_id = f"{kind}:{action['id']}:{stance['id'] if stance else '-'}"
            existing = argument_lookup.get(argument_id)
            if existing:
                return argument_id
            source_refs = sorted({ref for eid in premises for ref in by_id[eid]["source_refs"]})
            arguments.append({"id": argument_id, "event": event, "target_action": action["id"],
                              "kind": kind, "origin": origin, "polarity": polarity,
                              "premise_ids": premises, "source_refs": source_refs,
                              "model_is_independent_evidence": False, "source": source})
            argument_lookup[argument_id] = arguments[-1]
            return argument_id

        for action in actions:
            if not _located(action, duration_ms):
                add("UNLOCATED", action, polarity="UNCERTAINTY")
                continue
            candidates = [atom for atom in atoms if atom["tag"] in PROMOTION_TAGS | COUNTER_TAGS
                          and atom["id"] != action["id"] and _near(action, atom, gap_ms, duration_ms)]
            supports, counters, pending = [], [], []
            for stance in candidates:
                same = _event(action) == _event(stance) and not event.startswith("unresolved:")
                different = (not _event(action).startswith("unresolved:")
                             and not _event(stance).startswith("unresolved:") and not same)
                choices = normalized_decisions.get((action["id"], stance["id"]), set())
                is_promotion = stance["tag"] in PROMOTION_TAGS
                local_counter = same and stance["tag"] in COUNTER_TAGS
                if different and is_promotion and not choices and any(
                        c["tag"] in COUNTER_TAGS and _event(c) == event for c in candidates):
                    continue
                if local_counter:
                    counters.append(add("COUNTER_CONTEXT", action, stance, polarity="COUNTER"))
                if same and is_promotion:
                    supports.append(add("LOCAL_PROMOTION", action, stance))
                if "encourages_same" in choices:
                    candidate = add("MODEL_PROMOTION", action, stance, origin="MODEL")
                    supports.append(candidate)
                    if different:
                        blocker = add("REFERENT_CONFLICT", action, stance, polarity="UNCERTAINTY")
                        attacks.add((blocker, candidate))
                        graph_notes.append("REFERENT_CONFLICT")
                    elif not same:
                        blocker = add("TARGET_UNKNOWN", action, stance, polarity="UNCERTAINTY")
                        attacks.add((blocker, candidate))
                        graph_notes.append("TARGET_UNKNOWN")
                if choices & {"warns_same", "unrelated"}:
                    counters.append(add("MODEL_COUNTER", action, stance, origin="MODEL", polarity="COUNTER",
                                        source="warns_same" if "warns_same" in choices else "unrelated"))
                if choices & {"REVIEW", "insufficient"}:
                    pending.append(add("RELATION_UNCERTAIN", action, stance, origin="MODEL", polarity="UNCERTAINTY"))
                if require_relation and is_promotion and not choices:
                    pending.append(add("RELATION_MISSING", action, stance, polarity="UNCERTAINTY"))
                if not same and is_promotion and not choices:
                    pending.append(add("TARGET_UNKNOWN", action, stance, polarity="UNCERTAINTY"))
                if (action.get("time_confidence") in {"LOW", "UNAVAILABLE"}
                        or stance.get("time_confidence") in {"LOW", "UNAVAILABLE"}):
                    pending.append(add("TIME_UNCERTAIN", action, stance, polarity="UNCERTAINTY"))
            # Attacks are action-scoped, preventing another scene's warning from
            # cancelling an independently supported dangerous-promotion claim.
            for positive in supports:
                for negative in counters:
                    neg = argument_lookup[negative]
                    pos = argument_lookup[positive]
                    if neg["source"] == "unrelated" and neg["premise_ids"] != pos["premise_ids"]:
                        continue
                    attacks.add((positive, negative))
                    attacks.add((negative, positive))
                for unknown in pending:
                    node = argument_lookup[unknown]
                    targets = [by_id[eid] for eid in node["premise_ids"] if eid != action["id"]]
                    if targets and all(_event(t) != event and not _event(t).startswith("unresolved:") for t in targets):
                        continue
                    attacks.add((unknown, positive))
            unlocated_stance = [atom for atom in atoms if atom["tag"] in PROMOTION_TAGS
                                and not _located(atom, duration_ms) and _event(atom) == event]
            for stance in unlocated_stance:
                blocker = add("UNLOCATED", action, stance, polarity="UNCERTAINTY")
                for positive in supports:
                    attacks.add((blocker, positive))
        labels = grounded([item["id"] for item in arguments], sorted(attacks))
        positive = [a for a in arguments if a["polarity"] == "SUPPORT"]
        negative = [a for a in arguments if a["polarity"] == "COUNTER"]
        uncertainty = [a for a in arguments if a["polarity"] == "UNCERTAINTY"]
        accepted_positive = [a for a in positive if labels["labels"][a["id"]] == "IN"]
        if coverage in {"ERROR", "REFUSED"}:
            judgement, disposition, reason = "UNKNOWN", "RETRY", "MODEL_UNAVAILABLE"
        elif prepared["relevant_invalid"]:
            judgement, disposition, reason = "INSUFFICIENT", "REVIEW", "UNVERIFIED_OR_UNLOCATED"
        elif accepted_positive:
            judgement, disposition, reason = "SUPPORTED", "FLAG", "RELATED_ACTION_AND_PROMOTION"
            if any(a["origin"] == "MODEL" for a in accepted_positive):
                reason = "RELATION_LINK_ASSISTED"
        elif positive and (negative or "REFERENT_CONFLICT" in graph_notes):
            judgement, disposition, reason = "CONFLICTED", "REVIEW", "CONFLICTING_STANCE"
            if "REFERENT_CONFLICT" in graph_notes:
                reason = "RELATION_REFERENT_DISAGREEMENT"
        elif uncertainty:
            judgement, disposition, reason = "INSUFFICIENT", "REVIEW", "MISSING_SEMANTIC_RELATION"
        elif coverage != "FULL":
            judgement, disposition, reason = "UNKNOWN", "RECHECK", "INCOMPLETE_OBSERVATION"
        else:
            judgement, disposition, reason = "NOT_SUPPORTED", "NONE", "NO_SUPPORTING_RELATION"
            if any(a["kind"] == "MODEL_COUNTER" for a in negative):
                reason = "RELATION_UNRELATED_CONFIRMED" if any(
                    "unrelated" in values for (aid, _), values in normalized_decisions.items() if aid in {a["id"] for a in actions}
                ) else "NO_SUPPORTING_RELATION"
        supporting_ids = sorted({eid for a in positive + uncertainty for eid in a["premise_ids"]})
        counter_ids = sorted({eid for a in negative for eid in a["premise_ids"] if by_id[eid]["tag"] not in ACTION_TAGS})
        supporting_ids = sorted(set(supporting_ids) - set(counter_ids))
        row = {"event_key": event, "judgement": judgement, "disposition": disposition, "reason_code": reason,
               "supporting_ids": supporting_ids, "counter_ids": counter_ids,
               "argument_labels": labels, "evidence_ids": sorted({a["id"] for a in actions} | set(supporting_ids) | set(counter_ids))}
        event_rows.append(row)
        for argument in arguments:
            argument["label"] = labels["labels"][argument["id"]]
        argument_nodes.extend(arguments)
        attack_edges.extend({"source": source, "target": target, "relation": "ATTACK"} for source, target in sorted(attacks))
        certificates.extend({"event_key": event, "argument_id": arg["id"], "premise_ids": arg["premise_ids"],
                             "source_refs": arg["source_refs"], "note": "该论证的充分前提集合，非全局最小性证明。"}
                            for arg in accepted_positive if disposition == "FLAG")
    flagged = [row for row in event_rows if row["disposition"] == "FLAG"]
    reviewed = [row for row in event_rows if row["disposition"] in {"REVIEW", "RECHECK"}]
    selected = flagged or reviewed or event_rows
    if selected:
        lead = selected[0]
        judgement, disposition, reason = lead["judgement"], lead["disposition"], lead["reason_code"]
        if not flagged and any(r["judgement"] == "CONFLICTED" for r in reviewed):
            lead = next(r for r in reviewed if r["judgement"] == "CONFLICTED")
            judgement, disposition, reason = lead["judgement"], lead["disposition"], lead["reason_code"]
    elif prepared["relevant_invalid"]:
        judgement, disposition, reason = "INSUFFICIENT", "REVIEW", "UNVERIFIED_OR_UNLOCATED"
    elif coverage != "FULL":
        judgement, disposition, reason = "UNKNOWN", "RECHECK", "INCOMPLETE_OBSERVATION"
    else:
        judgement, disposition, reason = "NOT_SUPPORTED", "NONE", "NO_SUPPORTING_RELATION"
    if coverage in {"ERROR", "REFUSED"}:
        judgement, disposition, reason = "UNKNOWN", "RETRY", "MODEL_UNAVAILABLE"
    support_ids = sorted({eid for row in selected for eid in row["supporting_ids"]})
    counter_ids = sorted({eid for row in selected for eid in row["counter_ids"]})
    finding = {"policy_id": POLICY, "judgement": judgement, "disposition": disposition, "reason_code": reason,
               "supporting_ids": support_ids, "counter_ids": counter_ids,
               "counter_evidence": {"checked": True, "source": "COUNTER_CONTEXT_TAGS", "found": bool(counter_ids),
                                    "relation_checked": bool(relation_decisions) or not require_relation},
               "event_decisions": event_rows}
    graph = {"engine_version": ENGINE_VERSION, "policy_id": POLICY, "semantics": "GROUNDED_SKEPTICAL",
             "evidence": atoms, "aliases": prepared["aliases"], "source_groups": prepared["source_groups"],
             "invalid_ids": prepared["invalid_ids"], "arguments": argument_nodes, "attacks": attack_edges,
             "certificates": certificates, "event_decisions": event_rows,
             "trace": [{"stage": "CANONICALIZE", "result": "相同来源与命题合并；不把多次描述当独立观察"},
                       {"stage": "ARGUMENTATION", "result": "支持、反向语境及不确定性按动作构造论证"},
                       {"stage": "GROUNDED_FIXED_POINT", "result": "相互攻击保持未决，不以模型信心投票"},
                       {"stage": "EVENT_AGGREGATION", "result": "独立事件分别裁决；已支持风险不会被其他事件的警示消除"}],
             "counterfactuals": [], "counterfactuals_truncated": False,
             "limitations": ["图上的节点仍来自模型观察；不能独立核实视频事实。", "未报告的反向语境无法凭空补齐。"]}
    if counterfactual_limit > 0:
        candidates = sorted(set(support_ids + counter_ids))
        graph["counterfactuals_truncated"] = len(candidates) > counterfactual_limit
        for eid in candidates[:counterfactual_limit]:
            removed = {original for original, canonical in aliases.items() if canonical == eid}
            reduced = [o for o in observations if not isinstance(o, dict) or o.get("id") not in removed]
            alternate, _ = decide(reduced, duration_ms, coverage, gap_ms, relation_decisions,
                                  require_relation=require_relation, counterfactual_limit=0)
            graph["counterfactuals"].append({"removed_ids": sorted(removed), "judgement": alternate["judgement"],
                                           "disposition": alternate["disposition"], "reason_code": alternate["reason_code"],
                                           "changed": (alternate["judgement"], alternate["disposition"]) != (judgement, disposition),
                                           "note": "仅移除这些观察，复用冻结关系回答，不重新调用模型或重新编号。"})
    return finding, graph
