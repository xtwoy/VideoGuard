"""Immutable, validated boolean rules with explicit priorities; never eval()."""
from __future__ import annotations

import hashlib
import json
from functools import cached_property
from pathlib import Path
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

FACTS = frozenset({
    "action_unlocated", "same_event", "different_event", "counter_tag", "promotion_tag",
    "encourages_same", "warns_same", "unrelated", "relation_review", "relation_insufficient",
    "require_relation", "no_relation", "time_uncertain", "target_unknown", "stance_unlocated",
    "coverage_failure", "invalid_evidence", "resource_exceeded", "accepted_support",
    "accepted_model_support", "has_support", "has_counter", "referent_conflict",
    "has_uncertainty", "partial_coverage", "model_counter", "unrelated_confirmed",
    "negative_relation_conflict"})
KINDS = {
    "UNLOCATED": ("RULE", "UNCERTAINTY"), "COUNTER_CONTEXT": ("RULE", "COUNTER"),
    "LOCAL_PROMOTION": ("RULE", "SUPPORT"), "MODEL_PROMOTION": ("MODEL", "SUPPORT"),
    "REFERENT_CONFLICT": ("RULE", "UNCERTAINTY"), "TARGET_UNKNOWN": ("RULE", "UNCERTAINTY"),
    "MODEL_COUNTER": ("MODEL", "COUNTER"), "RELATION_UNCERTAIN": ("MODEL", "UNCERTAINTY"),
    "RELATION_MISSING": ("RULE", "UNCERTAINTY"), "TIME_UNCERTAIN": ("RULE", "UNCERTAINTY"),
    "UNLOCATED_COUNTER": ("RULE", "UNCERTAINTY"), "COUNTER_REFERENT_CONFLICT": ("RULE", "UNCERTAINTY")}
Priority = Annotated[int, Field(strict=True, ge=0, le=1000)]
Identifier = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Condition(FrozenModel):
    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    none_of: tuple[str, ...] = ()

    @model_validator(mode="after")
    def known_facts(self):
        if (set(self.all_of) | set(self.any_of) | set(self.none_of)) - FACTS:
            raise ValueError("unknown rule predicate")
        if set(self.all_of) & set(self.none_of):
            raise ValueError("contradictory rule predicates")
        return self

    def matches(self, facts: dict[str, bool]) -> bool:
        keys = set(self.all_of) | set(self.any_of) | set(self.none_of)
        if any(type(facts.get(key)) is not bool for key in keys):
            raise ValueError("referenced rule facts must be booleans")
        return (all(facts[key] for key in self.all_of)
                and (not self.any_of or any(facts[key] for key in self.any_of))
                and not any(facts[key] for key in self.none_of))


class ArgumentRule(FrozenModel):
    id: Identifier
    description: str
    scope: Literal["ACTION", "PAIR", "UNLOCATED_PAIR"]
    kind: str
    priority: Priority
    when: Condition

    @model_validator(mode="after")
    def known_kind(self):
        if self.kind not in KINDS:
            raise ValueError("unknown argument kind")
        return self


class DecisionRule(FrozenModel):
    id: Identifier
    description: str
    priority: Priority
    when: Condition
    judgement: Literal["UNKNOWN", "INSUFFICIENT", "SUPPORTED", "CONFLICTED", "NOT_SUPPORTED"]
    disposition: Literal["RETRY", "REVIEW", "FLAG", "RECHECK", "NONE"]
    reason_code: Identifier

    @model_validator(mode="after")
    def consistent_outcome(self):
        if (self.judgement, self.disposition) not in {
                ("UNKNOWN", "RETRY"), ("UNKNOWN", "RECHECK"), ("INSUFFICIENT", "REVIEW"),
                ("CONFLICTED", "REVIEW"), ("SUPPORTED", "FLAG"), ("NOT_SUPPORTED", "NONE")}:
            raise ValueError("inconsistent judgement and disposition")
        return self


class Limits(FrozenModel):
    max_arguments: Annotated[int, Field(strict=True, ge=1, le=2048)] = 512
    max_attacks: Annotated[int, Field(strict=True, ge=1, le=32768)] = 8192
    max_counterfactuals: Annotated[int, Field(strict=True, ge=0, le=32)] = 8


