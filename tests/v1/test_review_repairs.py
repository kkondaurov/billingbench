"""Contract allowances must reject missing money, fabricated links and orphan journals."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from billing_eval.checks import Mismatch, effect_integrity
from billing_eval.client import API
from billing_eval.fixtures import Fixture
from billing_eval.m1 import economics
from billing_eval.reviewed_challenges import transfer_checks
from billing_eval.suite import Context


class Response:
    def __init__(self, status, value):
        self.status, self.value = status, value

    def read(self):
        return json.dumps(self.value).encode()


class ReviewRepairs(unittest.TestCase):
    def test_unknown_earnings_do_not_invent_zero_or_hide_posting(self):
        f = MagicMock()
        row = dict(scope_key='s', billed_minor=100, earned_minor=None, position_minor=None,
                   issues=[dict(code='missing_evidence')])
        f.units.return_value = [row]
        f.effects.return_value = []
        economics(f, 100, 0)
        for changes in (dict(issues=[]), dict(billed_minor=99), dict(position_minor=90)):
            f.units.return_value = [dict(row, **changes)]
            with self.assertRaises(Mismatch):
                economics(f, 100, 0)
        f.units.return_value = [row]
        with self.assertRaises(Mismatch):
            economics(f, 100, 20)
        f.effects.return_value = [dict(kind='recognition', scope_key='s', amount_minor=1)]
        with self.assertRaises(Mismatch):
            economics(f, 100, 0)

    def test_paired_transfer_reconstructs_both_scopes(self):
        base = dict(key='k', kind='position_transfer', currency='USD', economic_date='2028-01-07',
                    posting_date='2028-01-07', configuration_id='chart', source=dict(kind='transfer', id='t'), corrects_ids=[])
        left = dict(base, id='left', scope_key='old', amount_minor=-40, legs=[
            dict(function='deferred', scope_key='old', debit_minor=40, credit_minor=0),
            dict(function='deferred', scope_key='new', debit_minor=0, credit_minor=40)])
        right = dict(base, id='right', scope_key='new', amount_minor=40, legs=[])
        effect_integrity([left, right])
        for changes in (dict(amount_minor=39), dict(scope_key='absent'), dict(source=dict(id='other')),
                        dict(posting_date='2028-01-08'), dict(kind='recognition'), dict(corrects_ids=['missing'])):
            with self.assertRaises(Mismatch):
                effect_integrity([left, dict(right, **changes)])
        with self.assertRaises(Mismatch):
            effect_integrity([right])
        with self.assertRaises(Mismatch):
            effect_integrity([left, right, dict(right, id='duplicate-claim')])
        bad = copy.deepcopy(left)
        bad['legs'][0]['debit_minor'] += 1
        with self.assertRaises(Mismatch):
            effect_integrity([bad, right])

    def test_explicit_creation_route_does_not_fallback(self):
        for suffix in ('amendments', 'terminations'):
            api = API('http://unused', 'secret', tenant='tenant')
            with patch('billing_eval.client.urlopen', side_effect=[
                Response(404, dict(error=dict(code='not_found', issues=[]))), Response(201, dict(data=dict(id='a')))
            ]) as call:
                with self.assertRaises(Mismatch):
                    api.request('POST', '/deals/d/'+suffix, dict(scope_key='s'), status=201, version=4)
            self.assertEqual(len(call.call_args_list), 1)
        for status, value in ((422, dict(error=dict(code='invalid_domain'))),
                              (200, dict(operation=dict(status='held'))),
                              (404, dict(error=dict(code='not_found'), data=dict(id='a')))):
            api = API('http://unused', 'secret', tenant='tenant')
            with patch('billing_eval.client.urlopen', return_value=Response(status, value)) as call:
                api.request('POST', '/deals/d/amendments', {}, version=4)
            self.assertEqual(call.call_count, 1)

    def test_one_agreement_can_have_multiple_transfer_pairs(self):
        base = dict(key='k', configuration_id='chart', kind='position_transfer', currency='USD', economic_date='2028-01-07',
                    posting_date='2028-01-07', source=dict(kind='amendment', id='a'), corrects_ids=[])
        rows = []
        for i, amount in enumerate((40, 40, 60)):
            scope = 'new-'+str(i)
            rows.extend([dict(base, id='journal-'+str(i), scope_key=scope, amount_minor=amount, legs=[
                dict(function='deferred', scope_key='old', debit_minor=amount, credit_minor=0),
                dict(function='deferred', scope_key=scope, debit_minor=0, credit_minor=amount)]),
                dict(base, id='logical-'+str(i), scope_key='old', amount_minor=-amount, legs=[])])
        effect_integrity(list(reversed(rows)))
        with self.assertRaises(Mismatch):
            effect_integrity(rows[1:])
        with self.assertRaises(Mismatch):
            effect_integrity(rows + [dict(rows[1], id='duplicate-claim')])
        with self.assertRaises(Mismatch):
            effect_integrity(rows + [dict(rows[0], id='duplicate-journal')])
        with self.assertRaises(Mismatch):
            effect_integrity([rows[0]])

    def test_collection_denial_cannot_carry_data_or_success(self):
        for status, code in ((403, 'forbidden'), (404, 'not_found')):
            api = API('http://unused', 'secret')
            value = dict(error=dict(code=code, issues=[]))
            with patch('billing_eval.client.urlopen', return_value=Response(status, value)):
                api.hidden_collection('/corrections')
            for bad in (dict(value, data=[]), dict(error=dict(code='internal_error', issues=[]))):
                with patch('billing_eval.client.urlopen', return_value=Response(status, bad)):
                    with self.assertRaises(Mismatch):
                        api.hidden_collection('/corrections')

    def test_memo_follows_explicit_document_link(self):
        for resource in (dict(id='doc'), dict(id='memo', document_id='doc')):
            f = object.__new__(Fixture)
            f.create, f.api = MagicMock(return_value=resource), MagicMock()
            f.memo(dict(id='buyer'), dict(id='invoice', items=[dict(key='item')]), 10)
            f.api.action.assert_called_once_with('/documents/doc/post', dict(posting_date='2028-01-31'))

    def test_source_item_must_exist_not_just_total(self):
        f = MagicMock()
        item = dict(document_id='invoice', item_key='line', assigned_minor=40)
        def population(path):
            if path == '/documents':
                return [dict(id='invoice', items=[dict(key='line', amount_minor=100)])]
            return [dict(predecessor_scope_key='old', billed_transfer_minor=40, source_items=[item])]
        f.api.all.side_effect = population
        transfer_checks(Context(f), ['old'], [40], {'invoice'})
        item['item_key'] = 'invented-item'
        with self.assertRaises(Mismatch):
            transfer_checks(Context(f), ['old'], [40], {'invoice'})
        item.update(item_key='line', assigned_minor=101)
        with self.assertRaises(Mismatch):
            transfer_checks(Context(f), ['old'], [40], {'invoice'})


if __name__ == '__main__':
    unittest.main()
