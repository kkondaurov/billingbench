"""Historical corrections against paid and closed state, not rewritten invoices."""

import copy

from .checks import closed_unchanged, document_totals, equal, fields, require
from .client import identifier
from .m1 import immutable_document
from .m5 import enterprise_history, minimum_fixture, read_grant
from .suite import case


def correction(f, body, change, date="2028-03-01", key=None, preview_only=False):
    proposed = dict(key=key or f.key("correction"), reason="Correct recorded usage", posting_date=date, change=change)
    before = (f.api.all("/documents"), f.effects())
    preview = f.api.preview("/correction-previews", proposed)
    equal((f.api.all("/documents"), f.effects()), before, "correction preview mutated state")
    equal(preview["issues"], [], "correction preview issues")
    for effect in preview["result"]["effects"]:
        equal(effect["target_minor"] - effect["old_minor"], effect["delta_minor"], "impact arithmetic")
    if preview_only:
        return proposed, preview
    result = f.api.create("/corrections", dict(proposed, basis_token=preview["basis_token"]))
    return result, preview


@case("minimum-offsetting-correction", 6, "B27", "M6-01 M6-06 M6-10 M6-19 M6-20",
      "Unchanged total consideration still requires separately attributed credit and debit effects")
def minimum_correction(c):
    f = c.f
    u, minimum, original = minimum_fixture(f)
    f.create("/period-closes", month="2028-01")
    closed = f.report("2028-01")
    documents = copy.deepcopy(f.api.all("/documents"))
    c.checkpoint("correct_two_opposing_components")
    event = dict(original, key="correction-event", revision=2, quantity="60")
    correction(f, {}, dict(kind="source", source_id=u.source["id"], event=event), date="2028-02-01")
    m = f.api.get(f"/minimum-agreements/{identifier(minimum['id'])}")
    fields(m, dict(qualifying_minor=6000, residual_minor=4000, billed_minor=4000, earned_minor=4000), "corrected minimum")
    ids = {d["id"] for d in documents}
    after = f.api.all("/documents")
    additions = [d for d in after if d["id"] not in ids]
    document_totals(additions, [("credit", 1000), ("debit", 1000)])
    for d in documents:
        immutable_document(d, next(a for a in after if a["id"] == d["id"]))
    closed_unchanged(closed, f.report("2028-01"))
    equal(sum(r["overage_minor"] for r in u.rows()), 6000, "corrected source overage")


@case("correction-through-replacement", 6, "B25", "M6-03 M6-05 M6-07 M6-08 M6-09 M6-10 M6-13 M6-15 M6-20",
      "A historical source revision changes other consumers and derived successor rights, retaining agreements")
def replacement_correction(c):
    f = c.f
    h = enterprise_history(f)
    f.create("/period-closes", month="2028-01")
    f.create("/period-closes", month="2028-02")
    closed = {m: f.report(m) for m in ("2028-01", "2028-02")}
    old_documents = copy.deepcopy(f.api.all("/documents"))
    old_ids = {d["id"] for d in old_documents}
    c.checkpoint("nonlocal_reconstruction")
    event = dict(h["original_event"], key="revised-b", revision=2, quantity="10")
    correction(f, {}, dict(kind="source", source_id=h["pooled"].source["id"], event=event))
    g0, g1 = read_grant(f, h["g0"]), read_grant(f, h["g1"])
    fields(g0, dict(basis_recognized_minor=10400, status="superseded"), "corrected predecessor earnings")
    fields(g1, dict(face_remaining_minor=0, basis_minor=10600, basis_recognized_minor=10600), "corrected successor")
    equal(g1["id"], h["g1"]["id"], "successor identity changed")
    equal(len(f.api.all("/grants")), 2, "correction created another grant")
    equal(len(f.api.all("/amendments")), 1, "source correction became renegotiation")
    equal(sum(r["overage_minor"] for r in h["later"].rows()), 8000, "untouched later consumer repriced")
    additions = [d for d in f.api.all("/documents") if d["id"] not in old_ids]
    document_totals(additions, [("credit", 2200), ("debit", 1600)])
    equal(next(d for d in additions if d["kind"] == "credit")["customer_id"], h["b"]["id"], "credit debtor")
    equal(next(d for d in additions if d["kind"] == "debit")["customer_id"], h["c"]["id"], "later debit debtor")
    for month, before in closed.items():
        closed_unchanged(before, f.report(month))
    c.checkpoint("second_revision_uses_last_accepted_baseline")
    before_ids = {d["id"] for d in f.api.all("/documents")}
    event2 = dict(event, key="second-b", revision=3, quantity="20")
    correction(f, {}, dict(kind="source", source_id=h["pooled"].source["id"], event=event2))
    second = [d for d in f.api.all("/documents") if d["id"] not in before_ids]
    document_totals(second, [("debit", 600), ("credit", 1600)])
    fields(read_grant(f, h["g1"]), dict(face_remaining_minor=0, basis_minor=11880), "restored economics, retained successor")
    current = {d["id"]: d for d in f.api.all("/documents")}
    for original in old_documents:
        immutable_document(original, current[original["id"]])


