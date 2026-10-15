"""Small independently implemented Dung grounded-semantics kernel.

The least fixed point contains skeptically accepted arguments. Cyclic attacks
remain undecided; they are not resolved by vote counts or model confidence.
Reference concepts: PyArg abstract argumentation and Argdown support/attack.
"""
from __future__ import annotations


def grounded(arguments: list[str], attacks: list[tuple[str, str]]) -> dict:
    if any(not isinstance(a, str) or not a for a in arguments) or len(set(arguments)) != len(arguments):
        raise ValueError("argument IDs must be unique nonempty strings")
    names = set(arguments)
    if any(source not in names or target not in names for source, target in attacks):
        raise ValueError("attack endpoints must exist")
    incoming = {name: set() for name in names}
    outgoing = {name: set() for name in names}
    for source, target in attacks:
        incoming[target].add(source)
        outgoing[source].add(target)
    accepted: set[str] = set()
    steps = [sorted(accepted)]
    while True:
        defeated = {target for source in accepted for target in outgoing[source]}
        following = {name for name in names if incoming[name].issubset(defeated)}
        if following == accepted:
            break
        if not accepted.issubset(following):
            raise RuntimeError("grounded fixed point must grow monotonically")
        accepted = following
        steps.append(sorted(accepted))
    rejected = {target for source in accepted for target in outgoing[source]}
    return {"accepted": sorted(accepted), "rejected": sorted(rejected),
            "undecided": sorted(names - accepted - rejected), "iterations": steps,
            "labels": {name: "IN" if name in accepted else "OUT" if name in rejected else "UNDECIDED"
                       for name in sorted(names)}}
