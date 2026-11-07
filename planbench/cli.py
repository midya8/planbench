"""PlanBench command line: validate plans and simulate their execution."""

from __future__ import annotations

import argparse
import sys

from .loader import load_plan, load_tools
from .report import build_report, to_json, to_markdown, to_terminal
from .simulate import simulate
from .validate import validate_plan


def _run(args: argparse.Namespace) -> tuple[dict, int]:
    plan = load_plan(args.plan)
    tools = load_tools(args.tools)
    findings = validate_plan(plan, tools)
    result = None
    if args.command == "simulate" and not any(f.severity == "high" for f in findings):
        result = simulate(plan, tools, seed=args.seed)
    report = build_report(plan, findings, result)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            fh.write(to_json(report))
    if args.markdown_path:
        with open(args.markdown_path, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(report))
    print(to_terminal(report))

    failures: list[str] = []
    high = [f for f in findings if f.severity == "high"]
    if high:
        failures.append(f"{len(high)} high-severity validation finding(s)")
    if args.max_findings is not None and len(findings) > args.max_findings:
        failures.append(f"{len(findings)} findings > {args.max_findings}")
    if result is not None:
        if args.require_success and not result.succeeded:
            failures.append("simulation did not succeed")
        if args.max_makespan is not None and result.makespan > args.max_makespan:
            failures.append(f"makespan {result.makespan:.4f} > {args.max_makespan}")
        if args.max_cost is not None and result.total_cost > args.max_cost:
            failures.append(f"total cost {result.total_cost:.4f} > {args.max_cost}")
    for failure in failures:
        print(f"GATE FAIL: {failure}", file=sys.stderr)
    return report, 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="planbench",
        description="Validate and simulate agent task plans.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("validate", "check plan structure and dependencies"),
                            ("simulate", "run a deterministic parallel simulation")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--plan", required=True, help="plan JSON file")
        p.add_argument("--tools", required=True, help="tool registry JSON file")
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--json", dest="json_path", default=None)
        p.add_argument("--markdown", dest="markdown_path", default=None)
        p.add_argument("--max-findings", type=int, default=None)
        if name == "simulate":
            p.add_argument("--require-success", action="store_true")
            p.add_argument("--max-makespan", type=float, default=None)
            p.add_argument("--max-cost", type=float, default=None)
    args = parser.parse_args(argv)
    _, code = _run(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
