import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from planbench import (
    critical_path,
    load_plan,
    load_tools,
    parallelism,
    simulate,
    validate_plan,
)
from planbench.cli import main
from planbench.report import build_report, to_json, to_markdown, to_terminal
from planbench.validate import topological_order

TOOLS = {
    "search": {"cost": 0.1, "failure_rate": 0.0, "produces": ["results"]},
    "llm": {"cost": 0.5, "failure_rate": 0.0, "produces": ["answer"]},
    "flaky": {"cost": 0.2, "failure_rate": 1.0, "produces": ["data"]},
}

PLAN = {
    "name": "t",
    "steps": [
        {"id": "a", "tool": "search", "duration": 2.0},
        {"id": "b", "tool": "llm", "needs": ["a"], "requires": ["results"], "duration": 3.0},
    ],
}


def write_json(tmp, name, obj):
    path = os.path.join(tmp, name)
    with open(path, "w") as fh:
        json.dump(obj, fh)
    return path


class TestLoaders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_load_tools(self):
        path = write_json(self.tmp, "tools.json", {"tools": [
            {"name": "x", "cost": 1, "failure_rate": 0.1, "produces": ["y"]}]})
        registry = load_tools(path)
        self.assertEqual(registry["x"]["cost"], 1.0)
        self.assertEqual(registry["x"]["produces"], ["y"])

    def test_load_tools_defaults(self):
        path = write_json(self.tmp, "tools.json", {"tools": [{"name": "x"}]})
        registry = load_tools(path)
        self.assertEqual(registry["x"]["cost"], 0.0)
        self.assertEqual(registry["x"]["failure_rate"], 0.0)
        self.assertEqual(registry["x"]["produces"], [])

    def test_load_tools_rejects_bad(self):
        for bad in ({"tools": [{"name": "x"} , {"name": "x"}]},
                    {"tools": [{"name": "x", "cost": -1}]},
                    {"tools": [{"name": "x", "failure_rate": 2}]},
                    {"tools": [{"name": "x", "produces": "y"}]},
                    {"tools": "nope"}):
            with self.assertRaises(SystemExit):
                load_tools(write_json(self.tmp, "bad.json", bad))

    def test_load_plan_rejects_bad(self):
        for bad in ({"steps": []},
                    {"steps": [{"tool": "x"}]},
                    {"steps": [{"id": "a"}]},
                    {"steps": [{"id": "a", "tool": "x", "duration": 0}]},
                    {"steps": [{"id": "a", "tool": "x", "max_retries": -1}]},
                    {"steps": [{"id": "a", "tool": "x", "needs": "b"}]}):
            with self.assertRaises(SystemExit):
                load_plan(write_json(self.tmp, "bad.json", bad))

    def test_missing_file(self):
        with self.assertRaises(SystemExit):
            load_plan(os.path.join(self.tmp, "nope.json"))


class TestValidate(unittest.TestCase):
    def test_clean_plan(self):
        self.assertEqual(validate_plan(PLAN, TOOLS), [])

    def test_unknown_tool_and_dependency(self):
        plan = {"name": "t", "steps": [
            {"id": "a", "tool": "nope"},
            {"id": "b", "tool": "search", "needs": ["ghost"]},
        ]}
        kinds = {f.kind for f in validate_plan(plan, TOOLS)}
        self.assertEqual(kinds, {"unknown_tool", "unknown_dependency"})

    def test_duplicate_and_self_dependency(self):
        plan = {"name": "t", "steps": [
            {"id": "a", "tool": "search", "needs": ["a"]},
            {"id": "a", "tool": "search"},
        ]}
        kinds = {f.kind for f in validate_plan(plan, TOOLS)}
        self.assertEqual(kinds, {"duplicate_step_id", "self_dependency"})

    def test_cycle_detected(self):
        plan = {"name": "t", "steps": [
            {"id": "a", "tool": "search", "needs": ["b"]},
            {"id": "b", "tool": "search", "needs": ["a"]},
        ]}
        findings = validate_plan(plan, TOOLS)
        self.assertEqual([f.kind for f in findings], ["dependency_cycle"])
        self.assertEqual(findings[0].severity, "high")

    def test_unproduced_input(self):
        plan = {"name": "t", "steps": [
            {"id": "a", "tool": "search"},
            {"id": "b", "tool": "llm", "needs": ["a"], "requires": ["answer"]},
        ]}
        findings = validate_plan(plan, TOOLS)
        self.assertEqual([f.kind for f in findings], ["unproduced_input"])
        self.assertEqual(findings[0].severity, "medium")

    def test_topological_order(self):
        self.assertEqual(topological_order({"a": [], "b": ["a"], "c": ["a"]}), ["a", "b", "c"])
        self.assertIsNone(topological_order({"a": ["b"], "b": ["a"]}))


