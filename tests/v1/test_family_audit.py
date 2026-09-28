import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'benchmark/v1/evaluation/0.5'))
from billing_eval.checks import Mismatch
from billing_eval.impacts import validate_impacts, closed_sale_impact
from billing_eval.scopes import current_transfers, chain_carries
from billing_eval.suite import Case, execute, REPETITIONS

ACCOUNTS = {k: 'book-' + k for k in ('receivable', 'customer_funds', 'contract_position', 'service_revenue')}
TRACE = HERE / 'fixtures/opus-impact-preview.json'


def preview():
    return json.loads(TRACE.read_text())


class Impacts(unittest.TestCase):
    def test_valid_recorded_opus(self):
        value = preview()
        before = copy.deepcopy(value)
        closed_sale_impact(value, value['result']['effects'][0]['customer_id'], ACCOUNTS)
        self.assertEqual(value, before)

    def test_corrupt_previews_rejected(self):
        for mutation in ('empty', 'debtor', 'address', 'amount', 'one-effect', 'segment'):
            value = preview()
            rows = value['result']['effects']
            customer = rows[0]['customer_id']
            if mutation == 'empty':
                rows.clear()
            elif mutation == 'debtor':
                rows[0]['customer_id'] = 'wrong'
            elif mutation == 'address':
                for row in rows:
                    row['target_addresses'] = []
            elif mutation == 'amount':
                rows[0]['target_addresses'][0]['credit_minor'] += 1
            elif mutation == 'one-effect':
                rows.pop()
            else:
                rows[0]['target_addresses'][0]['segments'] = {'wrong': 'segment'}
            with self.subTest(mutation=mutation), self.assertRaises(Mismatch):
                closed_sale_impact(value, customer, ACCOUNTS)

    def test_daily_and_combined_projections(self):
        value = preview()
        customer = value['result']['effects'][0]['customer_id']
        recognition = value['result']['effects'].pop()
        for _ in range(2):
            row = copy.deepcopy(recognition)
            for key in ('old_minor', 'target_minor', 'delta_minor'):
                row[key] //= 2
            for key in ('old_addresses', 'target_addresses'):
                for address in row[key]:
                    address['debit_minor'] //= 2
                    address['credit_minor'] //= 2
            value['result']['effects'].append(row)
        closed_sale_impact(value, customer, ACCOUNTS)
        for row in value['result']['effects']:
            row['kind'] = 'account_distribution'
        closed_sale_impact(value, customer, ACCOUNTS)

    def test_separate_address_projection_and_inconsistent_duplicates(self):
        value = preview()
        rows = value['result']['effects']
        customer = rows[0]['customer_id']
        combined = copy.deepcopy(rows)
        for row in combined:
            row['kind'] = 'account_distribution'
        for row in rows:
            row['old_addresses'] = []
            row['target_addresses'] = []
        rows.extend(combined)
        closed_sale_impact(value, customer, ACCOUNTS)
        rows[0]['target_addresses'] = copy.deepcopy(combined[0]['target_addresses'])
        with self.assertRaises(Mismatch):
            closed_sale_impact(value, customer, ACCOUNTS)

    def test_schema_failures_are_mismatches_not_exceptions(self):
        for field in preview()['result']['effects'][0]:
            value = preview()['result']
            del value['effects'][0][field]
            with self.subTest(field=field), self.assertRaises(Mismatch):
                validate_impacts(value)
        for bad in (None, True, '0', 0.0, [], {}):
            value = preview()['result']
            value['effects'][0]['delta_minor'] = bad
            with self.subTest(bad=bad), self.assertRaises(Mismatch):
                validate_impacts(value)
        for result in (None, {}, {'effects': None, 'affected': []}, {'effects': [None], 'affected': []}):
            with self.subTest(result=result), self.assertRaises(Mismatch):
                validate_impacts(result)

    def test_empty_is_schema_valid_but_not_a_changed_sale(self):
        value = {'effects': [], 'affected': []}
        self.assertEqual(validate_impacts(value), [])
        with self.assertRaises(Mismatch):
            closed_sale_impact({'result': value}, 'customer', ACCOUNTS)


def transfer(key, amount=10, refs=(), **extra):
    return dict(id=key, key=key, predecessor_scope_key='a', successor_scope_key='b',
                effective_on='2028-02-01', consideration_carry_minor=amount,
                corrects_ids=list(refs), **extra)


class Transfers(unittest.TestCase):
    def test_current_view_and_external_refs_unchanged(self):
        rows = [transfer('new', refs=['old-not-in-collection', 'journal'])]
        self.assertEqual(current_transfers(rows), rows)

    def test_history_resolved_without_mutation(self):
        rows = [transfer('old', current=False), transfer('new', 8, ['old'], current=True)]
        before = copy.deepcopy(rows)
        self.assertEqual(current_transfers(rows), [rows[1]])
        self.assertEqual(rows, before)
        self.assertEqual(current_transfers(current_transfers(rows)), [rows[1]])

    def test_signed_adjustments_remain_additive(self):
        rows = [transfer('old', 10), transfer('delta', -2, ['old'])]
        self.assertEqual(current_transfers(rows), rows)
        chain_carries(rows, [], ['a', 'b'], ['2028-02-01'], [8])

    def test_invalid_lineages_fail(self):
        corrupt = [
            [transfer('a', refs=['a'])],
            [transfer('a', refs=['b']), transfer('b', refs=['a'])],
            [transfer('a'), transfer('a')],
            [transfer('old', current=False)],
            [transfer('old', status='superseded')],
            [transfer('old', current=False), dict(transfer('new', refs=['old']), successor_scope_key='other')],
        ]
        for rows in corrupt:
            with self.subTest(rows=rows), self.assertRaises(Mismatch):
                current_transfers(rows)

    def test_wrong_current_amount_still_fails(self):
        rows = [transfer('old', current=False), transfer('new', 9, ['old'], current=True)]
        with self.assertRaises(Mismatch):
            chain_carries(rows, [], ['a', 'b'], ['2028-02-01'], [8])


class Repeatability(unittest.TestCase):
    def test_all_attempts_retained_and_any_failure_fails(self):
        calls = []
        def run(context):
            calls.append(1)
            if len(calls) == 3:
                raise Mismatch('one bad tie')
        case = Case('v02-debtor-boundary-self', 5, 'test', (), '', run)
        with tempfile.TemporaryDirectory() as directory, patch('billing_eval.suite.Fixture'):
            result = execute(case, 'unused', 'unused', directory)
            self.assertEqual(len(calls), REPETITIONS)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['representative_repetition'], 3)
            self.assertEqual(len(result['repetitions']), REPETITIONS)
            self.assertEqual(len(list(Path(directory).glob('repetitions/*/*/*.json'))), REPETITIONS)


if __name__ == '__main__':
    unittest.main()
