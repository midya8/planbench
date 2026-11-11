# The cheap run that failed

PlanBench 0.2 adds a separate exact finite retry-risk API and browser inspector.
The original seeded simulator, default CLI, loader, validator, metrics, reports,
29 original tests and offline demo are retained unchanged. This is not a second
plan project, a new probability algorithm or a production reliability predictor.

## Exact model

The input is one object with `plan`, `tools`, `deadline` and `budget`.
`plan.steps` uses the existing PlanBench names `id`, `tool`, `needs`, `requires`,
`duration` and `max_retries`. A tool registry maps names to `cost`, `failure_rate`
and optional `produces`. Plan name and produces/requires labels are metadata and
input-producibility checks, not data values passed through a real execution.

A step starts once **all direct dependencies** have succeeded. If any failed or
was skipped, the step is skipped at the latest dependency end, with no attempts
or cost. An unrelated branch continues. Every step must succeed for plan success;
there is no goal subset or cancellation. Unlimited workers permit parallel work.

A called tool attempt independently fails with supplied probability q. Each
attempt has the step's fixed duration d and tool's fixed cost c, whether it fails
or succeeds. With r allowed retries, the attempt cap is L=r+1. Success first at
attempt k has mass q^(k-1)(1-q), for 1<=k<=L. Exhaustion has mass q^L and L attempts.
Zero-probability outcomes are omitted. End equals ready+k*d, cost equals k*c.
`start` is **final attempt start** ready+(k-1)*d, matching the legacy simulator's
field, not total-step start. Ready is separately retained. A skipped step has
ready=start=end and cost 0.

The new API uses exact rational strings or integer inputs. It rejects float/bool
values. It does not convert binary floats to allegedly intended decimal numbers.
The original simulator continues to use binary floats and a seeded RNG, so no
same-seed exact-trace correspondence is claimed for rational rates/durations.
Three integer-duration/cost controls have 300 sampled legacy seed traces checked
against the exact support, not a proof of all floating trace equivalence.

## Full histories, joint law and summaries

Native `analyze_risk` follows lexicographic topological order and branches only
on executed steps' positive-mass terminal options. A failed prerequisite prunes
later draws, not their probability mass. Products of independent executed-step
masses give complete history weights. All histories are exported; none are
thresholded away. A shared ancestor's outcome is chosen once, not once per path.

The joint distribution aggregates identical `(plan success, makespan, total cost)`
triples. Makespan is the maximum end of all completed/failed/skipped steps. Cost
is the sum of attempted work, including failed attempts and exhausted steps.
Every time/cost limit is inclusive. Summaries separate:

- probability of plan success;
- probability of time AND cost within limits, regardless of success;
- probability of success AND both limits;
- unconditional expected time/cost;
- expected time/cost **given success**, or null if success has zero mass;
- unconditional per-step succeeded/failed/skipped masses and expected attempts.

For a half-failing prerequisite followed by a five-unit dependent step, time 1 and
cost 1 admit the cheap failed branch with probability 1/2, but admit no successful
run. Plan success is 1/4. For two independent half-failing parallel steps with one
retry each, expected makespan is 7/4 while each step's expected duration is 3/2.
Maximum of means is not mean of maximum. Conditional success time is 14/9.
These are synthetic witnesses, not observed tool reliability or latency.

## Independent browser and evidence

The browser uses BigInt rational arithmetic and **Cartesian potential terminal
assignments for every step**, including later skipped ones. A completion-event
scheduler resolves dependencies. It sums the masses of unused potential outcomes
when histories collapse after skips. This differs from native conditional-prefix
branching, which never samples skipped steps. Both retain the full final history
law. Browser ships only witness inputs, not native reports or reference outputs.
The browser exports the exact input and complete computed report. Both are
replayable through the native CLI, with every fraction/row compared exactly.

39 Python tests retain all 29 originals. Separate native test code enumerates all
potential **Bernoulli attempt bits**, including unused bits after success/skip,
and runs an attempt-completion event queue. It checks 65 seeded small DAGs,
15 probability/retry endpoint settings and chain/fork/join/shared-ancestor controls
against full native histories and joint laws. It derives topological order itself.
Three controls exercise 300 original-simulator seeded traces. Saved 28 reports
cover 260 histories,177 joint atoms, always-fail/succeed, zero cost, null conditional
means, fractional durations, six steps, full retry limits and unrelated work.

