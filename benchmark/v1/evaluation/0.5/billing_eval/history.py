"""Upgrade real earlier-version databases; never infer their internal SQL schema."""

import copy
import json
from pathlib import Path
import time
import traceback

from .checks import Mismatch, document_totals, equal, require, fields, integer_fields, closed_unchanged
from .client import identifier
from .fixtures import Fixture
from .m2 import Usage
from .m3 import discount, order
from .m4 import deal, promise, installment
from .m5 import grant
from .m1 import immutable_document


def prepare(f, milestone, mode):
    f.chart(capacity=milestone >= 5)
    allocation_scope = None
    if milestone == 1:
        buyer = f.customer()
        f.subscription(buyer, price="30")
        expected = 3000
    elif milestone == 2:
        usage = Usage(f)
        usage.event("historical-work", "30")
        usage.complete()
        buyer, expected = usage.customers[0], 3000
    elif milestone == 3:
        buyer = f.customer()
        sub, _, _ = f.subscription(buyer, price="30")
        reduction = discount(f, buyer, budget=700)
        order(f, sub, "2028-01-01", [dict(kind="attach_discount", discount_id=reduction["id"])])
        expected = 2300
    elif milestone == 4:
        buyer, product = f.customer(), f.product()
        arrangement = deal(f, buyer, 3000, [promise("a", product, ssp="15", end="2028-02-01"),
                              promise("b", product, ssp="15", end="2028-02-01")],
             [installment("all-on-b", "2028-01-01", 3000, "b")])
        require(isinstance(arrangement.get("scope_keys"), dict) and
                isinstance(arrangement["scope_keys"].get("groups"), dict) and
                arrangement["scope_keys"]["groups"].get("group"),
                "accepted deal missing required group scope_keys")
        allocation_scope = arrangement["scope_keys"]["groups"]["group"]
        expected = 3000
    else:
        usage = Usage(f)
        f.api.at("2028-01-01")
        buyer = usage.customers[0]
        capacity = grant(f, buyer, usage.consumers, usage.product, 1000, 800, end="2028-03-01")
        require(isinstance(capacity.get("deal_id"), str) and capacity["deal_id"],
                "paid grant missing generated sale deal_id")
        sale = f.api.get(f"/deals/{identifier(capacity['deal_id'])}")
        require(isinstance(sale.get("scope_keys"), dict) and
                isinstance(sale["scope_keys"].get("groups"), dict),
                "paid sale missing required group scope_keys")
        groups = sale["scope_keys"]["groups"]
        equal(len(groups), 1, "standalone capacity allocation group")
        allocation_scope = next(iter(groups.values()))
        f.api.at("2028-02-01")
        usage.event("funded-and-overage", "5" if mode in ("settled", "closed") else "12")
        usage.complete()
        expected = 800 if mode in ("settled", "closed") else 1000
    f.api.at("2028-02-01")
    run, documents = f.bill("2028-02-01", "2028-02-01", posted=mode != "draft")
    document_totals(documents, [("invoice", expected)])
    if mode == "reversed":
        f.recognition("2028-01-31", "2028-02-01")
        for document in documents:
            f.api.action(f"/billing-results/{identifier(document['result_id'])}/reverse", dict(key=f.key("reverse"), posting_date="2028-02-01"))
    extra = {}
    if mode in ("settled", "closed"):
        f.recognition("2028-01-31", "2028-02-01")
        if mode == "settled":
            receipt = f.receipt(buyer, expected, post="2028-02-01")
            allocations = [dict(document_id=d["id"], item_key=i["key"], amount_minor=i["amount_minor"])
                           for d in documents for i in d["items"] if i["amount_minor"]]
            f.create("/applications", source=dict(kind="receipt", id=receipt["id"]), allocations=allocations, posting_date="2028-02-01")
            item = dict(key="credit", document_id=documents[0]["id"], item_key=documents[0]["items"][0]["key"],
                        amount_minor=200, reason="Agreed fixed concession")
            if allocation_scope:
                item.update(allocation_scope_key=allocation_scope, concession_scope="full_sale")
            credit = f.create("/memos", kind="credit", customer_id=buyer["id"], currency="USD", invoice_date="2028-02-01",
                              posting_date="2028-02-01", items=[item])
            document_id = credit.get("document_id", credit["id"])
            require(isinstance(document_id, str) and document_id, "memo missing valid document identity")
            f.api.action(f"/documents/{identifier(document_id)}/post", dict(posting_date="2028-02-01"))
            credit = f.api.get(f"/documents/{identifier(document_id)}")
            f.create("/refunds", source=dict(kind="credit", id=credit["id"]), amount_minor=50, posting_date="2028-02-01")
            fields(f.statement(buyer), dict(ar_minor=0, available_backed_minor=150, cash_received_minor=expected, cash_refunded_minor=50),
                   "old partially refunded commercial credit")
            extra["credit"] = credit
        else:
            f.api.at("2028-03-01")
            f.recognition("2028-02-29", "2028-03-01")
            f.create("/period-closes", month="2028-02")
            extra["closed"] = f.report("2028-02")
        extra["statement"] = f.statement(buyer)
    return dict(buyer=buyer, expected=expected, run=run, documents=copy.deepcopy(documents),
                effects=copy.deepcopy(f.effects()), units=copy.deepcopy(f.units()),
                source_ids=[x["id"] for x in f.api.all("/subscriptions")], **extra)


