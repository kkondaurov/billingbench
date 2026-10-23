import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from export_deepseek import MODEL, checked_rows, session_usage


class DeepSeekExport(unittest.TestCase):
    def test_api_object_and_retained_array(self):
        rows = [dict(key='a', status='passed'), dict(key='b', status='failed')]
        receipt = dict(counts={'passed': 1, 'failed': 1})
        for summary in (rows, dict(status='completed', results=rows)):
            self.assertEqual(checked_rows(summary, receipt, 2), rows)

    def test_missing_duplicate_or_execution_errors_cannot_publish(self):
        rows = [dict(key='a', status='passed'), dict(key='b', status='failed')]
        receipt = dict(counts={'passed': 1, 'failed': 1})
        for summary in ([], rows[:1], [rows[0], rows[0]],
                        [rows[0], dict(key='b', status='error')],
                        dict(status='running', results=rows)):
            with self.subTest(summary=summary), self.assertRaises(AssertionError):
                checked_rows(summary, receipt, 2)

    def test_sdk_counters_are_normalized_without_double_counting(self):
        info = dict(id='message', role='assistant', providerID='openrouter', modelID=MODEL,
                    variant='high', time={'completed': 1}, cost=.000069,
                    tokens=dict(input=100, output=30, reasoning=50, cache={'read': 2000, 'write': 0}))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'session.json'
            path.write_text(json.dumps({'messages': [{'info': info}, {'info': copy.deepcopy(info)}]}))
            usage = session_usage(path)
        self.assertEqual(usage['requests'], 1)
        self.assertEqual((usage['input_tokens'], usage['cached_input_tokens']), (2100, 2000))
        self.assertEqual((usage['output_tokens'], usage['reasoning_output_tokens']), (80, 50))
        self.assertAlmostEqual(usage['api_equivalent_usd'], .000069)

    def test_wrong_model_or_incomplete_receipt_cannot_publish(self):
        for change in ({'modelID': 'wrong'}, {'time': {}}):
            info = dict(id='message', role='assistant', providerID='openrouter', modelID=MODEL,
                        variant='high', time={'completed': 1})
            info.update(change)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'session.json'
                path.write_text(json.dumps({'messages': [{'info': info}]}))
                with self.assertRaises(AssertionError):
                    session_usage(path)


if __name__ == '__main__':
    unittest.main()
