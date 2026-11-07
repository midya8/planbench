# PlanBench

Validate and simulate agent task plans before they run.

PlanBench checks agent plans - DAGs of tool calls - for structural and semantic errors (unknown tools, unknown or cyclic dependencies, inputs no dependency produces), then simulates their parallel execution deterministically: flaky tools fail with their declared failure rate under a seeded RNG, steps retry within policy, dependents of failed steps are skipped. Reports include makespan, total cost, critical path and parallelism, with CI gates. Dependency-free Python, fully offline.

## Why

Agent plans fail in boring ways that are cheap to catch before execution: a step calls a tool that does not exist, waits on an input nobody produces, or sits in a dependency cycle. And plans that look fine on paper miss their budgets once real tool latency, failures and retries are accounted for. PlanBench catches both:

- **semantic validation** - duplicate step ids, unknown tools, unknown or cyclic dependencies, and `requires` inputs no dependency's tool produces;
- **deterministic parallel simulation** - steps start when their dependencies succeed; tool failures are drawn from a seeded RNG so the same plan, registry and seed always produce the same trace; retries and skip cascades are explicit in the report;
- **plan-shape metrics** - makespan, total cost (including retry cost), critical path by duration, and parallelism (total work over critical path);
- **CI gates** - `--require-success`, `--max-makespan`, `--max-cost`, `--max-findings` fail the pipeline when a plan stops meeting policy.

## Usage

```bash
python3 -m planbench validate --plan plan.json --tools tools.json
python3 -m planbench simulate --plan plan.json --tools tools.json --seed 7 \
  --json report.json --markdown report.md --require-success --max-makespan 20 --max-cost 1.0
```

Plans are JSON: each step has an `id`, a `tool`, optional `needs` (dependency step ids), `requires` (input names a dependency must produce), `duration` and `max_retries`. The tool registry declares each tool's `cost`, `failure_rate` and `produces`.

## Verification

- 29 unit tests cover loader validation, every finding kind, topological ordering including cycles, sequential and parallel timing, seeded determinism, retry exhaustion and skip cascades, cost accumulation, critical path and parallelism, all three report formats, and the CLI end to end including both sides of every gate.
- `bash examples/demo.sh` runs fully offline: a research-agent plan with flaky tools simulates green (retries exercised, real concurrency asserted), a broken plan is rejected, and both gate sides are exercised.
- CI runs the same suite across Python 3.10-3.13.

Bounds worth stating: durations and failure rates are declared in the fixtures, not learned from real executions - the simulation measures what a plan would do under those assumptions, it does not predict real-world latency. Validation checks structure and producibility, not whether a tool call would actually succeed.

## License

MIT
