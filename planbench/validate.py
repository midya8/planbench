"""Semantic plan validation: duplicate ids, unknown tools, unknown or cyclic
dependencies, and steps whose required inputs no dependency produces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    severity: str  # "high" or "medium"
    kind: str
    step: str | None
    message: str


def validate_plan(plan: dict, tools: dict[str, dict]) -> list[Finding]:
    findings: list[Finding] = []
    steps = plan["steps"]

    seen: set[str] = set()
    for step in steps:
        if step["id"] in seen:
            findings.append(Finding("high", "duplicate_step_id", step["id"],
                                    f"duplicate step id '{step['id']}'"))
        seen.add(step["id"])
        if step["tool"] not in tools:
            findings.append(Finding("high", "unknown_tool", step["id"],
                                    f"step '{step['id']}' uses unknown tool '{step['tool']}'"))

    ids = {s["id"] for s in steps}
    for step in steps:
        for dep in step.get("needs", []):
            if dep == step["id"]:
                findings.append(Finding("high", "self_dependency", step["id"],
                                        f"step '{step['id']}' depends on itself"))
            elif dep not in ids:
                findings.append(Finding("high", "unknown_dependency", step["id"],
                                        f"step '{step['id']}' needs unknown step '{dep}'"))

    # cycle detection over known ids only
    graph = {s["id"]: [d for d in s.get("needs", []) if d in ids] for s in steps}
    order = topological_order(graph)
    if order is None:
        findings.append(Finding("high", "dependency_cycle", None,
                                "plan contains a dependency cycle"))

    # producibility: every required input name must be produced by the tool
    # of at least one dependency (or the step needs nothing)
    for step in steps:
        spec = tools.get(step["tool"])
        if spec is None:
            continue
        produced = set()
        for dep in step.get("needs", []):
            dep_step = next((s for s in steps if s["id"] == dep), None)
            if dep_step and dep_step["tool"] in tools:
                produced.update(tools[dep_step["tool"]]["produces"])
        required = step.get("requires", [])
        if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
            findings.append(Finding("high", "invalid_requires", step["id"],
                                    f"step '{step['id']}': requires must be a list of strings"))
            continue
        for req in required:
            if req not in produced:
                findings.append(Finding("medium", "unproduced_input", step["id"],
                                        f"step '{step['id']}' requires '{req}' but no dependency produces it"))

    findings.sort(key=lambda f: (f.severity != "high", f.kind, f.step or ""))
    return findings


def topological_order(graph: dict[str, list[str]]) -> list[str] | None:
    """Kahn's algorithm over edges id -> its dependencies. Returns a valid
    execution order (dependencies first), or None on a cycle."""
    indegree = {node: 0 for node in graph}
    dependents: dict[str, list[str]] = {node: [] for node in graph}
    for node, deps in graph.items():
        for dep in deps:
            if dep in graph:
                indegree[node] += 1
                dependents[dep].append(node)
    ready = sorted(n for n, d in indegree.items() if d == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in sorted(dependents[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    return order if len(order) == len(graph) else None
