import copy
import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from export_r3 import codex_usage, price
from export_r4 import INVENTORY, TOTALS, verified_results


def fixture():
    root = Path('/test-rescore')
    manifest = dict(lanes=[], jobs=[])
    state = dict(status='completed', hashes_verified=True, jobs={})
    files = {root / 'MANIFEST.json': manifest, root / 'STATUS.json': state}
    for model, count in INVENTORY.items():
        for replica in range(count):
            label = f'{model}-{replica + 1:02d}'
            manifest['lanes'].append(dict(label=label))
            for kind, n in [('api', n) for n in range(1, 6)] + [('retained', 5)]:
                key = f'{label}/{kind}-m{n}'
                output = root / key
                original = output / 'original.json'
                total = TOTALS[n] if kind == 'api' else 20
                rows = [dict(key=f'case-{i}', status='passed') for i in range(total)]
                summary = dict(status='completed', results=rows) if kind == 'api' else rows
                files[output / 'summary.json'] = summary
                files[original] = copy.deepcopy(summary)
                manifest['jobs'].append(dict(lane=label, kind=kind, milestone=n,
                                             output=str(output), original=str(original)))
                state['jobs'][key] = dict(status='completed', exit_code=0, summary_sha256='digest',
                                          counts={'passed': total}, changes=[])
    return root, files


class R4Export(unittest.TestCase):
    def test_usage_clock_cannot_silently_cross_delivery_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sessions').mkdir()
            usage = dict(type='token_usage_record', timestamp='03',
                         payload=dict(session_id='test', response_id='response', usage={}))
            done = dict(type='event_msg', timestamp='02', payload=dict(type='task_complete', last_agent_message='done'))
            (root / 'sessions/rollout-test.jsonl').write_text('\n'.join(map(json.dumps, [usage, done])))
            log = root / 'delivery.jsonl'
            log.write_text(json.dumps(dict(type='item.completed', item=dict(type='agent_message', text='done'))))
            stage = dict(session_id='test', log=str(log), seconds=10)
            with self.assertRaisesRegex(AssertionError, 'Usage clock/order boundary mismatch'):
                codex_usage(root, stage, 'gpt-6.1-sol')

    def test_sol61_exact_short_cached_price(self):
        usage = dict(input_tokens=100000, cached_input_tokens=60000, output_tokens=10000)
        self.assertEqual(price(usage, 'gpt-6.1-sol'), Decimal('.186'))
        self.assertEqual(price(usage, 'gpt-6-sol'), Decimal('.192'))

    def test_sol61_long_boundary_and_reasoning_not_double_counted(self):
        usage = dict(input_tokens=272000, cached_input_tokens=272000, output_tokens=100,
                     reasoning_output_tokens=90)
        self.assertEqual(price(usage, 'gpt-6.1-sol'), Decimal('.0282'))
        usage.update(input_tokens=272001, cached_input_tokens=272001)
        self.assertEqual(price(usage, 'gpt-6.1-sol'), Decimal('.0559002'))

    def test_complete_inventory_is_exportable(self):
        root, files = fixture()
        with patch('export_r4.read', side_effect=lambda p: files[p]), patch('export_r4.sha', return_value='digest'):
            result = verified_results(root)
        self.assertEqual(len(result['jobs']), 78)
        self.assertTrue(result['complete'])

    def test_incomplete_unverified_and_interrupted_runs_cannot_publish(self):
        for change in ({'status': 'running'}, {'hashes_verified': False}, {'status': 'needs_attention'}):
            root, files = fixture()
            files[root / 'STATUS.json'].update(change)
            with self.subTest(change=change), patch('export_r4.read', side_effect=lambda p: files[p]), \
                    patch('export_r4.sha', return_value='digest'), self.assertRaises(AssertionError):
                verified_results(root)

    def test_tampered_incomplete_or_errored_summary_cannot_publish(self):
        for failure in ('hash', 'missing-case', 'exception', 'duplicate-case', 'count', 'exit-code'):
            root, files = fixture()
            first = files[root / 'MANIFEST.json']['jobs'][0]
            summary = files[Path(first['output']) / 'summary.json']
            receipt = next(iter(files[root / 'STATUS.json']['jobs'].values()))
            if failure == 'hash':
                receipt['summary_sha256'] = 'changed'
            elif failure == 'missing-case':
                summary['results'].pop()
            elif failure == 'exception':
                summary['results'][0]['status'] = 'error'
            elif failure == 'duplicate-case':
                summary['results'][0]['key'] = summary['results'][1]['key']
            elif failure == 'count':
                receipt['counts'] = {'passed': 0}
            else:
                receipt['exit_code'] = 1
            with self.subTest(failure=failure), patch('export_r4.read', side_effect=lambda p: files[p]), \
                    patch('export_r4.sha', return_value='digest'), self.assertRaises(AssertionError):
                verified_results(root)


if __name__ == '__main__':
    unittest.main()
