#!/usr/bin/env bash
# Fully offline PlanBench demo: simulate a research-agent plan with flaky
# tools and retries, reject a broken plan, and exercise both gate sides.
set -u
cd "$(dirname "$0")/.."

OUT="$(mktemp -d /tmp/planbench-demo-XXXX)"
trap 'echo "demo artifacts: $OUT"' EXIT

echo "== validate a clean plan =="
python3 -m planbench validate \
  --plan examples/data/plan.json --tools examples/data/tools.json || { echo "FAIL clean plan rejected"; exit 1; }

echo "== simulate (expect pass) =="
python3 -m planbench simulate \
  --plan examples/data/plan.json --tools examples/data/tools.json --seed 7 \
  --json "$OUT/report.json" --markdown "$OUT/report.md" \
  --require-success --max-makespan 20 --max-cost 1.0 || { echo "FAIL simulation gate that should pass"; exit 1; }

python3 - "$OUT/report.json" <<'PY'
import json, sys
report = json.load(open(sys.argv[1]))
sim = report["simulation"]
assert sim["succeeded"] is True
assert sim["steps"] and all(s["status"] == "succeeded" for s in sim["steps"])
assert sim["makespan"] > 0 and sim["parallelism"] > 1.0  # real concurrency
assert any(s["attempts"] > 1 for s in sim["steps"])  # retries exercised
print("assertions ok: makespan %s, parallelism %s, retries exercised" % (
    sim["makespan"], sim["parallelism"]))
PY

echo "== reject a broken plan (expect fail) =="
if python3 -m planbench validate \
  --plan examples/data/broken-plan.json --tools examples/data/tools.json >/dev/null 2>&1; then
  echo "FAIL broken plan accepted"; exit 1
fi
echo "broken plan rejected as expected"

echo "== gate (expect fail) =="
if python3 -m planbench simulate \
  --plan examples/data/plan.json --tools examples/data/tools.json --seed 7 \
  --max-makespan 1 >/dev/null 2>&1; then
  echo "FAIL gate that should fail"; exit 1
fi
echo "gate failed as expected"

echo "demo ok"
