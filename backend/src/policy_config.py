"""Validated policy configuration.

The PEAD rule set protects itself with `RuleSet.integrity()`. The ten risk policies
live in a plain JSON file and had no equivalent guard, so emptying one policy's
`action_tags` silently replaced "risk found" with "nothing to do" — the same class of
bypass the rule set already rejects.

These constraints keep that path open in one direction only: a policy may add evidence
tags or become *more* cautious, but it cannot drop the minimum recognition path or
weaken a high-severity disposition without failing to load.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DISPOSITIONS = frozenset({"FLAG", "REVIEW", "VERIFY_EXTERNAL", "RECHECK", "RETRY", "NONE"})
# Ordering used to check that a disposition is at least as severe as required.
SEVERITY = {"NONE": 0, "RECHECK": 1, "RETRY": 1, "VERIFY_EXTERNAL": 2, "REVIEW": 3, "FLAG": 4}

# Every policy that must exist, with the evidence tags it must still be able to see
# and — only for the config-driven policies — the weakest disposition it may map them
# to. `None` means the code decides the disposition, so there is nothing to protect in
# the JSON beyond the tags.
PROTECTED = {
    "R_DANGER_PROMOTION": (frozenset({"danger_action", "danger_description"}), None),
    "R_VIOLENCE": (frozenset({"violence"}), None),
    "R_PRIVACY_EXPOSURE": (frozenset({"pii_candidate"}), None),
    "R_MARKETING_CLAIM": (frozenset({"credential_claim"}), None),
    "R_SELF_HARM": (frozenset({"self_harm_action", "self_harm_instruction"}), "FLAG"),
    "R_SEXUAL_CONTENT": (frozenset({"sexual_content"}), "FLAG"),
    "R_HATE_HARASSMENT": (frozenset({"hate_or_harassment"}), "REVIEW"),
    "R_FRAUD_SCAM": (frozenset({"fraud_or_scam"}), "REVIEW"),
    "R_CONTROLLED_GOODS": (frozenset({"controlled_goods"}), "REVIEW"),
    "R_MINORS_PROTECTION": (frozenset({"minor_risk"}), "FLAG"),
}

# Which observations a policy needs before "no cue" may be read as "nothing found".
# Omitted modalities do not make a policy stricter than it claims to be.
REQUIRED_MODALITIES = {
    "R_VIOLENCE": frozenset({"visual"}),
    "R_PRIVACY_EXPOSURE": frozenset({"visual", "screen_text", "speech"}),
    "R_MARKETING_CLAIM": frozenset({"visual", "screen_text", "speech"}),
    "R_SELF_HARM": frozenset({"visual", "speech"}),
    "R_SEXUAL_CONTENT": frozenset({"visual"}),
    "R_HATE_HARASSMENT": frozenset({"speech"}),
    "R_FRAUD_SCAM": frozenset({"speech", "screen_text"}),
    "R_CONTROLLED_GOODS": frozenset({"visual", "screen_text", "speech"}),
    "R_MINORS_PROTECTION": frozenset({"visual", "speech"}),
}

MODALITY_STATES = frozenset({"FULL", "PARTIAL", "UNKNOWN"})


class PolicyEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    action_tags: list[str] = Field(default_factory=list)
    context_tags: list[str] = Field(default_factory=list)
    disposition: str | None = None
    reason_code: str | None = None
    max_relation_gap_ms: int | None = None

    @field_validator("disposition")
    @classmethod
    def _known_disposition(cls, value):
        if value is not None and value not in DISPOSITIONS:
            raise ValueError(f"policy disposition must be one of {sorted(DISPOSITIONS)}")
        return value


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    policy_version: str
    policies: dict[str, PolicyEntry]

    @model_validator(mode="after")
    def integrity(self):
        missing = set(PROTECTED) - set(self.policies)
        if missing:
            raise ValueError(f"policy configuration is missing required policies: {sorted(missing)}")
        unknown = set(self.policies) - set(PROTECTED)
        if unknown:
            # A new policy is allowed, but it must be declared here so its minimum
            # recognition path is reviewed instead of silently defaulting to nothing.
            raise ValueError(f"undeclared policy ids: {sorted(unknown)}")
        for policy_id, (required_tags, weakest) in PROTECTED.items():
            entry = self.policies[policy_id]
            # Subset rather than equality: adding tags is a conservative change and is
            # allowed; removing one is how a risk quietly disappears.
            dropped = required_tags - set(entry.action_tags)
            if dropped:
                raise ValueError(
                    f"{policy_id} 删除了必需的风险线索 {sorted(dropped)}："
                    "合法配置不得让已有风险无法被识别")
            disposition = entry.disposition
            if weakest is not None and disposition is not None and SEVERITY[disposition] < SEVERITY[weakest]:
                raise ValueError(
                    f"{policy_id} 的处置 {disposition} 弱于最低要求 {weakest}："
                    "不得通过配置降级高风险处置")
        return self


def validate_policies(document: dict) -> dict:
    """Validate a loaded document and return its plain ``policies`` mapping."""
    validated = PolicyConfig.model_validate(document)
    return {policy_id: entry.model_dump(exclude_none=True)
            for policy_id, entry in validated.policies.items()}


def required_modalities(policy_id: str) -> frozenset[str]:
    return REQUIRED_MODALITIES.get(policy_id, frozenset())


def load_document(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
