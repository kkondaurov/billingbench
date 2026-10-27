import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from export_terra import usage_records


class TerraUsage(unittest.TestCase):
    def event(self, identity, inputs, cached, output, reasoning=0):
        return dict(type='token_usage_record', payload=dict(session_id='s', response_id=identity,
                    usage=dict(input_tokens=inputs,cached_input_tokens=cached,output_tokens=output,
                               reasoning_output_tokens=reasoning,cache_write_input_tokens=0)))

    def test_request_identity_deduplicates_resume_archive(self):
        e=self.event('r',100,80,20,10)
        u=usage_records([e,copy.deepcopy(e)])
        self.assertEqual((u['requests'],u['output_tokens'],u['reasoning_output_tokens']),(1,20,10))
        self.assertAlmostEqual(u['api_equivalent_usd'],.000124)

    def test_cumulative_input_does_not_trigger_long_context_tier(self):
        u=usage_records([self.event('a',200000,100000,100),self.event('b',200000,100000,100)])
        self.assertEqual(u['long_requests'],0)
        self.assertAlmostEqual(u['api_equivalent_usd'],.211)

    def test_actual_long_request_prices_full_request(self):
        u=usage_records([self.event('r',300000,200000,1000,500)])
        self.assertEqual(u['long_requests'],1)
        self.assertAlmostEqual(u['api_equivalent_usd'],.2275)

    def test_boundary_272k_stays_short(self):
        self.assertEqual(usage_records([self.event('r',272000,0,0)])['long_requests'],0)

    def test_conflicting_duplicate_fails_closed(self):
        with self.assertRaises(AssertionError):
            usage_records([self.event('r',100,0,10),self.event('r',101,0,10)])

    def test_inconsistent_cache_or_reasoning_fails_closed(self):
        for e in (self.event('r',100,101,10),self.event('r',100,0,10,11)):
            with self.assertRaises(AssertionError): usage_records([e])


if __name__=='__main__': unittest.main()
