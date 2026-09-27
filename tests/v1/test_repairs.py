import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'benchmark/v1/evaluation/0.5'))
from billing_eval.checks import Mismatch
from billing_eval.fixtures import Fixture
from billing_eval.funding_interactions import pool_postings
from billing_eval.m2 import Usage
from billing_eval.scopes import chain_carries, lineage, scope_members, selected


def deal(identifier, groups):
    return dict(id=identifier, groups=[dict(key=g, promises=[dict(key=p) for p in ps]) for g, ps in groups.items()],
                scope_keys=dict(groups={g: identifier + ':' + g for g in groups},
                                promises={p: identifier + ':' + p for ps in groups.values() for p in ps}))


def transfer(a, b, carry=1, date='2028-02-01'):
    return dict(predecessor_scope_key=a, successor_scope_key=b,
                consideration_carry_minor=carry, effective_on=date)


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.deals = [deal('old', {'group': ['p']}), deal('next', {'g': ['a', 'b'], 'other': ['x']}),
                      deal('last', {'g': ['c']}), deal('rogue', {'g': ['r']})]
        self.rows = [dict(deal_id=d['id'], promise_key=p, scope_key=s)
                     for d in self.deals for p, s in d['scope_keys']['promises'].items()]

    def test_multihop_membership_not_whole_deal(self):
        edges = [transfer('old:group', 'next:g'), transfer('next:a', 'last:g'),
                 transfer('next:other', 'rogue:g')]
        found = lineage(self.rows, edges, self.deals[0], self.deals)
        self.assertEqual({r['scope_key'] for r in found}, {'old:p', 'next:a', 'next:b', 'last:c'})

    def test_partial_group_does_not_authorize_siblings_or_group_edge(self):
        edges = [transfer('old:p', 'next:a'), transfer('next:g', 'last:g')]
        found = lineage(self.rows, edges, self.deals[0], self.deals)
        self.assertEqual({r['scope_key'] for r in found}, {'old:p', 'next:a'})

    def test_group_equals_only_complete_membership(self):
        members = scope_members(self.deals)
        self.assertEqual(selected(members, 'old:group'), selected(members, 'old:p'))
        self.assertNotEqual(selected(members, 'next:g'), selected(members, 'next:a'))

    def test_append_only_carries_and_group_alias(self):
        deals = [deal('old', {'g': ['p']}), deal('next', {'g': ['p']}), deal('last', {'g': ['p']})]
        edges = [transfer('old:p', 'next:g', 6000), transfer('old:p', 'next:g', -2000),
                 transfer('next:p', 'last:g', 4000, '2028-03-01'),
                 transfer('next:p', 'last:g', -2000, '2028-03-01')]
        args = (deals, ['old:p', 'next:p', 'last:p'], ['2028-02-01', '2028-03-01'], [4000, 2000])
        chain_carries(edges, *args)
        for mutate in ('wrong-scope', 'wrong-amount', 'wrong-date'):
            bad = copy.deepcopy(edges)
            if mutate == 'wrong-scope':
                bad[2]['predecessor_scope_key'] = 'old:p'
            elif mutate == 'wrong-amount':
                bad[0]['consideration_carry_minor'] += 1
            else:
                bad[0]['effective_on'] = '2028-01-01'
            with self.subTest(mutate=mutate), self.assertRaises(Mismatch):
                chain_carries(bad, *args)


class FixtureTests(unittest.TestCase):
    def test_completion_is_only_sent_once_per_boundary(self):
        usage = Usage.__new__(Usage)
        usage.f = Mock()
        usage.f.key.return_value = 'complete'
        usage.api = Mock()
        usage.source, usage.manifest = {'id': 'source'}, {'id': 'manifest'}
        usage.window = {'ends_before': '2028-02-01'}
        usage.complete()
        usage.complete()
        self.assertEqual(usage.api.action.call_count, 1)
        usage.window['ends_before'] = '2028-03-01'
        usage.complete()
        self.assertEqual(usage.api.action.call_count, 2)

    def test_split_invoice_settlement_and_explicit_item(self):
        fixture = Fixture.__new__(Fixture)
        fixture.create = Mock()
        doc = dict(id='invoice', items=[dict(key='a', amount_minor=40000), dict(key='b', amount_minor=10000)])
        fixture.application({'id': 'receipt'}, doc, 50000)
        self.assertEqual([r['amount_minor'] for r in fixture.create.call_args.kwargs['allocations']], [40000, 10000])
        fixture.application({'id': 'receipt'}, doc, 5000, item='b')
        self.assertEqual(fixture.create.call_args.kwargs['allocations'],
                         [dict(document_id='invoice', item_key='b', amount_minor=5000)])
        with self.assertRaises(Mismatch):
            fixture.application({'id': 'receipt'}, doc, 50001)


class JournalTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((ROOT / 'fixtures/pooled-postings.json').read_text())
        self.effects, self.rows = fixture['effects'], fixture['rated_charges']
        self.customers, self.grant = fixture['customers'], fixture['grant']

    def check(self, effects):
        pool_postings(effects, self.rows, self.customers, [0, 2400], self.grant['scope_key'], 3840)

    def test_recorded_positive_and_wrong_answers(self):
        self.check(self.effects)
        with self.assertRaises(Mismatch):
            self.check([])
        for field, value in [('economic_date', '2028-02-01'), ('posting_date', '2028-01-20'),
                             ('scope_key', 'unrelated'), ('amount_minor', 3841)]:
            effects = copy.deepcopy(self.effects)
            next(e for e in effects if e['kind'] == 'capacity_consumption')[field] = value
            with self.subTest(field=field), self.assertRaises(Mismatch):
                self.check(effects)
        effects = copy.deepcopy(self.effects)
        effect = next(e for e in effects if e['kind'] == 'capacity_consumption')
        next(l for l in effect['legs'] if l['function'] == 'service_revenue')['account_key'] = 'wrong-revenue'
        with self.assertRaises(Mismatch):
            self.check(effects)


if __name__ == '__main__':
    unittest.main(verbosity=2)
