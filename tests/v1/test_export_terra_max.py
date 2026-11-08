import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from export_terra_max import common_price, session_usage


class MaxExport(unittest.TestCase):
    def events(self,effort='max'):
        return [dict(type='session_meta',payload=dict(cli_version='0.164.0')),
            dict(type='turn_context',payload=dict(model='gpt-6.1-terra',effort=effort)),
            dict(type='token_usage_record',payload=dict(session_id='s',response_id='r',
                usage=dict(input_tokens=100,cached_input_tokens=80,output_tokens=20,reasoning_output_tokens=10,cache_write_input_tokens=0))),
            dict(type='event_msg',payload=dict(type='task_complete'))]

    def read(self,events):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'sessions').mkdir()
            (root/'sessions/rollout-test-s.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
            return session_usage(root,dict(session_id='s'))

    def test_exact_max_one_turn(self):
        u=self.read(self.events());self.assertEqual(u['requests'],1)
        self.assertAlmostEqual(u['api_equivalent_usd'],.000124)

    def test_other_effort_cannot_enter_max_cohort(self):
        with self.assertRaises(AssertionError):self.read(self.events('xhigh'))

    def test_nudged_session_cannot_enter_max_cohort(self):
        with self.assertRaises(AssertionError):self.read(self.events()+self.events()[1:])

    def test_usage_after_delivery_cannot_be_hidden(self):
        with self.assertRaises(AssertionError):self.read(self.events()+[self.events()[2]])

    def test_common_cost_preserves_actual_request_tiers(self):
        stages=[dict(usage=dict(pricing_buckets=dict(short=dict(input_tokens=200000,cached_input_tokens=100000,output_tokens=100),
                    long=dict(input_tokens=300000,cached_input_tokens=200000,output_tokens=1000))))]
        self.assertAlmostEqual(common_price(stages),.333)


if __name__=='__main__':unittest.main()
