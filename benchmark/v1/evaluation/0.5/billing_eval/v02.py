"""Boundary and control histories introduced for 0.2. Independent expected economics."""

import copy
from fractions import Fraction

from .checks import customer_documents, document_totals, equal, fields, closed_unchanged
from .client import identifier
from .m1 import immutable_document
from .m2 import Usage, measured
from .m5 import grant, read_grant
from .m6 import correction
from .funding_interactions import shared_discount
from .interactions import retry_orders
from .oracles import allocate, money
from .suite import case


@case("v02-linear-withdrawal-and-empty-completion", 1, "B05", "source", "Zero source input must be certified, not assumed")
def linear_empty(c):
    f = c.f
    f.chart()
    u = Usage(f)
    body = dict(key="waiting", customer_ids=None, target_date="2028-02-01",
                invoice_date="2028-02-01", posting_date="2028-02-01")
    pending = f.api.request("POST", "/bill-runs", body, status=200)
    equal(pending["operation"]["status"], "held", "unknown feed")
    u.event("work", "9.125")
    f.api.create(f"/sources/{identifier(u.source['id'])}/events",
                 dict(key="withdraw", event_key="work", revision=2, state="withdrawn"))
    u.complete()
    c.checkpoint("complete_empty_not_unknown")
    f.api.action(f"/bill-runs/{identifier(pending['data']['id'])}/retry", dict(mode="generate"))
    f.post_bill(pending["data"])
    equal(measured(u.rows()), 0, "withdrawn fact is not active")
    equal(f.statement(u.customers[0])["ar_minor"], 0, "empty complete source is not charged")
    equal(sum(d["total_minor"] for d in f.api.all("/documents")), 0, "no fabricated minimum")


def target(a, b, budget=1800):
    rate = Fraction(3, 4) if a + b >= 100 else Fraction(1)
    gross = {"a": money(a * rate * 100), "b": money(b * rate * 100)}
    shares = allocate(budget, gross)
    return tuple(gross[k] - shares[k] for k in ("a", "b"))


def setup_pool(f, parent_payer=False):
    f.chart(capacity=True)
    root = f.customer("enterprise")
    a, b, other = [f.customer(key, root["id"]) for key in ("a", "b", "outside")]
    u = Usage(f, customers=[a, b], owner=root, count=2, model="volume",
              bands=[dict(up_to="100", unit_price="1"), dict(up_to=None, unit_price="0.75")])
    f.api.at("2028-01-01")
    if parent_payer:
        f.create("/payer-policies", consumer_customer_id=a["id"], product_ids=[u.product["id"]],
                 window=u.window, payer_customer_id=root["id"])
    shared_discount(f, [a, b], u.subscriptions, amount=1800)
    g = grant(f, root, [u.consumers[0]], u.product, 4900, 3500, end="2028-03-01")
    f.subscription(other, price="11")
    f.api.at("2028-02-01")
    u.event("a-use", "75", project=0)
    original, _ = u.event("b-use", "45", project=1)
    u.complete()
    retry_orders(f)
    u.finish()
    return u, root if parent_payer else a, b, other, g, original


def debtor_case(parent, boundary):
    label = "v02-debtor-" + ("boundary" if boundary else "control") + ("-parent" if parent else "-self")
    @case(label, 5, "B25", "ownership", "Same pricing change, explicit independent debtor; a nearby control retains existing coverage")
    def run(c):
        f = c.f
        u, payer, b, other, g, event = setup_pool(f, parent)
        initial = target(75, 45)
        equal(initial, (4500, 2700), "hand-checked baseline")
        docs = copy.deepcopy(f.api.all("/documents"))
        statement = f.statement(other)
        quantity = 5 if boundary else 46
        expected = target(75, quantity)
        f.create("/period-closes", month="2028-01")
        closed = f.report("2028-01")
        c.checkpoint("new_debt_belongs_to_service_payer")
        correction(f, {}, dict(kind="source", source_id=u.source["id"],
                   event=dict(event, key="new-reading", revision=2, quantity=str(quantity))), date="2028-02-01")
        ids = {d["id"] for d in docs}
        issued = [d for d in f.api.all("/documents") if d["id"] not in ids]
        debt_a = max(expected[0] - 4900, 0)
        delta_b = expected[1] - initial[1]
        wanted = [(payer["id"], "debit", debt_a)] if debt_a else []
        if delta_b:
            wanted.append((b["id"], "debit" if delta_b > 0 else "credit", abs(delta_b)))
        customer_documents(issued, wanted, "customer-specific adjustments")
        for buyer, amount in zip(u.customers, expected):
            equal(sum(r["net_minor"] for r in u.rows() if r["customer_id"] == buyer["id"]), amount, "rated owner")
        used = min(expected[0], 4900)
        fields(read_grant(f, g), dict(face_remaining_minor=4900-used,
               basis_recognized_minor=money(Fraction(used * 3500, 4900))), "capacity target")
        equal(f.statement(other), statement, "outside sharing scope")
        closed_unchanged(closed, f.report("2028-01"))
        for doc in docs:
            immutable_document(doc, f.api.get(f"/documents/{identifier(doc['id'])}"))
    return run