@case("correction-token-binding", 6, "B26", "C04 C06 M6-01 M6-02 M6-24", "A preview token cannot authorize a different fact under an unchanged database")
def token_binding(c):
    f = c.f
    u, minimum, original = minimum_fixture(f)
    event = dict(original, key="proposal", revision=2, quantity="60")
    change = dict(kind="source", source_id=u.source["id"], event=event)
    proposed, preview = correction(f, {}, change, date="2028-02-01", preview_only=True)
    before = (f.api.all("/documents"), f.effects())
    c.checkpoint("token_binds_input")
    altered = dict(proposed, change=dict(change, event=dict(event, quantity="65")), basis_token=preview["basis_token"])
    f.api.error("POST", "/corrections", altered, 409, "stale_basis")
    equal((f.api.all("/documents"), f.effects()), before, "wrong-token rejection changed state")
    accepted = f.api.create("/corrections", dict(proposed, basis_token=preview["basis_token"]), key="accepted-correction")
    count = len(f.api.all("/documents"))
    replay = f.api.request("POST", "/corrections", dict(proposed, basis_token="obsolete-token"), status=201, key="accepted-correction")
    equal(replay["data"]["id"], accepted["id"], "accepted correction replay precedes token guard")
    equal(len(f.api.all("/documents")), count, "correction replay duplicated documents")


@case("expired-basis-category-correction", 6, "B27", "M6-14 M6-19 M6-20", "Correcting expired capacity moves revenue categories without restoring spendable rights")
def expired_basis(c):
    from .m2 import Usage
    from .m5 import grant
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000)
    f.api.at("2028-02-01")
    original, _ = u.event("work", "80")
    u.finish()
    f.create("/grant-expirations", through="2028-02-01", posting_date="2028-02-01")
    original_effects = {e["id"] for e in f.effects()}
    c.checkpoint("consumption_expiry_offset")
    correction(f, {}, dict(kind="source", source_id=u.source["id"], event=dict(original, key="revised", revision=2, quantity="60")), date="2028-02-01")
    effects = [e for e in f.effects() if e["id"] not in original_effects]
    equal(sum(e["amount_minor"] for e in effects if e["kind"] == "capacity_consumption"), -1600, "corrected consumed basis")
    equal(sum(e["amount_minor"] for e in effects if e["kind"] == "capacity_expiry"), 1600, "corrected expired basis")
    fields(read_grant(f, g), dict(status="expired", basis_recognized_minor=8000, basis_unearned_minor=0), "expired rights remain unavailable")


def reclassification_case(routing):
    @case(f"reclassification-correction-{routing}", 6, "B31", "M6-16 M6-17 M6-18 M6-19", "Correction offsets the actually reclassified account, not a superseded chart mapping")
    def run(c):
        from .m1 import base
        from .checks import distribution
        f, buyer, sub, old_addresses = base(c)
        f.bill()
        f.recognition("2028-01-31")
        f.api.at("2028-02-01")
        f.create("/period-closes", month="2028-01")
        closed = f.report("2028-01")
        before_chart = f.effects()
        chart, new_addresses = f.chart(effective="2028-02-01", prefix="replacement", routing=routing)
        equal(f.effects(), before_chart, "publishing a chart moved historical balances")
        recognized = [e for e in before_chart if e["kind"] == "recognition"]
        require(recognized, "recognition positive control missing")
        body = dict(key="reclassify", scope=dict(currency="USD", scope_keys=None, effect_ids=[e["id"] for e in recognized],
                    economic_window=None), configuration_id=chart["id"], posting_date="2028-02-01")
        preview = f.api.preview("/reclassification-previews", body)
        f.api.create("/reclassifications", dict(body, basis_token=preview["basis_token"]))
        after_reclass = {e["id"] for e in f.effects()}
        # A third chart makes original and current routing observably different.
        f.api.at("2028-02-02")
        _, current_addresses = f.chart(effective="2028-02-02", prefix="current", routing=routing)
        c.checkpoint("correct_latest_accepted_distribution")
        correction(f, {}, dict(kind="recorded_term", resource=dict(kind="subscription", id=sub["id"]),
                               path=["charges", "base", "price"], replacement="80"), date="2028-02-02")
        recognition = [e for e in f.effects() if e["id"] not in after_reclass and e["kind"] == "recognition"]
        require(recognition, "correction emitted no recognition adjustment")
        revenue_legs = [l for e in recognition for l in e["legs"] if l["function"] == "service_revenue"]
        expected = {(new_addresses["service_revenue"], ()): 2000} if routing == "original" else {
            (new_addresses["service_revenue"], ()): 10000,
            (current_addresses["service_revenue"], ()): -8000}
        distribution(revenue_legs, expected, "post-reclassification revenue correction")
        require(all(e['economic_date'].startswith('2028-01-') and e['posting_date'] == '2028-02-02'
                    for e in recognition), 'correction retains January economics in February posting')
        own_scopes = {row['scope_key'] for row in f.units(sub, through='2028-01-31')}
        require(all(e['scope_key'] in own_scopes for e in recognition), 'correction revenue belongs to its unit')
        closed_unchanged(closed, f.report("2028-01"))
        fields(f.statement(buyer), dict(ar_minor=8000), "corrected consideration")
    return run


