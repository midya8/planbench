"""Exact-law composition and inclusive policy boundaries on small supplied DAGs."""
import copy
from fractions import Fraction as F
from itertools import product
import unittest

from planbench.risk import analyze


def component(prefix, failure, retries, duration, cost):
    return {
        "plan": {"steps": [
            {"id": prefix + "a", "tool": prefix, "duration": duration,
             "max_retries": retries},
            {"id": prefix + "b", "tool": prefix, "duration": 2,
             "needs": [prefix + "a"]},
        ]},
        "tools": {prefix: {"cost": cost, "failure_rate": failure}},
        "deadline": 9, "budget": 9,
    }


def law(report):
    return {(x["succeeded"], F(x["makespan"]), F(x["total_cost"])):
            F(x["probability"]) for x in report["joint"]}


class CompositionTests(unittest.TestCase):
    def test_disjoint_parallel_components_convolve_cost_and_max_time(self):
        # An independent branch still runs when another branch has failed.
        configs = [("0", 0, 1, "1/2"), ("1/2", 1, "3/2", "2/3"),
                   ("1", 2, 2, 1)]
        for left, right in product(configs, repeat=2):
            with self.subTest(left=left, right=right):
                a = component("x", *left)
                b = component("y", *right)
                merged = copy.deepcopy(a)
                merged["plan"]["steps"] += b["plan"]["steps"]
                merged["tools"].update(b["tools"])
                ra, rb, got = analyze(a), analyze(b), analyze(merged)
                expected = {}
                for (sa, ta, ca), pa in law(ra).items():
                    for (sb, tb, cb), pb in law(rb).items():
                        key = (sa and sb, max(ta, tb), ca + cb)
                        expected[key] = expected.get(key, F(0)) + pa * pb
                self.assertEqual(law(got), expected)
                self.assertEqual(F(got["stats"]["success_probability"]),
                                 F(ra["stats"]["success_probability"]) *
                                 F(rb["stats"]["success_probability"]))
                self.assertEqual(F(got["stats"]["expected_cost"]),
                                 F(ra["stats"]["expected_cost"]) +
                                 F(rb["stats"]["expected_cost"]))
                by_id = {s["id"]: s for s in got["step_laws"]}
                for r in [ra, rb]:
                    for s in r["step_laws"]:
                        self.assertEqual(by_id[s["id"]], s)

    def test_policy_boundaries_include_atoms_without_changing_the_law(self):
        s = component("x", "1/2", 2, "3/2", "2/3")
        s["plan"]["steps"].append(
            {"id": "xc", "tool": "x", "duration": 1})
        original = copy.deepcopy(s)
        baseline = analyze(s)
        atoms = law(baseline)
        times = sorted({F(0)} | {t for _, t, _ in atoms})
        costs = sorted({F(0)} | {c for _, _, c in atoms})
        # Probe at and just below every attainable boundary. All values are
        # rational inputs accepted by the API, with no floating-point rounding.
        deadlines = sorted(set(times + [t - F(1, 12) for t in times if t]))
        budgets = sorted(set(costs + [c - F(1, 12) for c in costs if c]))
        within_by_policy = {}
        for deadline, budget in product(deadlines, budgets):
            with self.subTest(deadline=deadline, budget=budget):
                candidate = copy.deepcopy(s)
                candidate.update(deadline=str(deadline), budget=str(budget))
                r = analyze(candidate)
                self.assertEqual(r["joint"], baseline["joint"])
                self.assertEqual(r["histories"], baseline["histories"])
                self.assertEqual(r["step_laws"], baseline["step_laws"])
                within = sum((p for (_, t, c), p in atoms.items()
                              if t <= deadline and c <= budget), F(0))
                success = sum((p for (ok, t, c), p in atoms.items()
                               if ok and t <= deadline and c <= budget), F(0))
                self.assertEqual(F(r["stats"]["within_probability"]), within)
                self.assertEqual(F(r["stats"]["success_within_probability"]), success)
                within_by_policy[deadline, budget] = (within, success)
        for i, deadline in enumerate(deadlines):
            for j, budget in enumerate(budgets):
                here = within_by_policy[deadline, budget]
                for previous in ([within_by_policy[deadlines[i-1], budget]] if i else []) + ([within_by_policy[deadline, budgets[j-1]]] if j else []):
                    self.assertTrue(all(a <= b for a, b in zip(previous, here)))
        self.assertEqual(s, original)
        self.assertEqual(within_by_policy[deadlines[-1], budgets[-1]],
                         (F(1), F(baseline["stats"]["success_probability"])))
