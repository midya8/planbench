"""Finite input and output controls for the original simulator, not risk forecasts."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from planbench.cli import main
from planbench.loader import load_plan, load_tools
from planbench.report import build_report, to_json
from planbench.simulate import simulate


class FiniteInputTests(unittest.TestCase):
    def files(self, root, duration=1., cost=0., rate=0., retries=0):
        plan, tools = root/'plan.json', root/'tools.json'
        plan.write_text(json.dumps({'steps': [{'id': 'a', 'tool': 'x',
            'duration': duration, 'max_retries': retries}]}))
        tools.write_text(json.dumps({'tools': [{'name': 'x', 'cost': cost,
                                               'failure_rate': rate}]}))
        return plan, tools

    def test_loaders_refuse_nonfinite_boolean_and_overlarge_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for field, loader in [('duration', load_plan), ('cost', load_tools), ('rate', load_tools)]:
                for value in [True, False, float('nan'), float('inf'), -float('inf'), 10**1000]:
                    plan, tools = self.files(root, **{field: value})
                    with self.subTest(field=field, value=str(value)[:25]):
                        with self.assertRaises(SystemExit):
                            loader(plan if field == 'duration' else tools)
            for value in [True, False, .5, -1]:
                plan, _ = self.files(root, retries=value)
                with self.assertRaises(SystemExit):
                    load_plan(plan)
            for duration, cost, rate in [(1, 0, 0), (1e-100, 1e100, 1), (2.5, .1, .3)]:
                plan, tools = self.files(root, duration, cost, rate)
                self.assertEqual(load_plan(plan)['steps'][0]['duration'], duration)
                self.assertEqual(load_tools(tools)['x']['cost'], cost)

    def test_bad_gates_stop_before_loading_or_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = root/'report.json'
            for flag in ['--max-cost', '--max-makespan', '--max-findings']:
                for value in (['nan', 'inf', '-1'] if flag != '--max-findings' else ['-1']):
                    capture = io.StringIO()
                    with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                        code = main(['simulate', '--plan', str(root/'absent'),
                            '--tools', str(root/'absent'), '--json', str(out), flag+'='+value])
                    self.assertEqual(code, 2, capture.getvalue())
                    self.assertIn('finite and non-negative', capture.getvalue())
                    self.assertFalse(out.exists())

    def test_finite_inputs_can_overflow_report_but_cannot_pass_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, tools = self.files(root, duration=1e308, cost=1e308)
            data = json.loads(plan.read_text())
            data['steps'].append({'id': 'b', 'tool': 'x', 'needs': ['a'], 'duration': 1e308})
            plan.write_text(json.dumps(data))
            loaded, registry = load_plan(plan), load_tools(tools)
            with self.assertRaisesRegex(ValueError, 'finite numerical range'):
                build_report(loaded, [], simulate(loaded, registry))
            out = root/'report.json'
            result = subprocess.run([sys.executable, '-m', 'planbench', 'simulate',
                '--plan', str(plan), '--tools', str(tools), '--json', str(out)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('finite numerical range', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertFalse(out.exists())
            with self.assertRaises(ValueError):
                to_json({'cost': float('nan')})

    def test_finite_boundaries_and_gate_sides_still_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, tools = self.files(root, duration=2, cost=.5)
            for bound, expected in [('0.5', 0), ('0.49', 1)]:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = main(['simulate', '--plan', str(plan), '--tools', str(tools),
                        '--max-cost', bound, '--max-makespan', '2', '--max-findings', '0'])
                self.assertEqual(code, expected)
            out = root/'report.json'
            result = subprocess.run([sys.executable, '-m', 'planbench', 'simulate',
                '--plan', str(plan), '--tools', str(tools), '--json', str(out)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            parsed = json.loads(out.read_text(), parse_constant=lambda x: self.fail(x))
            self.assertEqual(parsed['simulation']['makespan'], 2)
            self.assertEqual(parsed['simulation']['total_cost'], .5)


if __name__ == '__main__':
    unittest.main()