reclassification_case("original")
reclassification_case("current")


@case("paid-correction-refund-next-revision", 6, "B26", "M6-11 M6-12 M6-13 M6-24", "A later debit is based on the last correction and preserves actual refunded cash")
def paid_correction(c):
    from .m2 import Usage
    f = c.f
    f.chart()
    u = Usage(f)
    original, _ = u.event("work", "40")
    _, docs = u.finish()
    document_totals(docs, [("invoice", 4000)], "linked paid-correction invoice")
    invoice = docs[0]
    receipt = f.receipt(u.customers[0], 4000, post="2028-02-01")
    f.application(receipt, invoice, 4000, post="2028-02-01")
    ids = {d["id"] for d in f.api.all("/documents")}
    c.checkpoint("paid_credit_and_real_refund")
    change = dict(kind="source", source_id=u.source["id"], event=dict(original, key="first", revision=2, quantity="10"))
    correction(f, {}, change, date="2028-02-01")
    credits = [d for d in f.api.all("/documents") if d["id"] not in ids]
    document_totals(credits, [("credit", 3000)])
    f.create("/refunds", source=dict(kind="credit", id=credits[0]["id"]), amount_minor=500, posting_date="2028-02-01")
    fields(f.statement(u.customers[0]), dict(ar_minor=0, available_backed_minor=2500, cash_refunded_minor=500), "first corrected/refunded state")
    ids = {d["id"] for d in f.api.all("/documents")}
    c.checkpoint("second_revision_relative_to_first")
    correction(f, {}, dict(change, event=dict(original, key="second", revision=3, quantity="20")), date="2028-02-01")
    new = [d for d in f.api.all("/documents") if d["id"] not in ids]
    document_totals(new, [("debit", 1000)])
    fields(f.statement(u.customers[0]), dict(cash_received_minor=4000, cash_refunded_minor=500), "cash history unchanged")
    immutable_document(invoice, f.api.get(f"/documents/{identifier(invoice['id'])}"))


@case("historical-fixed-budget-redistribution", 6, "B25", "M6-04 M6-10 M6-24", "Correcting one accepted charge reallocates a retained discount on another")
def fixed_discount(c):
    from .m3 import discount, order
    f = c.f
    f.chart()
    buyer = f.customer()
    a, _, _ = f.subscription(buyer, price="150")
    b, _, _ = f.subscription(buyer, price="50")
    d = discount(f, buyer, budget=4000)
    for sub in (a, b):
        order(f, sub, "2028-01-01", [dict(kind="attach_discount", discount_id=d["id"])])
    f.api.at("2028-02-01")
    _, initial = f.bill("2028-02-01", "2028-02-01")
    f.recognition("2028-01-31", "2028-02-01")
    ids = {d["id"] for d in initial}
    c.checkpoint("correct_one_charge_reallocate_shared_budget")
    correction(f, {}, dict(kind="recorded_term", resource=dict(kind="subscription", id=a["id"]),
                           path=["charges", "base", "price"], replacement="250"), date="2028-02-01")
    rows = f.units()
    equal(sum(r["net_minor"] for r in rows if r["subscription_id"] == a["id"]), 21667, "changed discounted service")
    equal(sum(r["net_minor"] for r in rows if r["subscription_id"] == b["id"]), 4333, "unchanged service reallocated discount")
    new = [d for d in f.api.all("/documents") if d["id"] not in ids]
    equal(sum(d["total_minor"] for d in new), 10000, "total increase")
    require(all(d["kind"] == "debit" for d in new), "historical billed correction must use debit memos")
    by_sub = {}
    for doc in new:
        for item in doc["items"]:
            by_sub[item["subscription_id"]] = by_sub.get(item["subscription_id"], 0) + item["amount_minor"]
    equal(by_sub, {a["id"]: 9667, b["id"]: 333}, "component debit attribution")


