# planbench

Agent frameworks happily produce a plan (a DAG of tool calls) and start running it. This checks the plan first and then simulates it, so you find the cycle, the missing tool or the step that needs an input nobody produces before anything real runs. Plain Python, offline.

You give it a plan and a tool registry. Each step has an `id`, a `tool`, optional `needs` (step ids it waits on), `requires` (inputs a dependency must produce), `duration` and `max_retries`. Each tool declares a `cost`, a `failure_rate` and what it `produces`.

```bash
python -m planbench validate --plan examples/data/broken-plan.json --tools examples/data/tools.json
python -m planbench simulate --plan examples/data/plan.json --tools examples/data/tools.json --seed 7
```

The broken example trips four checks (duplicate step id, unknown dependency, unknown tool, unproduced input). The good one is an eight-step research-and-report plan:

```
simulation: succeeded makespan=15.5 cost=0.27 parallelism=1.2593
  critical path: search-b -> fetch-b -> extract -> verify -> report -> notify
  fetch-b          succeeded  attempts=2 [4.0..5.5] cost=0.02
  ...
```

Failures are drawn from a seeded RNG, so the same seed gives the same run. Retries and skipped dependents show up in the trace. For CI there's `--require-success`, `--max-makespan`, `--max-cost` and `--max-findings`, plus `--json` and `--markdown` reports.

## Risk over all outcomes

One simulated run only tells you about one roll of the dice. `python -m planbench.risk_cli --input input.json` (or `planbench-risk`) instead works out the full distribution of success, time and cost across every way the retries could go, for small plans (up to six steps, two retries). RISK.md has the model, and there's an interactive version at https://midya8.github.io/planbench/.

## Caveats

All the durations and failure rates are numbers you supply, so the output is only as good as those guesses. It assumes failures are independent, which real outages usually aren't. Validation checks the plan's shape, not whether a tool call would actually work.

`python -m unittest discover -s tests` runs the 45 tests, and `bash examples/demo.sh` runs both sides of every gate. MIT.
