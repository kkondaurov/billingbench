import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from export_neon import MODEL, session_usage


class NeonExport(unittest.TestCase):
    def test_sums_cache_reads_once_and_does_not_double_charge_thinking(self):
        raw = dict(input_tokens=1000, cache_read_tokens=8000, output_tokens=100,
                   thinking_tokens=90, total_tokens=1100)
        init = dict(event='init', conversation_id='trace', init=dict(model=MODEL))
        result = dict(event='result', result=dict(conversation_id='trace', status='SUCCESS',
                                                   num_turns=1, usage=raw))
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'agy.ndjson'
            path.write_text('\n'.join(map(json.dumps, (init, result))))
            usage = session_usage(dict(log=path, session_id='trace', usage=raw))
        self.assertEqual((usage['input_tokens'], usage['cached_input_tokens']), (9000, 8000))
        self.assertEqual((usage['output_tokens'], usage['reasoning_output_tokens']), (100, 90))
        self.assertAlmostEqual(usage['api_equivalent_usd'], .0057)
