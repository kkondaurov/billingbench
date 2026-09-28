import contextlib
from decimal import Decimal
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'benchmark/v1')]
from export_r3 import codex_usage, price


class Pricing(unittest.TestCase):
    def test_cache_reads_writes_and_reasoning_are_not_double_counted(self):
        u = dict(input_tokens=100000, cached_input_tokens=60000, cache_write_5m_tokens=10000,
                 cache_write_1h_tokens=10000, output_tokens=10000, reasoning_output_tokens=7000)
        self.assertEqual(price(u, 'claude-opus-5-5'), Decimal('.422'))

    def test_long_context_boundary_is_per_request(self):
        u = dict(input_tokens=272000, cached_input_tokens=0, output_tokens=1000)
        self.assertEqual(price(u, 'gpt-6-astra'), Decimal('2.77'))
        u['input_tokens'] += 1
        self.assertEqual(price(u, 'gpt-6-astra'), Decimal('5.51502'))

    def test_reused_first_release_stops_at_first_delivery_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sessions').mkdir()
            usage = dict(input_tokens=1000, cached_input_tokens=500, output_tokens=100, reasoning_output_tokens=40)
            request = lambda stamp, response: dict(type='token_usage_record', timestamp=stamp,
                payload=dict(session_id='test', response_id=response, usage=usage))
            done = lambda stamp, message: dict(type='event_msg', timestamp=stamp,
                payload=dict(type='task_complete', last_agent_message=message))
            rows = [request('01', 'r1'), request('01', 'r1'), done('02', 'first'),
                    request('03', 'r2'), done('04', 'second')]
            (root / 'sessions/rollout-test.jsonl').write_text('\n'.join(map(json.dumps, rows)))
            log = root / 'first.jsonl'
            log.write_text(json.dumps(dict(type='item.completed', item=dict(type='agent_message', text='first'))))
            stage = dict(inherited_from=str(root), session_id='test', log=str(log), seconds=10)
            result, seconds = codex_usage(root, stage, 'gpt-6-astra')
            self.assertEqual((result['requests'], result['input_tokens'], seconds), (1, 1000, 10))
            self.assertAlmostEqual(result['api_equivalent_usd'], .0105)


class PublishedCommands(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('published_run', ROOT / 'benchmark/v1/run.py')
        cls.command = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.command)

    def test_evaluation_context_only_passed_to_api(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind in ('api', 'retained', 'performance'):
                args = ['run.py', 'evaluate', '--kind', kind, '--output', str(root / kind),
                        '--run' if kind == 'retained' else '--snapshot', str(root / 'source')]
                calls = []
                with patch.object(sys, 'argv', args), patch.dict(os.environ, {'BILLING_EVALUATION_LOCK': str(root / 'lock')}), \
                     patch.object(self.command.runpy, 'run_path', side_effect=lambda *_a, **_k: calls.append(list(sys.argv))):
                    self.assertEqual(self.command.main(), 0)
                self.assertEqual('--context' in calls[0], kind == 'api')

    def test_candidate_requires_explicit_protocol(self):
        with patch.object(sys, 'argv', ['run.py', 'candidate', '--directory', 'unused',
                                      '--model', 'gpt-6-astra', '--effort', 'low']), \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.command.main()


if __name__ == '__main__':
    unittest.main()
