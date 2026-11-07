"""Plan-shape metrics: critical path and parallelism."""

from __future__ import annotations

from .validate import topological_order


def critical_path(plan: dict) -> tuple[float, list[str]]:
    """Longest dependency chain by summed duration. Returns (duration, ids).
    Assumes the plan is acyclic (validate first)."""
    steps = {s["id"]: s for s in plan["steps"]}
    graph = {sid: [d for d in s.get("needs", []) if d in steps] for sid, s in steps.items()}
    order = topological_order(graph)
    if order is None:
        raise ValueError("plan contains a dependency cycle")
    best: dict[str, tuple[float, list[str]]] = {}
    for sid in order:
        duration = float(steps[sid].get("duration", 1.0))
        if not graph[sid]:
            best[sid] = (duration, [sid])
        else:
            dep_dur, dep_path = max((best[d] for d in graph[sid]), key=lambda bp: (bp[0], bp[1]))
            best[sid] = (dep_dur + duration, dep_path + [sid])
    return max(best.values(), key=lambda bp: (bp[0], bp[1]))


def parallelism(plan: dict) -> float:
    """Ratio of total step work to critical-path duration. 1.0 means fully
    sequential; higher means more concurrency is available."""
    total = sum(float(s.get("duration", 1.0)) for s in plan["steps"])
    cp, _ = critical_path(plan)
    return total / cp if cp > 0 else 0.0