class RuleSet(FrozenModel):
    schema_version: Literal[1]
    ruleset_id: Identifier
    version: Annotated[str, Field(pattern=r"^\d+\.\d+\.\d+$")]
    limits: Limits
    argument_rules: tuple[ArgumentRule, ...]
    decision_rules: tuple[DecisionRule, ...]

    @model_validator(mode="after")
    def integrity(self):
        rules = self.argument_rules + self.decision_rules
        if len({r.id for r in rules}) != len(rules):
            raise ValueError("duplicate rule ID")
        if {r.kind for r in self.argument_rules} != set(KINDS):
            raise ValueError("every supported argument kind must have a rule")
        # Protect generation as well as routing. Otherwise a valid decision
        # guard can be bypassed by simply suppressing its warning/uncertainty.
        protected_arguments = {
            "A_ACTION_UNLOCATED": ("ACTION", "UNLOCATED", Condition(all_of=("action_unlocated",))),
            "A_LOCAL_COUNTER": ("PAIR", "COUNTER_CONTEXT", Condition(all_of=("same_event", "counter_tag"))),
            "A_REFERENT_CONFLICT": ("PAIR", "REFERENT_CONFLICT", Condition(all_of=("encourages_same", "different_event"))),
            "A_MODEL_TARGET_UNKNOWN": ("PAIR", "TARGET_UNKNOWN", Condition(all_of=("encourages_same", "target_unknown"))),
            "A_MODEL_COUNTER": ("PAIR", "MODEL_COUNTER", Condition(any_of=("warns_same", "unrelated"))),
            "A_RELATION_UNCERTAIN": ("PAIR", "RELATION_UNCERTAIN", Condition(any_of=("relation_review", "relation_insufficient"))),
            "A_RELATION_MISSING": ("PAIR", "RELATION_MISSING", Condition(all_of=("require_relation", "promotion_tag", "no_relation"))),
            "A_UNLINKED_TARGET": ("PAIR", "TARGET_UNKNOWN", Condition(all_of=("promotion_tag", "no_relation"), none_of=("same_event",))),
            "A_TIME_UNCERTAIN": ("PAIR", "TIME_UNCERTAIN", Condition(all_of=("time_uncertain",))),
            "A_STANCE_UNLOCATED": ("UNLOCATED_PAIR", "UNLOCATED", Condition(all_of=("stance_unlocated", "same_event", "promotion_tag"))),
            "A_COUNTER_UNLOCATED": ("UNLOCATED_PAIR", "UNLOCATED_COUNTER", Condition(all_of=("stance_unlocated", "same_event", "counter_tag"))),
            "A_COUNTER_REFERENT_CONFLICT": ("PAIR", "COUNTER_REFERENT_CONFLICT", Condition(all_of=("negative_relation_conflict",))),
            # The support generators are protected too. They are the only path from
            # observed evidence to "this risk is supported"; leaving them pliable
            # means a stricter condition silently erases the risk instead of
            # flagging it, and the tightening survives every other guard.
            "A_LOCAL_PROMOTION": ("PAIR", "LOCAL_PROMOTION", Condition(all_of=("same_event", "promotion_tag"))),
            "A_MODEL_PROMOTION": ("PAIR", "MODEL_PROMOTION", Condition(all_of=("encourages_same",))),
        }
        argument_by_id = {r.id: r for r in self.argument_rules}
        for rid, definition in protected_arguments.items():
            rule = argument_by_id.get(rid)
            if rule is None or (rule.scope, rule.kind, rule.when) != definition:
                raise ValueError(f"protected argument generation is missing or altered: {rid}")
        for rule in self.argument_rules:
            required = {"LOCAL_PROMOTION": {"same_event", "promotion_tag"}, "MODEL_PROMOTION": {"encourages_same"}}.get(rule.kind)
            if required is not None and (rule.scope != "PAIR" or not required <= set(rule.when.all_of)):
                raise ValueError("support rules cannot drop their evidence prerequisites")
        priorities = [r.priority for r in self.decision_rules]
        if len(set(priorities)) != len(priorities):
            raise ValueError("decision priorities must be unique")
        by_id = {r.id: r for r in self.decision_rules}
        default = by_id.get("D_DEFAULT")
        if default is None or default.when != Condition() or default.priority != 0 or (
                default.judgement, default.disposition) != ("NOT_SUPPORTED", "NONE") or default.reason_code != "NO_SUPPORTING_RELATION":
            raise ValueError("a lowest-priority non-supporting default is required")
        guards = {"D_UNAVAILABLE": ("coverage_failure", "UNKNOWN", "RETRY"),
                  "D_RESOURCE": ("resource_exceeded", "INSUFFICIENT", "REVIEW"),
                  "D_INVALID": ("invalid_evidence", "INSUFFICIENT", "REVIEW")}
        for rid, (fact, judgement, disposition) in guards.items():
            rule = by_id.get(rid)
            if rule is None or rule.when != Condition(all_of=(fact,)) or (
                    rule.judgement, rule.disposition) != (judgement, disposition):
                raise ValueError(f"protected failure guard is missing or altered: {rid}")
            expected_reason = {"D_UNAVAILABLE": "MODEL_UNAVAILABLE", "D_RESOURCE": "ARGUMENTATION_RESOURCE_LIMIT",
                               "D_INVALID": "UNVERIFIED_OR_UNLOCATED"}[rid]
            if rule.reason_code != expected_reason:
                raise ValueError(f"protected failure reason is altered: {rid}")
        if not by_id["D_UNAVAILABLE"].priority > by_id["D_RESOURCE"].priority > by_id["D_INVALID"].priority:
            raise ValueError("failure guard precedence must remain unavailable, resource, invalid")
        if min(by_id[rid].priority for rid in guards) <= max(
                r.priority for r in self.decision_rules if r.id not in guards):
            raise ValueError("failure guards must precede ordinary decisions")
        protected = {
            "D_REFERENT_CONFLICT": (Condition(all_of=("has_support", "referent_conflict")), "CONFLICTED", "REVIEW"),
            "D_STANCE_CONFLICT": (Condition(all_of=("has_support", "has_counter")), "CONFLICTED", "REVIEW"),
            "D_UNCERTAIN": (Condition(all_of=("has_uncertainty",)), "INSUFFICIENT", "REVIEW"),
            "D_PARTIAL": (Condition(all_of=("partial_coverage",)), "UNKNOWN", "RECHECK"),
            # Protecting only the conservative branches is not enough: the rules that
            # turn accepted support into a risk decision must exist and keep their
            # conditions, or a supported risk falls through to the default "nothing
            # to do" without any earlier guard noticing.
            "D_MODEL_SUPPORTED": (Condition(all_of=("accepted_support", "accepted_model_support")), "SUPPORTED", "FLAG"),
            "D_LOCAL_SUPPORTED": (Condition(all_of=("accepted_support",)), "SUPPORTED", "FLAG"),
        }
        for rid, (condition, judgement, disposition) in protected.items():
            rule = by_id.get(rid)
            if rule is None or (rule.when, rule.judgement, rule.disposition) != (condition, judgement, disposition):
                raise ValueError(f"protected conservative decision is missing or altered: {rid}")
        for rule in self.decision_rules:
            if rule.disposition == "FLAG" and "accepted_support" not in rule.when.all_of:
                raise ValueError("FLAG requires accepted support")
            if rule.disposition == "NONE" and rule.id != "D_DEFAULT" and (
                    "has_support" not in rule.when.none_of or "has_uncertainty" not in rule.when.none_of):
                raise ValueError("NONE cannot ignore support or uncertainty")
        if by_id["D_UNCERTAIN"].priority <= by_id["D_PARTIAL"].priority:
            raise ValueError("explicit uncertainty must precede incomplete-coverage recheck")
        if any(r.disposition == "NONE" and r.priority >= min(by_id[rid].priority for rid in protected)
               for r in self.decision_rules):
            raise ValueError("non-supporting decisions must follow conservative review rules")
        # A semantic invariant, not only an ID check: with accepted support and no
        # blocking condition the engine must still reach a risk decision. Deleting
        # or widening the support rules would otherwise turn a supported risk into
        # "nothing to do" while every conservative guard above still passes.
        supported = {fact: False for fact in FACTS}
        supported.update(accepted_support=True, has_support=True, accepted_model_support=True)
        ordered = sorted(self.decision_rules, key=lambda r: (-r.priority, r.id))
        winner = next(rule for rule in ordered if rule.when.matches(supported))
        if (winner.judgement, winner.disposition) != ("SUPPORTED", "FLAG"):
            raise ValueError("accepted support must reach a risk decision, "
                             f"not {winner.judgement}/{winner.disposition} via {winner.id}")
        return self

    @cached_property
    def fingerprint(self) -> str:
        encoded = json.dumps(self.model_dump(mode="json"), ensure_ascii=False,
                             sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @cached_property
    def argument_order(self) -> tuple[ArgumentRule, ...]:
        return tuple(sorted(self.argument_rules, key=lambda r: (-r.priority, r.id)))

    @cached_property
    def decision_order(self) -> tuple[DecisionRule, ...]:
        return tuple(sorted(self.decision_rules, key=lambda r: (-r.priority, r.id)))

    def argument_matches(self, scope: str, facts: dict[str, bool]) -> tuple[ArgumentRule, ...]:
        return tuple(r for r in self.argument_order
                     if r.scope == scope and r.when.matches(facts))

    def decision(self, facts: dict[str, bool]) -> tuple[DecisionRule, dict]:
        ordered = self.decision_order
        evaluated = [{"rule_id": r.id, "priority": r.priority, "matched": r.when.matches(facts),
                      "description": r.description} for r in ordered]
        winner = next(r for r, row in zip(ordered, evaluated) if row["matched"])
        return winner, {"selected_rule_id": winner.id, "facts": dict(sorted(facts.items())),
                        "evaluated_rules": evaluated}


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "pead_rules_v1.json"


def load_rules(path: str | Path = DEFAULT_PATH) -> RuleSet:
    """Recursive evidence-removal checks reuse the top-level immutable snapshot."""
    return RuleSet.model_validate_json(Path(path).read_text(encoding="utf-8"))
