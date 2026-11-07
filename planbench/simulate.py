"""Deterministic discrete-event plan simulation.

Steps run in parallel as soon as their dependencies succeed. Tool calls fail
independently with the tool's failure_rate, driven by a seeded RNG, and are
retried up to the step's max_retries. A step whose attempts are exhausted
fails; its dependents are skipped. The same plan, tools and seed always
produce the same trace.
"""

from __future__ import annotations

import heapq
import random
from dataclasses import dataclass, field

from .validate import topological_order


@dataclass
class StepOutcome:
    step_id: str
    status: str  # "succeeded", "failed", "skipped"
    attempts: int
    start: float
    end: float
    cost: float


@dataclass
class SimulationResult:
    outcomes: list[StepOutcome]
    makespan: float
    total_cost: float
    succeeded: bool

    def by_id(self) -> dict[str, StepOutcome]:
        return {o.step_id: o for o in self.outcomes}


def simulate(plan: dict, tools: dict[str, dict], seed: int = 0) -> SimulationResult:
    """Run the plan to completion. Assumes validate_plan found no cycles or
    unknown dependencies; call validate first."""
    rng = random.Random(seed)
    steps = {s["id"]: s for s in plan["steps"]}
    graph = {sid: [d for d in s.get("needs", []) if d in steps] for sid, s in steps.items()}
    order = topological_order(graph)
    if order is None:
        raise ValueError("plan contains a dependency cycle")

    outcomes: dict[str, StepOutcome] = {}
    # event queue of (start_time, seq, step_id, attempt)
    events: list[tuple[float, int, str, int]] = []
    seq = 0
    remaining_deps = {sid: len(deps) for sid, deps in graph.items()}
    dependents: dict[str, list[str]] = {sid: [] for sid in steps}
    for sid, deps in graph.items():
        for dep in deps:
            dependents[dep].append(sid)
    blocked = set()  # steps whose dependency failed or was skipped

    def schedule(sid: str, ready_at: float) -> None:
        nonlocal seq
        if sid in blocked:
            outcomes[sid] = StepOutcome(sid, "skipped", 0, ready_at, ready_at, 0.0)
            finish(sid, ready_at)
            return
        step = steps[sid]
        seq += 1
        heapq.heappush(events, (ready_at, seq, sid, 1))

    def finish(sid: str, end: float) -> None:
        for child in dependents[sid]:
            remaining_deps[child] -= 1
            if outcomes[sid].status != "succeeded":
                blocked.add(child)
            if remaining_deps[child] == 0:
                # ready when the slowest dependency finished
                dep_ends = [outcomes[d].end for d in graph[child]]
                schedule(child, max(dep_ends) if dep_ends else end)

    for sid in order:
        if not graph[sid]:
            schedule(sid, 0.0)

    clock = 0.0
    while events:
        start, _, sid, attempt = heapq.heappop(events)
        clock = max(clock, start)
        step = steps[sid]
        spec = tools[step["tool"]]
        end = clock + float(step.get("duration", 1.0))
        failed = rng.random() < spec["failure_rate"]
        if failed and attempt <= step.get("max_retries", 0):
            seq += 1
            heapq.heappush(events, (end, seq, sid, attempt + 1))
            continue
        status = "failed" if failed else "succeeded"
        outcomes[sid] = StepOutcome(sid, status, attempt, clock, end,
                                    spec["cost"] * attempt)
        finish(sid, end)

    # preserve plan order in the report
    ordered = [outcomes[sid] for sid in order if sid in outcomes]
    makespan = max((o.end for o in ordered), default=0.0)
    return SimulationResult(
        outcomes=ordered,
        makespan=makespan,
        total_cost=sum(o.cost for o in ordered),
        succeeded=all(o.status == "succeeded" for o in ordered),
    )
