import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from export_deepseek_replicates import checked_rows, price
from export_v1 import sha


class ReplicateExportTests(unittest.TestCase):
    def test_common_price_includes_reasoning_once(self):
        usage = dict(input_tokens=212622296, cached_input_tokens=211546496,
                     output_tokens=1014848, cache_write_5m_tokens=0, cache_write_1h_tokens=0)
        self.assertAlmostEqual(price(usage, [.08, .08, .80]), 17.82166208)
        self.assertAlmostEqual(price(usage, [.15, .003, .60]), 1.404918288)

    def test_errors_require_audited_trace_not_just_zero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'cases').mkdir()
            row = dict(key='memo-compensation', status='error', error="KeyError: 'source'")
            path = output / 'cases/memo-compensation.json'
            raw = dict(result=row, trace=[dict(method='GET', path='/applications?limit=200',
                       status=200, response=dict(data=[dict(source_id='x')]))])
            path.write_text(json.dumps(raw))
            summary = dict(status='completed', results=[row])
            receipt = dict(counts=dict(error=1), error_evidence=[dict(key=row['key'], error=row['error'],
                field='source', collection='applications', case_sha256=sha(path),
                classification='candidate_required_response_field_missing')])
            with self.assertRaises(AssertionError):
                checked_rows(summary, receipt, [row['key']], output)
            rows, errors = checked_rows(summary, receipt, [row['key']], output, True)
            self.assertEqual(rows[0]['status'], 'error')
            self.assertEqual(len(errors), 1)
            with self.assertRaises(AssertionError):
                checked_rows(dict(summary, results=[row, row]), receipt, [row['key']], output, True)
            raw['trace'][0]['response']['data'][0]['source'] = dict(kind='credit', id='x')
            path.write_text(json.dumps(raw))
            with self.assertRaises(AssertionError):
                checked_rows(summary, receipt, [row['key']], output, True)

    def test_incomplete_jobs_cannot_be_scored(self):
        with self.assertRaises(AssertionError):
            checked_rows(dict(status='running', results=[]), dict(counts={}), [], Path('/unused'))
