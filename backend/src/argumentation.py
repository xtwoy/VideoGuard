"""Production PyArg solver with NetworkX explanations. No silent fallback."""
from __future__ import annotations

from importlib.metadata import version
from functools import lru_cache
import networkx as nx
from py_arg.abstract_argumentation_classes.abstract_argumentation_framework import AbstractArgumentationFramework
from py_arg.abstract_argumentation_classes.argument import Argument
from py_arg.abstract_argumentation_classes.defeat import Defeat
from py_arg.algorithms.semantics.get_grounded_extension import get_grounded_extension


class ArgumentationLimitError(ValueError):
    """Graph overflow requires review, never assumed acceptance."""


@lru_cache(maxsize=1)
def _versions() -> tuple[str, str]:
    return version("python-argumentation"), version("networkx")


def backend_info() -> dict:
    pyarg_version, graph_version = _versions()
    return {"name": "PyArg", "distribution": "python-argumentation",
            "version": pyarg_version,
            "graph_library": "NetworkX", "graph_version": graph_version,
            "semantics": "grounded", "fallback": False}


def grounded(arguments: list[str], attacks: list[tuple[str, str]], *,
             max_arguments: int = 512, max_attacks: int = 8192) -> dict:
    if any(not isinstance(a, str) or not a for a in arguments) or len(set(arguments)) != len(arguments):
        raise ValueError("argument IDs must be unique nonempty strings")
    names = set(arguments)
    if any(source not in names or target not in names for source, target in attacks):
        raise ValueError("attack endpoints must exist")
    edges = sorted(set(attacks))
    if len(names) > max_arguments or len(edges) > max_attacks:
        raise ArgumentationLimitError("argument graph exceeds configured resource limits")
    objects = {name: Argument(name) for name in sorted(names)}
    framework = AbstractArgumentationFramework(
        "videoguard-event", list(objects.values()),
        [Defeat(objects[source], objects[target]) for source, target in edges])
    accepted = {argument.name for argument in get_grounded_extension(framework)}
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(names))
    graph.add_edges_from(edges)
    rejected = {target for source in accepted for target in graph.successors(source)}
    labels = {name: "IN" if name in accepted else "OUT" if name in rejected else "UNDECIDED"
              for name in sorted(names)}
    cycles = sorted((sorted(component) for component in nx.strongly_connected_components(graph)
                     if len(component) > 1 or any(graph.has_edge(n, n) for n in component)),
                    key=lambda component: tuple(component))
    explanations = {}
    for name in sorted(names):
        attackers = sorted(graph.predecessors(name))
        explanations[name] = {
            "label": labels[name], "attacker_ids": attackers,
            "defeated_by": sorted(set(attackers) & accepted),
            "defenses": [{"attacker_id": a,
                          "accepted_defender_ids": sorted(set(graph.predecessors(a)) & accepted)}
                         for a in attackers],
            "unresolved_attacker_ids": [a for a in attackers if labels[a] == "UNDECIDED"]}
    return {"accepted": sorted(accepted), "rejected": sorted(rejected),
            "undecided": sorted(names - accepted - rejected), "labels": labels,
            "backend": backend_info(), "executed": True,
            "cycles": cycles, "explanations": explanations,
            "statistics": {"arguments": len(names), "attacks": len(edges),
                           "weak_components": nx.number_weakly_connected_components(graph)}}
