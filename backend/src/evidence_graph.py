"""Event-scoped evidence and defeasible-argument graph for dangerous promotion.

Only observed facts are used. Model decisions are arguments about those facts,
not independent observations. Provenance aliases cannot inflate corroboration.
All numbers are timestamps/limits, not learned or calibrated risk probabilities.
"""
from __future__ import annotations

from collections import Counter
import json

from src.argumentation import grounded, backend_info, ArgumentationLimitError
from src.pead_rules import FACTS, KINDS, RuleSet, load_rules

POLICY = "R_DANGER_PROMOTION"
ENGINE_VERSION = "pead-pyarg-rules-v2.1"
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


def _known_event(item: dict) -> bool:
    return bool(_scope_value(item))


def _scope_value(item: dict) -> str | None:
    event_id = item.get("event_id")
    if isinstance(event_id, str) and event_id:
        return event_id
    key = item.get("referent_key")
    return key if isinstance(key, str) and key else None


def _same_event(a: dict, b: dict) -> bool:
    return _known_event(a) and _known_event(b) and _scope_value(a) == _scope_value(b)


def _event(item: dict) -> str:
    # Escape both reserved namespaces, so genuine model keys cannot collide
    # with the internal identity assigned to a missing referent.
    key = _scope_value(item)
    if _known_event(item):
        return "known:" + json.dumps(key, ensure_ascii=False) if key.startswith(("unresolved:", "known:")) else key
    return "unresolved:" + json.dumps(item["id"], ensure_ascii=False)


def _argument_id(kind: str, action_id: str, stance_id: str | None) -> str:
    return kind + ":" + json.dumps([action_id, stance_id], ensure_ascii=False, separators=(",", ":"))


class _BoundedAttacks(set):
    def __init__(self, limit):
        super().__init__()
        self.limit = limit

    def add(self, edge):
        if edge not in self and len(self) >= self.limit:
            raise ArgumentationLimitError("attack construction budget exceeded")
        super().add(edge)


def _relation_status(required: bool, pairs: set, checked: set, truncated: bool = False) -> dict:
    if truncated:
        status = "INCOMPLETE"
    elif not pairs or (not required and not checked):
        status = "NOT_REQUIRED"
    elif pairs <= checked:
        status = "COMPLETE"
    else:
        status = "PARTIAL" if pairs & checked else "NOT_CHECKED"
    return {"required": required, "status": status, "candidate_pairs": len(pairs),
            "checked_pairs": len(pairs & checked)}