class TestSimulate(unittest.TestCase):
    def test_sequential_timing(self):
        result = simulate(PLAN, TOOLS)
        self.assertTrue(result.succeeded)
        self.assertEqual(result.makespan, 5.0)
        self.assertEqual(result.total_cost, 0.6)
        by_id = result.by_id()
        self.assertEqual((by_id["a"].start, by_id["a"].end), (0.0, 2.0))
        self.assertEqual((by_id["b"].start, by_id["b"].end), (2.0, 5.0))

    def test_parallel_timing(self):
        plan = {"name": "p", "steps": [
            {"id": "a", "tool": "search", "duration": 2.0},
            {"id": "b", "tool": "search", "duration": 5.0},
            {"id": "c", "tool": "llm", "needs": ["a", "b"], "duration": 1.0},
        ]}
        result = simulate(plan, TOOLS)
        self.assertEqual(result.makespan, 6.0)
        by_id = result.by_id()
        self.assertEqual(by_id["a"].start, 0.0)
        self.assertEqual(by_id["b"].start, 0.0)
        self.assertEqual(by_id["c"].start, 5.0)

    def test_deterministic_by_seed(self):
        tools = {"flaky50": {"cost": 0.1, "failure_rate": 0.5, "produces": []}}
        plan = {"name": "f", "steps": [{"id": "a", "tool": "flaky50", "max_retries": 5}]}
        r1 = simulate(plan, tools, seed=11)
        r2 = simulate(plan, tools, seed=11)
        self.assertEqual(r1.outcomes[0].attempts, r2.outcomes[0].attempts)
        self.assertEqual(r1.succeeded, r2.succeeded)

    def test_retries_exhausted_fails_and_skips_dependents(self):
        plan = {"name": "f", "steps": [
            {"id": "a", "tool": "flaky", "max_retries": 2},
            {"id": "b", "tool": "search", "needs": ["a"]},
            {"id": "c", "tool": "search", "needs": ["b"]},
        ]}
        result = simulate(plan, TOOLS)
        self.assertFalse(result.succeeded)
        by_id = result.by_id()
        self.assertEqual(by_id["a"].status, "failed")
        self.assertEqual(by_id["a"].attempts, 3)
        self.assertEqual(by_id["b"].status, "skipped")
        self.assertEqual(by_id["c"].status, "skipped")

    def test_retry_cost_accumulates(self):
        plan = {"name": "f", "steps": [{"id": "a", "tool": "flaky", "max_retries": 1}]}
        result = simulate(plan, TOOLS)
        self.assertEqual(result.total_cost, 0.4)

    def test_cycle_raises(self):
        plan = {"name": "c", "steps": [
            {"id": "a", "tool": "search", "needs": ["b"]},
            {"id": "b", "tool": "search", "needs": ["a"]},
        ]}
        with self.assertRaises(ValueError):
            simulate(plan, TOOLS)


