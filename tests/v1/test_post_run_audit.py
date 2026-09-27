"""Post-run repairs preserve permitted wrappers without hiding absent data."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from billing_eval.checks import Mismatch
from billing_eval.fixtures import currency_report, currency_statement
from billing_eval.m1 import immutable_document
from billing_eval.combined import public_allocations


class PostRunAudit(unittest.TestCase):
    def test_allocation_history_uses_required_public_fields(self):
        row = dict(document_id='d', item_key='i', original_minor=10, unapplied_minor=0,
                   backing_released_minor=0, currently_applied_minor=10, unappliable_minor=10)
        expected = public_allocations(dict(allocations=[row]))
        self.assertEqual(public_allocations(dict(allocations=[dict(row, private_context={'x': 1})])), expected)
        self.assertNotEqual(public_allocations(dict(allocations=[dict(row, currently_applied_minor=9)])), expected)
        broken = dict(row)
        del broken['unapplied_minor']
        with self.assertRaises(Mismatch):
            public_allocations(dict(allocations=[broken]))

    def test_empty_statement_funding_wrappers(self):
        values = [dict(documents=[], funds=[], balances=[]),
                  dict(documents=[], receipts=[], refunds=[], currencies={})]
        self.assertEqual(currency_statement(values[0]), currency_statement(values[1]))
        for value in (dict(currencies={}), dict(documents=[], currencies={}),
                      dict(documents=[], receipts=[{'amount_minor': 1}], refunds=[], currencies={})):
            with self.assertRaises(Mismatch):
                currency_statement(value)

    def test_empty_currency_wrappers(self):
        expected = dict(closed=True, unresolved=[], accounts=[], rollups=[], units=[])
        for wrapper in ({}, []):
            self.assertEqual(currency_report(dict(closed=True, unresolved=[], currencies=wrapper)), expected)
        for value in ({}, {'currencies': {}}, {'closed': True, 'currencies': {}},
                      {'closed': 1, 'unresolved': [], 'currencies': {}},
                      {'closed': True, 'unresolved': [], 'currencies': {'EUR': {}}},
                      {'closed': True, 'unresolved': [], 'currencies': [None]}):
            with self.subTest(value=value), self.assertRaises(Mismatch):
                currency_report(value)

    def test_missing_immutable_item_fields_are_candidate_failures(self):
        doc = dict(id='d', key='d', kind='invoice', origin='bill_run', customer_id='c', currency='USD',
                   invoice_date='2028-01-01', posting_date='2028-01-01', total_minor=100,
                   items=[dict(key='i', scope_key='s', subscription_id='sub', charge_key='base',
                               product_id='p', service_window=None, amount_minor=100,
                               origin_document_id=None, origin_item_key=None)])
        immutable_document(doc, copy.deepcopy(doc))
        for field in ('service_window', 'origin_document_id', 'scope_key'):
            broken = copy.deepcopy(doc)
            del broken['items'][0][field]
            with self.subTest(field=field), self.assertRaises(Mismatch):
                immutable_document(broken, broken)


if __name__ == '__main__':
    unittest.main()