@case("closed-current-reconciliation", 6, "B28", "M6-19 M6-20", "Closed posting history and corrected economic history reconcile without becoming the same report")
def report_reconciliation(c):
    from .m1 import base, economics
    from .fixtures import currency_report
    f, buyer, sub, addr = base(c)
    _, docs = f.bill()
    document_totals(docs, [("invoice", 10000)], "linked original invoice")
    f.recognition("2028-01-31")
    f.api.at("2028-02-01")
    f.create("/period-closes", month="2028-01")
    closed = f.report("2028-01")
    c.checkpoint("historical_price_change_in_open_month")
    _, preview = correction(f, {}, dict(kind="recorded_term", resource=dict(kind="subscription", id=sub["id"]),
                           path=["charges", "base", "price"], replacement="80"), date="2028-02-01")
    from .impacts import closed_sale_impact
    closed_sale_impact(preview, buyer['id'], addr)
    economics(f, 8000, 8000, sub)
    fields(f.statement(buyer), dict(ar_minor=8000, cash_received_minor=0, cash_refunded_minor=0), "unpaid corrected sale")
    closed_unchanged(closed, f.report("2028-01"))
    immutable_document(docs[0], f.api.get(f"/documents/{identifier(docs[0]['id'])}"))
    current = currency_report(f.report("2028-01", "current"))
    accounts = {r["account_key"]: r for r in current["accounts"] if not r["segments"]}
    # The corrective credit belongs to January; its automatic application can
    # retain February's settlement date under the ordinary application rule.
    equal(sum(accounts.get(addr[k], {}).get("closing_net_debit_minor", 0)
              for k in ("receivable", "customer_funds")), 8000,
          "current January receivable less customer credit")
    fields(accounts.get(addr["service_revenue"]), dict(opening_net_debit_minor=0, closing_net_debit_minor=-8000), "current January revenue")
    equal(sum(r["billed_minor"] for r in current["units"]), 8000, "current January billed scopes")
    equal(sum(r["earned_minor"] for r in current["units"]), 8000, "current January earned scopes")
    february = currency_report(f.report("2028-02"))
    accounts = {r["account_key"]: r for r in february["accounts"] if not r["segments"]}
    fields(accounts.get(addr["receivable"]), dict(opening_net_debit_minor=10000,
           net_debit_minor=-2000, closing_net_debit_minor=8000), "February receivable adjustment")
    fields(accounts.get(addr["service_revenue"]), dict(opening_net_debit_minor=-10000,
           net_debit_minor=2000, closing_net_debit_minor=-8000), "February revenue adjustment")


def frozen_export_routing(routing):
    @case("frozen-export-routing-" + routing, 6, "B32", "M6-16 M6-18 M6-21", "New corrections obey routing policy without rewriting an existing export's historical addresses")
    def run(c):
        from .m1 import base
        from .checks import distribution
        from .integrity import exported_entries_match
        f, buyer, sub, old = base(c)
        f.bill()
        f.recognition("2028-01-31")
        original = f.effects()
        batch = f.create("/exports", currency="USD", posting_window=dict(starts_on="2028-01-01", ends_before="2028-02-01"))
        exported_entries_match(f, batch["payload"], original)
        f.api.at("2028-02-01")
        f.create("/period-closes", month="2028-01")
        f.chart(effective="2028-02-01", prefix="new", routing=routing)
        equal(f.effects(), original, "chart publication remapped old books")
        c.checkpoint("correction_routing_and_frozen_export")
        correction(f, {}, dict(kind="recorded_term", resource=dict(kind="subscription", id=sub["id"]),
                               path=["charges", "base", "price"], replacement="80"), date="2028-02-01")
        old_ids = {e["id"] for e in original}
        added = [e for e in f.effects() if e["id"] not in old_ids]
        legs = [leg for e in added if e["kind"] == "recognition" for leg in e["legs"] if leg["function"] == "service_revenue"]
        expected = {(old["service_revenue"], ()): 2000} if routing == "original" else {
            (old["service_revenue"], ()): 10000, ("new-service_revenue", ()): -8000}
        distribution(legs, expected, "correction's actual old and target revenue addresses")
        saved = f.api.get(f"/exports/{identifier(batch['id'])}")
        fields(saved, {k: batch[k] for k in ("payload", "digest", "entry_ids")}, "frozen historical batch")
        current = {e["id"]: e for e in f.effects()}
        for effect in original:
            equal(current[effect["id"]], effect, "old effect provenance changed")
        next_batch = f.create("/exports", currency="USD", posting_window=dict(starts_on="2028-02-01", ends_before="2028-03-01"))
        exported_entries_match(f, next_batch["payload"], added)
    return run


frozen_export_routing("original")
frozen_export_routing("current")