def canonicalize(observations: list[dict], duration: int) -> dict:
    counts = Counter(item.get("id") for item in observations
                     if isinstance(item, dict) and isinstance(item.get("id"), str))
    atoms, aliases, signatures, invalid = [], {}, {}, []
    relevant_invalid = False
    for raw in sorted((o for o in observations if isinstance(o, dict)), key=lambda x: str(x.get("id", ""))):
        relevant = isinstance(raw.get("tag"), str) and raw["tag"] in ACTION_TAGS | PROMOTION_TAGS | COUNTER_TAGS
        oid = raw.get("id")
        no_time = raw.get("start_ms") is None and raw.get("end_ms") is None
        if (not isinstance(oid, str) or not oid or counts[oid] != 1
                or not isinstance(raw.get("modality"), str) or raw["modality"] not in MODALITIES
                or (raw.get("referent_key") is not None and not isinstance(raw["referent_key"], str))
                or (raw.get("event_id") is not None and not isinstance(raw["event_id"], str))
                or (raw.get("time_confidence") is not None and raw["time_confidence"] not in ("HIGH", "MEDIUM", "LOW", "UNAVAILABLE"))
                or not (no_time or _located(raw, duration))):
            invalid.append(oid if isinstance(oid, str) else "(missing ID)")
            relevant_invalid |= relevant
            continue
        if not relevant:
            continue
        refs = raw.get("source_refs", [])
        refs = sorted(set(r for r in refs if isinstance(r, str) and r)) if isinstance(refs, list) else []
        atom = {key: raw.get(key) for key in ("id", "modality", "tag", "start_ms", "end_ms", "event_id", "referent_key", "time_confidence")}
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
           counterfactual_limit: int | None = None, ruleset: RuleSet | None = None) -> tuple[dict, dict]:
    """Return the policy finding and its complete deterministic decision graph.

    relation_decisions already contain gated stances and immutable evidence-ID
    pairs; pair indexes are never reassigned during counterfactual evaluation.
    """
    if type(duration_ms) is not int or duration_ms < 0 or type(gap_ms) is not int or gap_ms < 0:
        raise ValueError("duration and relation gap must be non-negative integers")
    rules = ruleset if ruleset is not None else load_rules()
    if not isinstance(rules, RuleSet):
        raise TypeError("ruleset must be a validated RuleSet")
    if counterfactual_limit is not None and (type(counterfactual_limit) is not int or counterfactual_limit < 0):
        raise ValueError("counterfactual_limit must be a non-negative integer")
    counterfactual_limit = min(rules.limits.max_counterfactuals,
                              rules.limits.max_counterfactuals if counterfactual_limit is None else counterfactual_limit)
    if not isinstance(observations, list) or type(require_relation) is not bool:
        raise ValueError("observations must be a list and require_relation must be boolean")
    if not isinstance(coverage, str) or coverage not in {"FULL", "PARTIAL", "UNKNOWN", "ERROR", "REFUSED"}:
        coverage = "UNKNOWN"
    prepared = canonicalize(observations, duration_ms)
    base_facts = {fact: False for fact in FACTS}
    base_facts.update(coverage_failure=coverage in {"ERROR", "REFUSED"},
                      invalid_evidence=prepared["relevant_invalid"], partial_coverage=coverage != "FULL")
    atoms, aliases = prepared["atoms"], prepared["aliases"]
    if any(atom.get("event_id") for atom in atoms) and any(not atom.get("event_id") for atom in atoms):
        raise ValueError("cannot mix explicit event IDs with legacy referent-only observations")
    by_id = {atom["id"]: atom for atom in atoms}
    normalized_decisions = {}
    pair_validity = {}
    if relation_decisions is not None and not isinstance(relation_decisions, list):
        raise ValueError("relation_decisions must be a list")
    for decision in relation_decisions or []:
        if (not isinstance(decision, dict) or not isinstance(decision.get("action_id"), str)
                or not isinstance(decision.get("stance_id"), str)
                or not isinstance(decision.get("stance"), str)
                or decision["stance"] not in {"encourages_same", "warns_same", "unrelated", "insufficient", "REVIEW"}
                or ("valid" in decision and type(decision["valid"]) is not bool)):
            raise ValueError("invalid frozen relation decision")
        a, s = aliases.get(decision["action_id"]), aliases.get(decision["stance_id"])
        if a in by_id and s in by_id:
            valid = decision.get("valid", decision["stance"] != "REVIEW")
            normalized_decisions.setdefault((a, s), set()).add(decision["stance"] if valid else "REVIEW")
            pair_validity.setdefault((a, s), []).append(valid)
    valid_relation_pairs = {pair for pair, flags in pair_validity.items() if all(flags)}
    events = {}
    for action in (atom for atom in atoms if atom["tag"] in ACTION_TAGS):
        key = _event(action)
        events.setdefault(key, []).append(action)
    event_rows, argument_nodes, attack_edges, certificates, rule_firings = [], [], [], [], []
    all_relation_pairs = set()
    for event, actions in sorted(events.items()):
        arguments, attacks, graph_notes = [], _BoundedAttacks(rules.limits.max_attacks), []
        deferred_edges = []
        event_relation_pairs = set()
        resource_exceeded = False
        argument_lookup = {}

        def add(kind, action, stance=None, *, origin="RULE", polarity="SUPPORT", source=""):
            premises = sorted({action["id"]} | ({stance["id"]} if stance else set()))
            argument_id = _argument_id(kind, action["id"], stance["id"] if stance else None)
            existing = argument_lookup.get(argument_id)
            if existing:
                return argument_id
            if len(arguments) >= rules.limits.max_arguments:
                raise ArgumentationLimitError("argument construction budget exceeded")
            source_refs = sorted({ref for eid in premises for ref in by_id[eid]["source_refs"]})
            arguments.append({"id": argument_id, "event": event, "target_action": action["id"],
                              "kind": kind, "origin": origin, "polarity": polarity,
                              "premise_ids": premises, "source_refs": source_refs,
                              "model_is_independent_evidence": False, "source": source})
            argument_lookup[argument_id] = arguments[-1]
            return argument_id

        def emit(scope, facts, action, stance=None):
            result = []
            for rule in rules.argument_matches(scope, facts):
                origin, polarity = KINDS[rule.kind]
                source = ("warns_same" if facts["warns_same"] else "unrelated") if rule.kind == "MODEL_COUNTER" else ""
                aid = add(rule.kind, action, stance, origin=origin, polarity=polarity, source=source)
                node = argument_lookup[aid]
                if rule.kind == "MODEL_COUNTER":
                    node["relation_scope_valid"] = not facts["negative_relation_conflict"]
                node["rule_ids"] = sorted(set(node.get("rule_ids", [])) | {rule.id})
                rule_firings.append({"event_key": event, "rule_id": rule.id,
                                     "argument_id": aid, "premise_ids": node["premise_ids"]})
                result.append(aid)
            return result

        try:
            for action in actions:
                action_facts = dict(base_facts, action_unlocated=not _located(action, duration_ms))
                emit("ACTION", action_facts, action)
                if not _located(action, duration_ms):
                    continue
                candidates = [atom for atom in atoms if atom["tag"] in PROMOTION_TAGS | COUNTER_TAGS
                              and atom["id"] != action["id"] and _near(action, atom, gap_ms, duration_ms)]
                supports, counters, pending = [], [], []
                for stance in candidates:
                    same = _same_event(action, stance)
                    different = _known_event(action) and _known_event(stance) and not same
                    if stance["tag"] in PROMOTION_TAGS | {"warning"}:
                        event_relation_pairs.add((action["id"], stance["id"]))
                    choices = normalized_decisions.get((action["id"], stance["id"]), set())
                    is_promotion = stance["tag"] in PROMOTION_TAGS
                    if different and is_promotion and not choices and any(
                            c["tag"] in COUNTER_TAGS and _event(c) == event for c in candidates):
                        continue
                    facts = dict(base_facts, same_event=same, different_event=different,
                                 counter_tag=stance["tag"] in COUNTER_TAGS, promotion_tag=is_promotion,
                                 encourages_same="encourages_same" in choices, warns_same="warns_same" in choices,
                                 negative_relation_conflict="warns_same" in choices and not same,
                                 unrelated="unrelated" in choices, relation_review="REVIEW" in choices,
                                 relation_insufficient="insufficient" in choices, require_relation=require_relation,
                                 no_relation=not choices, target_unknown=not same and not different,
                                 time_uncertain=(action.get("time_confidence") in {"LOW", "UNAVAILABLE"}
                                                 or stance.get("time_confidence") in {"LOW", "UNAVAILABLE"}))
                    emitted = emit("PAIR", facts, action, stance)
                    for aid in emitted:
                        node = argument_lookup[aid]
                        if node["polarity"] == "SUPPORT":
                            supports.append(aid)
                        elif node["polarity"] == "COUNTER":
                            counters.append(aid)
                        elif node["kind"] not in {"REFERENT_CONFLICT", "TARGET_UNKNOWN", "COUNTER_REFERENT_CONFLICT"} or (
                                node["kind"] == "TARGET_UNKNOWN" and is_promotion and not choices):
                            pending.append(aid)
                        if node["kind"] in {"REFERENT_CONFLICT", "TARGET_UNKNOWN", "COUNTER_REFERENT_CONFLICT"}:
                            # Deferred: the target may not be generated yet, and rule
                            # priority decides generation order. Resolving after all
                            # nodes exist keeps the attack edge independent of that
                            # order — otherwise raising a rule's priority silently
                            # deletes the structural conflict.
                            deferred_edges.append(
                                ("MODEL_COUNTER" if node["kind"] == "COUNTER_REFERENT_CONFLICT"
                                 else "MODEL_PROMOTION", aid, action["id"], stance["id"],
                                 frozenset(choices)))
                        if node["kind"] == "REFERENT_CONFLICT":
                            graph_notes.append("REFERENT_CONFLICT")
                # Attacks are action-scoped, preventing another scene's warning from
                # cancelling an independently supported dangerous-promotion claim.
                for positive in supports:
                    pos = argument_lookup[positive]
                    pos_stance = [eid for eid in pos["premise_ids"] if eid != action["id"]]
                    for negative in counters:
                        neg = argument_lookup[negative]
                        if neg["source"] == "unrelated" and neg["premise_ids"] != pos["premise_ids"]:
                            continue
                        attacks.add((positive, negative))
                        attacks.add((negative, positive))
                    for unknown in pending:
                        node = argument_lookup[unknown]
                        unknown_stance = [eid for eid in node["premise_ids"] if eid != action["id"]]
                        targets = [by_id[eid] for eid in unknown_stance]
                        if targets and all(_event(t) != event and _known_event(t) for t in targets):
                            continue
                        if unknown_stance and pos_stance and unknown_stance != pos_stance:
                            # An unanswered relation for one stance must not cancel a
                            # support built on a *different* stance whose answer was
                            # verified. The graph reports the incomplete check
                            # separately; it is not a reason to drop that support.
                            continue
                        attacks.add((unknown, positive))
                unlocated_stance = [atom for atom in atoms if atom["tag"] in PROMOTION_TAGS | COUNTER_TAGS
                                    and not _located(atom, duration_ms) and _same_event(atom, action)]
                for stance in unlocated_stance:
                    for blocker in emit("UNLOCATED_PAIR", dict(base_facts, stance_unlocated=True,
                                                               same_event=True, promotion_tag=stance["tag"] in PROMOTION_TAGS,
                                                               counter_tag=stance["tag"] in COUNTER_TAGS), action, stance):
                        for positive in supports:
                            attacks.add((blocker, positive))
        except ArgumentationLimitError:
            resource_exceeded = True
        # Second phase: all argument nodes for this event now exist, so the
        # cross-argument attack edges can be resolved without depending on the
        # order rules happened to fire in.
        for target_kind, source, action_id, stance_id, choices in deferred_edges:
            required = "warns_same" if target_kind == "MODEL_COUNTER" else "encourages_same"
            if required not in choices:
                continue
            target = _argument_id(target_kind, action_id, stance_id)
            if target in argument_lookup:
                attacks.add((source, target))
        all_relation_pairs.update(event_relation_pairs)
        try:
            if resource_exceeded:
                raise ArgumentationLimitError("graph construction stopped at its budget")
            labels = grounded([item["id"] for item in arguments], sorted(attacks),
                              max_arguments=rules.limits.max_arguments, max_attacks=rules.limits.max_attacks)
        except ArgumentationLimitError:
            resource_exceeded = True
            ids = sorted(item["id"] for item in arguments)
            labels = {"accepted": [], "rejected": [], "undecided": ids,
                      "labels": {aid: "UNDECIDED" for aid in ids}, "backend": backend_info(),
                      "executed": False, "construction_truncated": True, "error": "ARGUMENTATION_RESOURCE_LIMIT",
                      "cycles": [], "explanations": {},
                      "statistics": {"arguments": len(ids), "attacks": len(attacks)}}
        positive = [a for a in arguments if a["polarity"] == "SUPPORT"]
        negative = [a for a in arguments if a["polarity"] == "COUNTER" and a.get("relation_scope_valid", True)]
        uncertainty = [a for a in arguments if a["polarity"] == "UNCERTAINTY"]
        accepted_positive = [a for a in positive if labels["labels"][a["id"]] == "IN"]
        # An argument that means "this could not be determined" and is still standing
        # blocks a risk verdict. Refutations of a model claim (referent conflicts) are
        # deliberately excluded: they settle a doubt instead of opening one. So is any
        # doubt about a stance that belongs to another event — the same scoping the
        # attack edges use, otherwise an unlabelled phrase in the next scene would
        # downgrade this scene's conclusion.
        OPEN_UNCERTAINTY_KINDS = {"RELATION_MISSING", "RELATION_UNCERTAIN", "TARGET_UNKNOWN",
                                  "TIME_UNCERTAIN", "UNLOCATED", "UNLOCATED_COUNTER"}

        def _concerns_this_event(node):
            stance_ids = [eid for eid in node["premise_ids"] if eid != node["target_action"]]
            targets = [by_id[eid] for eid in stance_ids if eid in by_id]
            return not (targets and all(_event(t) != event and _known_event(t) for t in targets))

        open_uncertainty = any(a["kind"] in OPEN_UNCERTAINTY_KINDS
                               and labels["labels"][a["id"]] == "IN"
                               and _concerns_this_event(a) for a in uncertainty)
        decision_facts = dict(base_facts, resource_exceeded=resource_exceeded,
                              accepted_support=bool(accepted_positive),
                              accepted_model_support=any(a["origin"] == "MODEL" for a in accepted_positive),
                              has_support=bool(positive), has_counter=bool(negative),
                              referent_conflict="REFERENT_CONFLICT" in graph_notes,
                              has_uncertainty=bool(uncertainty),
                              open_uncertainty=open_uncertainty,
                              # has_counter only says a counter node exists; a defeated
                              # counter is no reason to drop the review gate.
                              accepted_counter=any(labels["labels"][a["id"]] == "IN"
                                                   for a in negative),
                              model_counter=any(a["kind"] == "MODEL_COUNTER" for a in negative),
                              unrelated_confirmed=any("unrelated" in values for (aid, _), values in normalized_decisions.items()
                                                      if aid in {a["id"] for a in actions}))
        winning_rule, decision_trace = rules.decision(decision_facts)
        judgement, disposition, reason = winning_rule.judgement, winning_rule.disposition, winning_rule.reason_code
        supporting_ids = sorted({eid for a in positive + uncertainty for eid in a["premise_ids"]})
        counter_ids = sorted({eid for a in negative + [a for a in uncertainty if a["kind"] == "UNLOCATED_COUNTER"]
                              for eid in a["premise_ids"] if by_id[eid]["tag"] not in ACTION_TAGS})
        supporting_ids = sorted(set(supporting_ids) - set(counter_ids))
        row = {"event_key": event, "judgement": judgement, "disposition": disposition, "reason_code": reason,
               "supporting_ids": supporting_ids, "counter_ids": counter_ids,
               "argument_labels": labels, "decision_trace": decision_trace,
               "relation_check": _relation_status(require_relation, event_relation_pairs, valid_relation_pairs, resource_exceeded),
               "evidence_ids": sorted({a["id"] for a in actions} | set(supporting_ids) | set(counter_ids))}
        event_rows.append(row)
        for argument in arguments:
            argument["label"] = labels["labels"][argument["id"]]
            argument["explanation"] = labels["explanations"].get(argument["id"],
                {"label": "UNDECIDED", "not_evaluated": "ARGUMENTATION_RESOURCE_LIMIT"})
        argument_nodes.extend(arguments)
        attack_edges.extend({"source": source, "target": target, "relation": "ATTACK"} for source, target in sorted(attacks))
        certificates.extend({"event_key": event, "argument_id": arg["id"], "premise_ids": arg["premise_ids"],
                             "source_refs": arg["source_refs"], "note": "仅为构造该论证的事实前提，不含完整防御链，不能单独证明最终裁决。"}
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
    else:
        empty_rule, _ = rules.decision(base_facts)
        judgement, disposition, reason = empty_rule.judgement, empty_rule.disposition, empty_rule.reason_code
    if coverage in {"ERROR", "REFUSED"}:
        judgement, disposition, reason = "UNKNOWN", "RETRY", "MODEL_UNAVAILABLE"
    reported = flagged + reviewed or event_rows
    support_ids = sorted({eid for row in reported for eid in row["supporting_ids"]})
    counter_ids = sorted({eid for row in reported for eid in row["counter_ids"]})
    graph_truncated = any(not row["argument_labels"].get("executed", False) for row in event_rows)
    relation_check = _relation_status(require_relation, all_relation_pairs, valid_relation_pairs, graph_truncated)
    finding = {"policy_id": POLICY, "judgement": judgement, "disposition": disposition, "reason_code": reason,
               "supporting_ids": support_ids, "counter_ids": counter_ids,
               "counter_evidence": {"checked": not graph_truncated, "source": "COUNTER_CONTEXT_TAGS", "found": bool(counter_ids),
                                    "relation_checked": relation_check["status"] == "COMPLETE",
                                    "relation_status": relation_check["status"],
                                    "relation_candidate_pairs": relation_check["candidate_pairs"],
                                    "relation_checked_pairs": relation_check["checked_pairs"]},
               "event_decisions": event_rows}
    graph = {"engine_version": ENGINE_VERSION, "policy_id": POLICY, "semantics": "GROUNDED_SKEPTICAL",
             "solver": backend_info(),
             "solver_execution": {"executed_events": sum(row["argument_labels"]["executed"] for row in event_rows),
                                  "skipped_events": sum(not row["argument_labels"]["executed"] for row in event_rows)},
             "ruleset": {"id": rules.ruleset_id, "version": rules.version, "sha256": rules.fingerprint},
             "rule_firings": rule_firings, "limits": rules.limits.model_dump(),
             "evidence": atoms, "aliases": prepared["aliases"], "source_groups": prepared["source_groups"],
             "invalid_ids": prepared["invalid_ids"], "arguments": argument_nodes, "attacks": attack_edges,
             "certificates": certificates, "event_decisions": event_rows,
             "trace": [{"stage": "CANONICALIZE", "result": "相同来源与命题合并；不把多次描述当独立观察"},
                       {"stage": "ARGUMENTATION", "result": "支持、反向语境及不确定性按动作构造论证"},
                       {"stage": "PYARG_GROUNDED", "executed": any(row["argument_labels"]["executed"] for row in event_rows),
                        "result": "已执行事件由 PyArg 求解，未执行事件保留原因；NetworkX 只解释已求解图"},
                       {"stage": "RULE_DECISION", "result": "按显式优先级裁决；保存匹配规则、事实与规则集指纹"},
                       {"stage": "EVENT_AGGREGATION", "result": "独立事件分别裁决；已支持风险不会被其他事件的警示消除"}],
             "counterfactuals": [], "counterfactuals_truncated": False,
             "counterfactuals_skipped_reason": "ARGUMENTATION_RESOURCE_LIMIT" if any(
                 row["argument_labels"].get("error") == "ARGUMENTATION_RESOURCE_LIMIT" for row in event_rows) else "DISABLED" if counterfactual_limit == 0 else None,
             "limitations": ["图上的节点仍来自模型观察；不能独立核实视频事实。", "未报告的反向语境无法凭空补齐。"]}
    if counterfactual_limit > 0 and not graph["counterfactuals_skipped_reason"]:
        candidates = sorted(set(support_ids + counter_ids))
        graph["counterfactuals_truncated"] = len(candidates) > counterfactual_limit
        for eid in candidates[:counterfactual_limit]:
            removed = {original for original, canonical in aliases.items() if canonical == eid}
            reduced = [o for o in observations if not isinstance(o, dict) or o.get("id") not in removed]
            alternate, alternate_graph = decide(reduced, duration_ms, coverage, gap_ms, relation_decisions,
                                  require_relation=require_relation, counterfactual_limit=0, ruleset=rules)
            before_events = {r["event_key"]: r for r in event_rows}
            after_events = {r["event_key"]: r for r in alternate_graph["event_decisions"]}
            event_changes = []
            fields = ("judgement", "disposition", "reason_code")
            for key in sorted(before_events.keys() | after_events.keys()):
                before = {field: before_events[key][field] for field in fields} if key in before_events else None
                after = {field: after_events[key][field] for field in fields} if key in after_events else None
                if before != after:
                    event_changes.append({"event_key": key, "before": before, "after": after})
            graph["counterfactuals"].append({"removed_ids": sorted(removed), "scope": "GLOBAL_POLICY",
                                           "event_changes": event_changes, "judgement": alternate["judgement"],
                                           "disposition": alternate["disposition"], "reason_code": alternate["reason_code"],
                                           "changed": (alternate["judgement"], alternate["disposition"]) != (judgement, disposition),
                                           "ruleset_sha256": rules.fingerprint,
                                           "note": "仅移除这些观察，复用冻结关系回答与同一规则快照，不重新调用模型或重新编号。"})
    return finding, graph
