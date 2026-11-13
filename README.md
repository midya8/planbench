# PlanBench

Validate and simulate agent task plans before they run.

PlanBench checks agent plans - DAGs of tool calls - for structural and semantic errors (unknown tools, unknown or cyclic dependencies, inputs no dependency produces), then simulates their parallel execution deterministically: flaky tools fail with their declared failure rate under a seeded RNG, steps retry within policy, dependents of failed steps are skipped. Reports include makespan, total cost, critical path and parallelism, with CI gates. Dependency-free Python, fully offline.

## Exact retry risk (0.2)

A cheap failed run is not a successful plan. The optional exact-risk API computes
the whole joint success/time/cost law under supplied independent failures and
bounded retries, including exhausted steps, skip cascades and unrelated branches.
The original seeded simulator and CLI remain unchanged.

[Interactive risk inspector](https://midya8.github.io/planbench/) |
[Exact model, limits and sources](RISK.md)

```sh
python -m planbench.risk_cli --input input.json > report.json
planbench-risk --input input.json > report.json
```

The independent browser enumerates potential outcomes and schedules completion
events; native Python branches only on executed steps. All histories and exact
fractions are inspectable and exportable. A supplied six-step bound and at most
two retries keep enumeration deliberately small. No live tool calls occur.

39 Python tests retain all 29 originals; four Node/actual-Chrome tests check 28
complete reports, 260 histories, 177 joint atoms, 24 responsive views and trusted
exports. Installed-wheel checks run outside the source checkout. Supplied rational
assumptions are not production predictions, empirical confidence, resource-aware
scheduling, correlated-outage modeling or a recommendation to retry real calls.

## Validation, simulation and exact risk

Validation checks the plan's structure and declared input production. Simulation
uses one seeded sequence of failures with supplied durations, costs and retry
limits. The separate exact-risk calculation enumerates all positive-probability
histories within its bounds, including failed and skipped branches. None of
these calculations calls real tools or learns their latency or reliability.

The original simulator provides:

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

- The 29 original unit tests cover loader validation, every finding kind, topological ordering including cycles, sequential and parallel timing, seeded determinism, retry exhaustion and skip cascades, cost accumulation, critical path and parallelism, all three report formats, and the CLI end to end including both sides of every gate.
- `bash examples/demo.sh` runs fully offline: a research-agent plan with flaky tools simulates green (retries exercised, real concurrency asserted), a broken plan is rejected, and both gate sides are exercised.
- The current 39-test Python suite includes those originals and the exact-risk checks. Four Node/actual-Chrome tests exercise the independent browser. CI runs Python 3.10-3.13.

Bounds worth stating: durations and failure rates are declared in the fixtures, not learned from real executions - the simulation measures what a plan would do under those assumptions, it does not predict real-world latency. Validation checks structure and producibility, not whether a tool call would actually succeed.

## License

MIT
