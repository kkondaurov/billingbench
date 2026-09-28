import copy
import tempfile
import unittest
from unittest.mock import patch

from billing_eval.checks import Mismatch
from billing_eval.fixtures import currency_report, report_content
from billing_eval.suite import Case, execute


def report():
    account = dict(account_key='receivable', segments={}, debit_minor=20, credit_minor=5,
                   net_debit_minor=15, opening_net_debit_minor=3, closing_net_debit_minor=18)
    unit = dict(scope_key='unit', billed_minor=20, earned_minor=5, position_minor=15,
                asset_minor=0, deferred_minor=15)
    return dict(accounts=[account], rollups=[copy.deepcopy(account)], units=[unit],
                closed=False, unresolved=[])


class ReportValidation(unittest.TestCase):
    def test_valid_wrappers_preserve_values_and_extensions(self):
        value = report()
        value['units'][0]['private_extension'] = 'allowed'
        wrappers = [value, {'USD': value}, {'currencies': {'USD': value}},
                    {'currencies': [dict(value, currency='USD')]}]
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper):
                before = copy.deepcopy(wrapper)
                self.assertEqual(report_content(currency_report(wrapper)), report_content(value))
                self.assertEqual(wrapper, before)

    def test_zero_and_negative_positions_remain_valid(self):
        for billed, earned in ((0, 0), (0, 10), (10, 0), (-10, -20), (-20, -10)):
            value = report()
            position = billed - earned
            value['units'][0].update(billed_minor=billed, earned_minor=earned, position_minor=position,
                                     asset_minor=max(-position, 0), deferred_minor=max(position, 0))
            self.assertEqual(currency_report(value), value)

    def test_every_missing_public_row_field_is_a_mismatch(self):
        for name in ('accounts', 'rollups', 'units'):
            for field in report()[name][0]:
                value = report()
                del value[name][0][field]
                with self.subTest(name=name, field=field), self.assertRaisesRegex(Mismatch, 'missing required fields.*' + field):
                    currency_report(value)

    def test_money_is_not_coerced_from_null_boolean_string_float_or_container(self):
        for name in ('accounts', 'rollups', 'units'):
            for field in (key for key in report()[name][0] if key.endswith('_minor')):
                for bad in (None, True, False, '0', 0.0, [], {}):
                    value = report()
                    value[name][0][field] = bad
                    with self.subTest(name=name, field=field, bad=bad), self.assertRaisesRegex(Mismatch, 'expected integer'):
                        currency_report(value)

    def test_missing_fields_are_reported_before_null_arithmetic(self):
        value = report()
        value['units'][0].update(earned_minor=None, position_minor=None)
        del value['units'][0]['asset_minor']
        del value['units'][0]['deferred_minor']
        with self.assertRaisesRegex(Mismatch, 'missing required fields asset_minor, deferred_minor'):
            currency_report(value)

    def test_invalid_row_and_projection_shapes_are_mismatches(self):
        for name in ('accounts', 'rollups', 'units'):
            for row in (None, [], 0, 'bad'):
                value = report()
                value[name] = [row]
                with self.subTest(name=name, row=row), self.assertRaisesRegex(Mismatch, 'expected object'):
                    currency_report(value)
        for name, field, bad in (('accounts', 'segments', None), ('rollups', 'segments', []),
                                  ('accounts', 'segments', {1: 'x'}), ('units', 'scope_key', None),
                                  ('accounts', 'account_key', 1)):
            value = report()
            value[name][0][field] = bad
            with self.subTest(name=name, field=field), self.assertRaises(Mismatch):
                currency_report(value)

    def test_wrong_amounts_still_fail(self):
        for name, field in (('accounts', 'net_debit_minor'), ('rollups', 'closing_net_debit_minor'),
                            ('units', 'position_minor'), ('units', 'asset_minor'), ('units', 'deferred_minor')):
            value = report()
            value[name][0][field] += 1
            with self.subTest(name=name, field=field), self.assertRaises(Mismatch):
                currency_report(value)

    def test_suite_distinguishes_bad_response_from_internal_bug(self):
        value = report()
        del value['units'][0]['asset_minor']
        def malformed(_):
            currency_report(value)
        def bug(_):
            raise KeyError('internal-bug')
        with tempfile.TemporaryDirectory() as directory, patch('billing_eval.suite.Fixture'):
            for run, expected in ((malformed, 'failed'), (bug, 'error')):
                case = Case(run.__name__, 1, 'validation', (), '', run)
                result = execute(case, 'http://unused', 'unused', directory)
                self.assertEqual(result['status'], expected)


if __name__ == '__main__':
    unittest.main()