for parent in (False, True):
    for boundary in (False, True):
        debtor_case(parent, boundary)


@case("v02-correction-refund-restoration", 5, "B26", "settled-correction", "Restoring usage does not restore cash already refunded under a valid intervening correction")
def restored(c):
    f = c.f
    u, payer, b, other, g, event = setup_pool(f, True)
    invoices = [d for d in f.api.all("/documents") if d["customer_id"] == b["id"] and d["kind"] == "invoice"]
    document_totals(invoices, [("invoice", 2700)])
    receipt = f.receipt(b, 2700, post="2028-02-01")
    f.application(receipt, invoices[0], 2700, post="2028-02-01")
    old = {d["id"] for d in f.api.all("/documents")}
    revision = dict(event, key="corrected", revision=2, quantity="5")
    correction(f, {}, dict(kind="source", source_id=u.source["id"], event=revision), date="2028-02-01")
    docs = [d for d in f.api.all("/documents") if d["id"] not in old]
    customer_documents(docs, [(payer["id"], "debit", 912), (b["id"], "credit", 2312)])
    credit = next(d for d in docs if d["kind"] == "credit")
    f.create("/refunds", source=dict(kind="credit", id=credit["id"]), amount_minor=700, posting_date="2028-02-01")
    refunds = copy.deepcopy(f.api.all("/refunds"))
    old = {d["id"] for d in f.api.all("/documents")}
    c.checkpoint("restore_usage_not_refunded_cash")
    correction(f, {}, dict(kind="source", source_id=u.source["id"],
               event=dict(event, key="restored", revision=3, quantity="45")), date="2028-02-01")
    docs = [d for d in f.api.all("/documents") if d["id"] not in old]
    customer_documents(docs, [(payer["id"], "credit", 912), (b["id"], "debit", 2312)])
    equal(f.api.all("/refunds"), refunds, "historic refund is not rolled back")
    fields(f.statement(b), dict(cash_received_minor=2700, cash_refunded_minor=700), "real cash")
    fields(read_grant(f, g), dict(face_remaining_minor=400,
           basis_recognized_minor=money(Fraction(4500*3500, 4900))), "restored pricing, retained cash")


@case("v02-correction-token-and-isolation", 5, "B26", "atomic-correction", "A token binds its fact, but an unrelated customer does not stale it")
def token_scope(c):
    f = c.f
    f.chart()
    u = Usage(f)
    event, _ = u.event("work", "17")
    u.finish()
    proposed, preview = correction(f, {}, dict(kind="source", source_id=u.source["id"],
        event=dict(event, key="changed", revision=2, quantity="11")), date="2028-02-01", preview_only=True)
    before = (f.api.all("/documents"), f.effects())
    altered = copy.deepcopy(proposed)
    altered["change"]["event"]["quantity"] = "12"
    f.api.error("POST", "/corrections", dict(altered, basis_token=preview["basis_token"]), 409, "stale_basis")
    equal((f.api.all("/documents"), f.effects()), before, "rejected proposal is inert")
    f.customer("unrelated-new-customer")
    c.checkpoint("unrelated_state_is_not_a_dependency")
    accepted = f.api.create("/corrections", dict(proposed, basis_token=preview["basis_token"]), key="accept")
    document_totals([d for d in f.api.all("/documents") if d["id"] not in {d["id"] for d in before[0]}], [("credit", 600)])
    after = (f.api.all("/documents"), f.effects())
    # Acceptance changes the relevant basis; replay the identical request/token.
    replay = f.api.create("/corrections", dict(proposed, basis_token=preview["basis_token"]), key="accept")
    equal(replay["id"], accepted["id"], "replay precedes token check")
    equal((f.api.all("/documents"), f.effects()), after, "replay has no second effect")