class TestMetrics(unittest.TestCase):
    def test_critical_path(self):
        plan = {"name": "p", "steps": [
            {"id": "a", "tool": "search", "duration": 2.0},
            {"id": "b", "tool": "search", "duration": 5.0},
            {"id": "c", "tool": "llm", "needs": ["a", "b"], "duration": 1.0},
        ]}
        duration, path = critical_path(plan)
        self.assertEqual(duration, 6.0)
        self.assertEqual(path, ["b", "c"])
        self.assertAlmostEqual(parallelism(plan), 8.0 / 6.0)

    def test_parallelism_of_sequential_plan_is_one(self):
        self.assertEqual(parallelism(PLAN), 1.0)

    def test_critical_path_cycle_raises(self):
        plan = {"name": "c", "steps": [
            {"id": "a", "tool": "search", "needs": ["b"]},
            {"id": "b", "tool": "search", "needs": ["a"]},
        ]}
        with self.assertRaises(ValueError):
            critical_path(plan)


class TestReport(unittest.TestCase):
    def setUp(self):
        result = simulate(PLAN, TOOLS)
        self.report = build_report(PLAN, [], result)

    def test_json_roundtrip(self):
        parsed = json.loads(to_json(self.report))
        self.assertTrue(parsed["simulation"]["succeeded"])
        self.assertEqual(parsed["simulation"]["critical_path"], ["a", "b"])

    def test_markdown_sections(self):
        md = to_markdown(self.report)
        self.assertIn("| Step | Status |", md)
        self.assertIn("| b | succeeded |", md)

    def test_terminal(self):
        text = to_terminal(self.report)
        self.assertIn("makespan=5.0", text)
        self.assertIn("a -> b", text)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.tools = write_json(self.tmp, "tools.json", {"tools": [
            {"name": "search", "cost": 0.1, "failure_rate": 0.0, "produces": ["results"]},
            {"name": "llm", "cost": 0.5, "failure_rate": 0.0, "produces": ["answer"]},
        ]})
        self.plan = write_json(self.tmp, "plan.json", PLAN)

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_validate_clean(self):
        code, out, _ = self.run_cli(["validate", "--plan", self.plan, "--tools", self.tools])
        self.assertEqual(code, 0)
        self.assertIn("no findings", out)

    def test_validate_findings_fail(self):
        bad = write_json(self.tmp, "bad.json", {"name": "b", "steps": [
            {"id": "a", "tool": "nope"}]})
        code, _, err = self.run_cli(["validate", "--plan", bad, "--tools", self.tools])
        self.assertEqual(code, 1)
        self.assertIn("GATE FAIL", err)

    def test_simulate_writes_reports(self):
        jp = os.path.join(self.tmp, "r.json")
        mp = os.path.join(self.tmp, "r.md")
        code, out, _ = self.run_cli([
            "simulate", "--plan", self.plan, "--tools", self.tools,
            "--json", jp, "--markdown", mp, "--require-success"])
        self.assertEqual(code, 0)
        report = json.load(open(jp))
        self.assertEqual(report["simulation"]["makespan"], 5.0)
        self.assertIn("# PlanBench report", open(mp).read())

    def test_simulate_skipped_on_high_findings(self):
        bad = write_json(self.tmp, "bad.json", {"name": "b", "steps": [
            {"id": "a", "tool": "nope"}]})
        code, out, _ = self.run_cli(["simulate", "--plan", bad, "--tools", self.tools])
        self.assertEqual(code, 1)
        self.assertNotIn("simulation:", out)

    def test_makespan_gate(self):
        argv = ["simulate", "--plan", self.plan, "--tools", self.tools, "--max-makespan"]
        self.assertEqual(self.run_cli(argv + ["6.0"])[0], 0)
        code, _, err = self.run_cli(argv + ["4.0"])
        self.assertEqual(code, 1)
        self.assertIn("makespan", err)

    def test_cost_gate(self):
        argv = ["simulate", "--plan", self.plan, "--tools", self.tools, "--max-cost"]
        self.assertEqual(self.run_cli(argv + ["1.0"])[0], 0)
        self.assertEqual(self.run_cli(argv + ["0.1"])[0], 1)


if __name__ == "__main__":
    unittest.main()
