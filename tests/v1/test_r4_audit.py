import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'benchmark/v1/evaluation/0.5'))
from billing_eval.checks import Mismatch, bill_documents, document_totals
from billing_eval.impacts import closed_sale_impact


def document(key='old', amount=100, status='posted'):
    return dict(id=key, kind='invoice', origin='bill_run', customer_id='customer', currency='USD',
                invoice_date='2028-01-31', posting_date='2028-01-31', result_id='result',
                total_minor=amount, items=[dict(key='item', amount_minor=amount)], status=status)


def scopes(*ids):
    return [dict(status='covered', document_ids=list(ids))]


class BillingPopulation(unittest.TestCase):
    def test_covered_document_links_are_not_new_charges(self):
        old = document()
        new = document('new', 200)
        self.assertEqual(bill_documents([old], [old], scopes('old')), [])
        self.assertEqual(bill_documents([old], [old, new], scopes('old', 'new')), [new])

    def test_existing_draft_is_still_observed(self):
        old = document(status='draft')
        new = dict(old, status='posted')
        self.assertEqual(bill_documents([old], [new], scopes('old')), [new])

    def test_new_duplicate_is_not_filtered(self):
        old = document()
        duplicate = document('duplicate')
        observed = bill_documents([old], [old, duplicate], scopes('old', 'duplicate'))
        with self.assertRaises(Mismatch):
            document_totals(observed, [])

    def test_unlinked_missing_deleted_and_duplicate_ids_fail(self):
        old, new = document(), document('new')
        for before, after, linked in [
            ([old], [old, new], scopes('old')),
            ([old], [old], scopes('missing')),
            ([old], [], scopes()),
            ([old], [old, old], scopes('old')),
        ]:
            with self.subTest(linked=linked), self.assertRaises(Mismatch):
                bill_documents(before, after, linked)

    def test_existing_face_facts_must_not_change(self):
        old = document()
        for field, value in [('total_minor', 101), ('customer_id', 'wrong'),
                             ('posting_date', '2028-02-01'), ('items', []), ('status', 'cancelled')]:
            new = dict(old, **{field: value})
            with self.subTest(field=field), self.assertRaises(Mismatch):
                bill_documents([old], [new], scopes('old'))
        settled = dict(old, open_minor=0, applied_minor=100)
        settled['items'] = [dict(old['items'][0], open_minor=0)]
        self.assertEqual(bill_documents([old], [settled], scopes('old')), [])

    def test_money_is_integer_not_boolean_float_or_missing(self):
        for value in (True, 1.0, '1', None):
            for field in ('total_minor', 'item'):
                doc = document(amount=1)
                if field == 'item':
                    doc['items'][0]['amount_minor'] = value
                else:
                    doc[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(Mismatch):
                    document_totals([doc], [('invoice', 1)])


class NullableImpactDebtor(unittest.TestCase):
    def setUp(self):
        import json
        self.preview = json.loads((Path(__file__).parent / 'fixtures/sol61-account-preview.json').read_text())
        self.customer = next(r['customer_id'] for r in self.preview['result']['effects'] if r['kind'] == 'billing')
        self.accounts = {k: 'book-' + k for k in ('receivable', 'customer_funds', 'contract_position', 'service_revenue')}

    def test_null_aggregate_customer_with_correct_debtor_is_valid(self):
        original = copy.deepcopy(self.preview)
        closed_sale_impact(self.preview, self.customer, self.accounts)
        self.assertEqual(self.preview, original)

    def test_wrong_nonnull_or_missing_billing_debtor_rejected(self):
        for kind, value in [('account_distribution', 'wrong'), ('billing', 'wrong'), ('billing', None)]:
            preview = copy.deepcopy(self.preview)
            next(r for r in preview['result']['effects'] if r['kind'] == kind)['customer_id'] = value
            with self.subTest(kind=kind, value=value), self.assertRaises(Mismatch):
                closed_sale_impact(preview, self.customer, self.accounts)

    def test_economic_amounts_cannot_disagree_with_valid_addresses(self):
        for kind in ('billing', 'recognition'):
            preview = copy.deepcopy(self.preview)
            row = next(r for r in preview['result']['effects'] if r['kind'] == kind)
            row['target_minor'] += 1
            row['delta_minor'] += 1
            with self.subTest(kind=kind), self.assertRaises(Mismatch):
                closed_sale_impact(preview, self.customer, self.accounts)


if __name__ == '__main__':
    unittest.main()
