from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from export_sol62 import RATES, usage_records


class Sol62Export(unittest.TestCase):
    def test_prices_deduplicated_short_and_long_requests(self):
        def record(response, tokens):
            return dict(type='token_usage_record', payload=dict(session_id='s', response_id=response,
                usage=dict(input_tokens=tokens, cached_input_tokens=200000,
                           output_tokens=1000, reasoning_output_tokens=200)))

        short, long = record('a', 272000), record('b', 300000)
        usage = usage_records([short, long, long], RATES)
        self.assertEqual(usage['requests'], 2)
        self.assertEqual(usage['long_requests'], 1)
        self.assertAlmostEqual(usage['api_equivalent_usd'], .629)
        self.assertEqual(usage['output_tokens'], 2000)