def resume(f, state, mode):
    from .checks import retained_projection
    # This is intentionally the first business read after the new VM starts.
    original = f.api.get(f"/documents/{identifier(state['documents'][0]['id'])}")
    immutable_document(state["documents"][0], original)
    if mode in ("settled", "closed"):
        retained_projection(f.statement(state["buyer"]), state["statement"], "upgrade changed retained funds")
        actual_effects = {e['id']: e for e in f.effects()}
        old_effects = {e['id']: e for e in state['effects']}
        equal(set(actual_effects), set(old_effects), 'upgrade changed journal population')
        retained_projection(actual_effects, old_effects, "upgrade changed old journals")
        f.api.at("2028-03-01")
        f.subscription(state["buyer"], price="5", starts="2028-03-01", end="2028-04-01")
        _, new = f.bill("2028-03-01", "2028-03-01")
        document_totals(new, [("invoice", 500)])
        if mode == "settled":
            f.application(state["credit"], new[0], 150, kind="credit", post="2028-03-01")
            fields(f.statement(state["buyer"]), dict(ar_minor=350, available_backed_minor=0,
                   cash_received_minor=state["expected"], cash_refunded_minor=50), "continued old credit on new sale")
        else:
            closed_unchanged(state["closed"], f.report("2028-02"))
            fields(f.statement(state["buyer"]), dict(ar_minor=state["expected"]+500), "old debt plus new sale")
        immutable_document(state["documents"][0], f.api.get(f"/documents/{identifier(state['documents'][0]['id'])}"))
        return
    if mode == "draft":
        f.api.action(f"/bill-runs/{identifier(state['run']['id'])}/post", dict(result_keys=None))
        documents = [f.api.get(f"/documents/{identifier(d['id'])}") for d in state["documents"]]
        require(all(d["status"] == "posted" for d in documents), "old draft did not post")
    else:
        _, documents = f.bill("2028-02-01", "2028-02-01")
    document_totals(documents, [("invoice", state["expected"])])
    equal([x["id"] for x in f.api.all("/subscriptions")], state["source_ids"], "upgrade recreated subscriptions")
    equal(f.statement(state["buyer"])["ar_minor"], state["expected"], "continued historical debt")
    old_effects = {e["id"]: e for e in state["effects"]}
    actual = {e["id"]: e for e in f.effects()}
    for key, value in old_effects.items():
        retained_projection(actual.get(key), value, "upgrade changed immutable old effect")
    if mode == "reversed":
        current_units = f.units()
        for label, rows in (("retained", state["units"]), ("current", current_units)):
            for index, row in enumerate(rows):
                integer_fields(row, ("earned_minor",), f"{label} revenue unit {index}")
        before = {u["scope_key"]: u["earned_minor"] for u in state["units"]}
        after = {u["scope_key"]: u["earned_minor"] for u in current_units}
        equal(after, before, "rebilling through upgrade changed recognized service")


def execute_history(runtime, secret, old_milestone, snapshots, mode, directory):
    trace, stage, started = [], "old_version_setup", time.monotonic()
    result = dict(key=f"m{old_milestone}-to-m{max(snapshots)}-{mode}", old_milestone=old_milestone,
                  versions=list(snapshots), mode=mode)
    try:
        f = Fixture(runtime.base_url, secret, result["key"], trace)
        state = prepare(f, old_milestone, mode)
        for milestone, snapshot in sorted(snapshots.items()):
            stage = f"upgrade_to_{milestone}"
            runtime.upgrade(snapshot)
        stage = "first_cold_request_and_continuation"
        resume(f, state, mode)
        result["status"] = "passed"
    except Mismatch as exc:
        result.update(status="failed", error=str(exc))
    except Exception as exc:
        result.update(status="error", error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    result.update(stage=stage, seconds=round(time.monotonic() - started, 3))
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    (path / (result["key"] + ".json")).write_text(json.dumps(dict(result=result, trace=trace), indent=2) + "\n")
    return result
