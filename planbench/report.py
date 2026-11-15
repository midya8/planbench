"""Terminal, JSON and Markdown reports for validation and simulation."""

from __future__ import annotations

import json
import math

from .metrics import critical_path, parallelism
from .simulate import SimulationResult
from .validate import Finding


def build_report(plan: dict, findings: list[Finding], result: SimulationResult | None) -> dict:
    report = {
        "plan": plan.get("name", "unnamed"),
        "steps": len(plan["steps"]),
        "findings": [
            {"severity": f.severity, "kind": f.kind, "step": f.step, "message": f.message}
            for f in findings
        ],
    }
    if result is not None:
        cp_duration, cp_steps = critical_path(plan)
        report["simulation"] = {
            "succeeded": result.succeeded,
            "makespan": round(result.makespan, 4),
            "total_cost": round(result.total_cost, 4),
            "critical_path_duration": round(cp_duration, 4),
            "critical_path": cp_steps,
            "parallelism": round(parallelism(plan), 4),
            "steps": [
                {"id": o.step_id, "status": o.status, "attempts": o.attempts,
                 "start": round(o.start, 4), "end": round(o.end, 4), "cost": round(o.cost, 4)}
                for o in result.outcomes
            ],
        }
    def check(value):
        if isinstance(value, dict):
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError('simulation report exceeds finite numerical range')
    check(report)
    return report


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"


def to_markdown(report: dict) -> str:
    lines = [f"# PlanBench report: {report['plan']}", ""]
    if report["findings"]:
        lines += ["## Findings", "", "| Severity | Kind | Step | Message |", "|---|---|---|---|"]
        for f in report["findings"]:
            step = f["step"] or "-"
            lines.append(f"| {f['severity']} | {f['kind']} | {step} | {f['message']} |")
        lines.append("")
    else:
        lines += ["No validation findings.", ""]
    sim = report.get("simulation")
    if sim:
        lines += [
            "## Simulation", "",
            f"- Succeeded: {'yes' if sim['succeeded'] else 'no'}",
            f"- Makespan: {sim['makespan']}",
            f"- Total cost: {sim['total_cost']}",
            f"- Critical path ({sim['critical_path_duration']}): {' -> '.join(sim['critical_path'])}",
            f"- Parallelism: {sim['parallelism']}",
            "",
            "| Step | Status | Attempts | Start | End | Cost |",
            "|---|---|---|---|---|---|",
        ]
        for s in sim["steps"]:
            lines.append(f"| {s['id']} | {s['status']} | {s['attempts']} | {s['start']} | {s['end']} | {s['cost']} |")
        lines.append("")
    return "\n".join(lines)


def to_terminal(report: dict) -> str:
    lines = [f"plan: {report['plan']} ({report['steps']} steps)"]
    for f in report["findings"]:
        lines.append(f"  [{f['severity']}] {f['kind']}: {f['message']}")
    if not report["findings"]:
        lines.append("  no findings")
    sim = report.get("simulation")
    if sim:
        lines.append(f"simulation: {'succeeded' if sim['succeeded'] else 'FAILED'} "
                     f"makespan={sim['makespan']} cost={sim['total_cost']} parallelism={sim['parallelism']}")
        lines.append(f"  critical path: {' -> '.join(sim['critical_path'])}")
        for s in sim["steps"]:
            lines.append(f"  {s['id']:<16} {s['status']:<10} attempts={s['attempts']} "
                         f"[{s['start']}..{s['end']}] cost={s['cost']}")
    return "\n".join(lines)
