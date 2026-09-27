"""Positive controls and targeted negative controls for the completed-screen audit."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from billing_eval.client import API
from billing_eval.fixtures import Fixture, currency_report
from billing_eval.checks import Mismatch, document_totals, effect_integrity


class ContractAudit(unittest.TestCase):
    def test_empty_currency_report_preserves_explicit_status_not_invented_data(self):
        self.assertEqual(currency_report(dict(currencies=[], closed=True, unresolved=[])),
                         dict(accounts=[], rollups=[], units=[], closed=True, unresolved=[]))
        for value in ([], dict(currencies=[]), dict(currencies=[], closed=True),
                      dict(currencies=[dict(currency='EUR')], closed=True, unresolved=[])):
            with self.assertRaises(Mismatch):
                currency_report(value)

    def test_computed_layouts_without_persisted_pagination(self):
        for data in ([{"earned_minor": 17}], {"rows": [{"earned_minor": 17}]}):
            api = API("http://unused", "secret")
            api.request = MagicMock(return_value={"data": data})
            self.assertEqual(api.all("/revenue-units"), [{"earned_minor": 17}])
        for path, data in (("/documents", []), ("/revenue-units", {})):
            api.request = MagicMock(return_value={"data": data})
            with self.assertRaises(Mismatch):
                api.all(path)

    def test_noop_post_requires_terminal_scopes(self):
        f = object.__new__(Fixture)
        f.api = MagicMock()
        f.api.action.return_value = {"error": {"code": "already_final"}}
        for status in ("covered", "posted", "not_due"):
            f.api.get.return_value = {"status": "posted", "scopes": [{"status": status, "document_ids": []}]}
            f.post_bill({"id": "run"})
        for status in ("held", "draft", "cancelled"):
            f.api.get.return_value = {"status": "posted", "scopes": [{"status": status, "document_ids": []}]}
            with self.assertRaises(Mismatch):
                f.post_bill({"id": "run"})
        f.api.get.side_effect = [{"status": "posted", "scopes": [{"status": "posted", "document_ids": ["doc"]}]},
                                {"status": "draft"}]
        with self.assertRaises(Mismatch):
            f.post_bill({"id": "run"})

    def test_missing_evidence_allowance_is_local_and_bounded(self):
        f = object.__new__(Fixture)
        f.counter = 0
        f.api = MagicMock(spec=API)
        f.api.resource = API.resource
        f.api.completed = API.completed
        r = {"data": {"id": "r", "version": 1}, "operation": {
            "id": "op", "status": "held", "issues": [{"code": "missing_evidence"}], "effects": []}}
        f.api.request.return_value = r
        f.recognition("2028-01-31", allow_missing_evidence=True)
        with self.assertRaises(Mismatch):
            f.recognition("2028-01-31")
        r["operation"]["issues"] = [{"code": "missing_configuration"}]
        with self.assertRaises(Mismatch):
            f.recognition("2028-01-31", allow_missing_evidence=True)

    def test_zero_document_not_missing_money_or_offset_items(self):
        document_totals([{"kind": "invoice", "total_minor": 0, "items": [{"amount_minor": 0}]}], [])
        for total, items in ((1, [1]), (0, [1, -1])):
            with self.assertRaises(Mismatch):
                document_totals([{"kind": "invoice", "total_minor": total,
                                  "items": [{"amount_minor": x} for x in items]}], [])

    def test_balanced_population_does_not_hide_unbalanced_effects(self):
        e = {k: k for k in ("id", "key", "kind", "currency", "scope_key", "economic_date", "posting_date", "configuration_id")}
        e.update(amount_minor=10, legs=[{"debit_minor": 10, "credit_minor": 0}, {"debit_minor": 0, "credit_minor": 10}])
        effect_integrity([e])
        unallocated = dict(e, scope_key=None)
        effect_integrity([unallocated])
        missing_scope = dict(e)
        del missing_scope["scope_key"]
        with self.assertRaises(Mismatch):
            effect_integrity([missing_scope])
        other = copy.deepcopy(e)
        other["id"] = "other"
        bad = copy.deepcopy(e)
        bad["legs"][0]["debit_minor"] += 1
        other["legs"][0]["debit_minor"] -= 1
        for rows in ([bad, other], [e, e]):
            with self.assertRaises(Mismatch):
                effect_integrity(rows)


if __name__ == "__main__":
    unittest.main()