Four Node/actual-Chrome tests compare all 28 native/BigInt reports, independent
fair-bit counts for parallel retry controls, all 260 selected histories and 778
step rows,177 joint-table rows,24 responsive views, invalidation, strict input
errors and 2 trusted JSON exports. Complete fractions are exact, not tolerant.
An installed wheel outside the checkout verifies 9 module origins,28 complete
reports, both new CLI entrypoints and original validate/simulate with both gate
sides. The original offline demo remains unchanged and passes.

These are bounded development witnesses, not a held-out field study or universal
correctness proof. Exactness is within this declared finite model, not a confidence
interval on a real service's failure probability.

## Input bounds and use

At most 6 nonempty steps and 6 tools, with at most 2 retries each. Strict unique
ASCII step/tool ids have 1..24 characters. Dependencies must be unique, known and
acyclic. Required inputs must be produced by a **direct dependency**, retaining
the original validator's interpretation, not arbitrary transitive ancestry.
Default duration is 1 and retry count 0; optional needs/requires/produces default
empty. Tool cost and failure rate are required in the exact API. Duration is
positive and at most 100, cost 0..100, failure rate 0..1, deadline/budget 0..10,000.
Every rational has denominator at most 1,000; rational text is at most 24 characters.
Plan names have at most 80 characters. Produces/requires lists have at most 12
strings each of at most 40 characters. Unknown/duplicate JSON keys fail. CLI input
is at most 128 KiB UTF-8; browser JSON has an eight-level syntax nesting limit.
Maximal Cartesian terminal support is 4^6=4,096 before zero-mass pruning. Full
history serialization is extra exponential output, not a scalable inference claim.

```python
from planbench import analyze_risk
report = analyze_risk(spec)
assert report['stats']['mass'] == '1'
```

```sh
python -m planbench.risk_cli --input input.json > report.json
planbench-risk --input input.json > report.json
python scripts/build_risk.py
python -m unittest discover -s tests -v
node --test tests/test_risk.cjs tests/test_risk_browser.cjs
bash scripts/wheel_smoke.sh
```

This exact API is separate from the original normalized float-loaded plan files.
The `tools` mapping is the registry shape returned by legacy loading, but exact
inputs must use integers/rational strings, not its float outputs. Never silently
coerce a legacy loaded float when exact decimal intent is unknown. This is an
analysis API only: it executes no shell commands or real plan actions.

## Boundaries and established sources

No resource contention, backoff, jitter, queueing, timeouts, nonstationary or
correlated outages, shared failure variables, conditional rates, changing attempt
costs or unsafe-side-effect/idempotency model. A reused tool name still denotes
independent calls. Exact constants are supplied, not inferred from telemetry.
There is no production retry recommendation, runtime benchmark, sample-based
estimator or globally optimized plan. Exponential enumeration is deliberate.

- [SciPy geometric-distribution documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.geom.html):
  established first-success probability law. The infinite geometric mean is not
  substituted for bounded retry expectation.
- [Geometric-distribution reference](https://en.wikipedia.org/wiki/Geometric_distribution):
  independent Bernoulli assumptions and trials-versus-failures conventions.
- [Scheduling under Uncertainty: Bounding the Makespan Distribution](https://page.math.tu-berlin.de/~moehring/adm 3-scheduling/paperBoundsOnCmax.pdf):
  prior stochastic-project/DAG critical-path work and mean-of-maximum distinction.
  Our failure/skip extension and finite enumeration do not inherit a theorem or
  broad tractability guarantee from this survey.
- [NetworkX DAG longest path documentation](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.dag_longest_path.html):
  standard topological/critical-path concepts. No NetworkX dependency/code copied.
- [Python fractions documentation](https://docs.python.org/3/library/fractions.html):
  exact rationals and binary-float distinctions.
- [AWS Builders' Library: Timeouts, retries and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/):
  real retry load, correlation and side-effect hazards. This model deliberately
  excludes those mechanisms rather than claiming to solve them.
