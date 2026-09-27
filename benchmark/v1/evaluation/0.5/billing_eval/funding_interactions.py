"""Pricing, entitlement, settlement and correction histories from X24-X38."""

import copy

from .checks import earned_minor, document_totals, equal, fields, require, closed_unchanged, distribution, customer_documents
from .client import identifier
from .m1 import immutable_document, single
from .m2 import Usage
from .m3 import order
from .m4 import amend, apply
from .m5 import grant, read_grant
from .m6 import correction
from .suite import case
from .interactions import pending_order, retry_orders
from .scopes import chain_carries


def agreement_terms(agreement, keys):
    retained = agreement.get("input", agreement)
    require(isinstance(retained, dict), "amendment missing retained input")
    require(all(key in retained for key in keys), "amendment missing retained commercial fields")
    return {key: copy.deepcopy(retained[key]) for key in keys}


def shared_discount(f, customers, subscriptions, amount=2400, percentage=None):
    d = f.create("/discounts", currency="USD", window=dict(starts_on="2028-01-01", ends_before="2028-02-01"), priority=1,
                 scope=dict(customer_ids=[b["id"] for b in customers], subscription_ids=[], plan_keys=[], product_ids=[], charge_keys=[]),
                 kind="fixed" if percentage is None else "percentage", budget_minor=amount if percentage is None else None,
                 percentage_group=None if percentage is None else dict(mode="sequential", percentages=[percentage]), partial_window="fixed")
    for s in subscriptions:
        pending_order(f, s, "2028-01-01", [dict(kind="attach_discount", discount_id=d["id"])])
    return d


def pooled_fixture(f, reduction=True, funding=True, unrelated=False):
    f.chart(capacity=True)
    root = f.customer("root")
    a, b = [f.customer(key, root["id"]) for key in ("a", "b")]
    u = Usage(f, customers=[a, b], owner=root, count=2, model="volume",
              bands=[dict(up_to="100", unit_price="1"), dict(up_to=None, unit_price="0.8")])
    f.api.at("2028-01-01")
    d = shared_discount(f, [a, b], u.subscriptions) if reduction else None
    g = grant(f, root, [u.consumers[0]], u.product, 5000, 4000, end="2028-03-01") if funding else None
    other = None
    if unrelated:
        other = f.customer("untouched", root["id"])
        f.subscription(other, price="40")
    f.api.at("2028-02-01")
    u.event("a-work", "80", project=0)
    original, _ = u.event("b-work", "40", project=1)
    u.complete()
    retry_orders(f)
    u.finish()
    return dict(root=root, a=a, b=b, u=u, grant=g, discount=d, event=original, other=other)


def pool_postings(effects, rows, customers, overages, grant_scope=None, basis=0):
    """Assert actual journal targets, not only self-reported rating/grant totals."""
    expected_scopes = set()
    for buyer, amount in zip(customers, overages):
        scopes = {r['scope_key'] for r in rows if r['customer_id'] == buyer['id']}
        require(scopes, 'pool customer has no published usage scope')
        expected_scopes.update(scopes)
        matching = [e for e in effects if e['kind'] == 'unfunded_usage' and e['scope_key'] in scopes]
        equal(sum(e['amount_minor'] for e in matching), amount, 'posted pooled overage')
        distribution([leg for e in matching for leg in e['legs'] if leg['function'] == 'service_revenue'],
                     {('book-service_revenue', ()): -amount}, 'pooled overage revenue address')
    usage = [e for e in effects if e['kind'] == 'unfunded_usage']
    require(all(e['scope_key'] in expected_scopes for e in usage), 'usage posted to an unrelated scope')
    capacity = [e for e in effects if e['kind'] == 'capacity_consumption']
    require(all(e['scope_key'] == grant_scope for e in capacity), 'basis posted to an unrelated grant')
    equal(sum(e['amount_minor'] for e in capacity), basis, 'posted pooled capacity basis')
    distribution([leg for e in capacity for leg in e['legs'] if leg['function'] == 'service_revenue'],
                 {('book-service_revenue', ()): -basis}, 'pooled capacity revenue address')
    require(all(e['economic_date'] == '2028-01-20' and e['posting_date'] == '2028-02-01'
                for e in usage + capacity), 'pool postings retain service date and open posting date')


def pool_correction(quantity, reduction=True, funding=True):
    label = f"interaction-pool-correction-{quantity}-discount-{int(reduction)}-funding-{int(funding)}"
    @case(label, 6, "B25", "M6-03 M6-04 M6-05 M6-10 M6-24",
          "X30/X38: a sibling's revision changes tier, shared discount, grant draw and overage")
    def run(c):
        f = c.f
        h = pooled_fixture(f, reduction, funding, unrelated=True)
        u, a, b = h["u"], h["a"], h["b"]
        before = copy.deepcopy(f.api.all("/documents"))
        untouched = f.statement(h["other"])
        f.create("/period-closes", month="2028-01")
        closed = f.report("2028-01")
        initial = (4800, 2400) if reduction else (6400, 3200)
        for buyer, net in zip((a, b), initial):
            equal(sum(r["net_minor"] for r in u.rows() if r["customer_id"] == buyer["id"]), net, "initial child net")
        if funding:
            fields(read_grant(f, h["grant"]), dict(face_remaining_minor=5000-min(initial[0], 5000),
                   basis_recognized_minor=3840 if reduction else 4000), "initial funding")
        initial_overages = [max(initial[0]-5000, 0) if funding else initial[0], initial[1]]
        grant_scope = h['grant']['scope_key'] if funding else None
        initial_journal = copy.deepcopy(f.effects())
        pool_postings(initial_journal, u.rows(), [a, b], initial_overages, grant_scope,
                      (3840 if reduction else 4000) if funding else 0)
        c.checkpoint("correct_sibling_recompute_entire_pipeline")
        correction(f, {}, dict(kind="source", source_id=u.source["id"],
                   event=dict(h["event"], key="changed-b", revision=2, quantity=quantity)), date="2028-02-01")
        # Independent hand-calculated pairs: band-preserving 41 is a close control.
        target = {("10", True): (5867, 733), ("41", True): (4813, 2467),
                  ("10", False): (8000, 1000)}[(quantity, reduction)]
        for buyer, net in zip((a, b), target):
            equal(sum(r["net_minor"] for r in u.rows() if r["customer_id"] == buyer["id"]), net, "corrected child net")
            expected_overage = max(net-5000, 0) if funding and buyer["id"] == a["id"] else net
            equal(sum(r["overage_minor"] for r in u.rows() if r["customer_id"] == buyer["id"]), expected_overage, "corrected child debt")
        if funding:
            used = min(target[0], 5000)
            # 4813 * 0.8 is 3850.4 cents; one cumulative rounding gives 3850.
            fields(read_grant(f, h["grant"]), dict(face_remaining_minor=5000-used,
                   basis_recognized_minor=3850 if quantity == "41" else 4000), "corrected funded basis")
        ids = {d["id"] for d in before}
        issued = [d for d in f.api.all("/documents") if d["id"] not in ids]
        target_overages = [max(target[0]-5000, 0) if funding else target[0], target[1]]
        expected_docs = [(buyer['id'], 'debit' if new > old else 'credit', abs(new-old))
                         for buyer, old, new in zip((a, b), initial_overages, target_overages) if old != new]
        customer_documents([d for d in issued if d['total_minor']], expected_docs, 'corrected sibling documents')
        require(all(all(i['amount_minor'] == 0 for i in d['items']) for d in issued if not d['total_minor']),
                'zero document hides nonzero components')
        journal = f.effects()
        pool_postings(journal, u.rows(), [a, b], target_overages, grant_scope,
                      (3850 if quantity == '41' else 4000) if funding else 0)
        now = {e['id']: e for e in journal}
        for old in initial_journal:
            equal(now.get(old['id']), old, 'pool correction preserves original journal entries')
        equal(f.statement(h["other"]), untouched, "unrelated customer changed")
        closed_unchanged(closed, f.report("2028-01"))
        for d in before:
            immutable_document(d, f.api.get(f"/documents/{identifier(d['id'])}"))
        reader = f.api.actor("customer", a["id"])
        reader.hidden_collection("/corrections")
    return run


pool_correction("10")
pool_correction("41")
pool_correction("10", reduction=False)
pool_correction("10", funding=False)


def priority_case(promo_first):
    @case(f"interaction-discounted-pool-{'promo' if promo_first else 'paid'}-first", 5, "B19",
          "M5-01 M5-07 M5-08 M5-09 M5-12", "X25: window allowance and discount reduce the amount funded in priority order")
    def run(c):
        f = c.f
        f.chart(capacity=True)
        u = Usage(f, included="20", model="volume", bands=[dict(up_to="100", unit_price="1"), dict(up_to=None, unit_price="0.8")])
        f.api.at("2028-01-01")
        shared_discount(f, u.customers, u.subscriptions, percentage="10")
        p = grant(f, u.customers[0], u.consumers, u.product, 2000, kind="promotional", key="promo", priority=1 if promo_first else 2)
        g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000, key="paid", priority=2 if promo_first else 1)
        f.api.at("2028-02-01")
        u.event("work", "120")
        u.complete()
        retry_orders(f)
        c.checkpoint("allowance_rate_discount_funding")
        u.finish()
        equal(sum(r["net_minor"] for r in u.rows()), 7200, "discounted pool")
        equal(sum(r["overage_minor"] for r in u.rows()), 0, "funded pool")
        fields(read_grant(f, p, "2028-01-31"), dict(face_remaining_minor=0 if promo_first else 2000, basis_recognized_minor=0), "promotional rights")
        fields(read_grant(f, g, "2028-01-31"), dict(face_remaining_minor=4800 if promo_first else 2800,
               basis_recognized_minor=4160 if promo_first else 5760), "paid basis")
        equal(sum(d["total_minor"] for d in f.api.all("/documents")), 8000, "only purchase invoiced")
    return run


priority_case(True)
priority_case(False)


@case("interaction-three-cent-funded-basis", 5, "B17", "C10 M5-09 M5-10", "X26: successive draws release cumulative basis as 1, 0, 1 cents")
def basis_cents(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    g = grant(f, u.customers[0], u.consumers, u.product, 3, 2)
    f.api.at("2028-02-01")
    for date in ("2028-01-10", "2028-01-15", "2028-01-20"):
        u.event(date, "0.01", date=date)
    u.complete()
    c.checkpoint("cumulative_basis_not_per_draw_rounding")
    for date, expected in (("2028-01-10", 1), ("2028-01-15", 1), ("2028-01-20", 2)):
        f.recognition(date, "2028-02-01")
        equal(read_grant(f, g)["basis_recognized_minor"], expected, "cumulative basis at " + date)
    draws = f.api.all("/drawdowns", grant_id=g["id"])
    equal([d["basis_minor"] for d in sorted(draws, key=lambda d: d["service_date"])], [1, 0, 1], "three independent draw attributions")


def read_order(bill_first):
    @case("interaction-funding-" + ("bill-first" if bill_first else "recognize-first"), 5, "B17", "M5-09 M5-10 M5-19",
          "R10: reads do not commit rights, and billing is not recognition")
    def run(c):
        f = c.f
        f.chart(capacity=True)
        u = Usage(f)
        f.api.at("2028-01-01")
        g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000)
        f.api.at("2028-02-01")
        u.event("work", "50")
        u.complete()
        before = (f.effects(), f.api.all("/drawdowns"), f.api.all("/documents"))
        for _ in range(2):
            read_grant(f, g, "2028-01-31")
            u.rows()
        equal((f.effects(), f.api.all("/drawdowns"), f.api.all("/documents")), before, "query committed funding")
        c.checkpoint("billing_and_recognition_order")
        if bill_first:
            f.bill("2028-02-01", "2028-02-01")
            equal(read_grant(f, g, "2028-01-31")["basis_recognized_minor"], 0, "billing recognized capacity")
        f.recognition("2028-01-31", "2028-02-01")
        if not bill_first:
            f.bill("2028-02-01", "2028-02-01")
        fields(read_grant(f, g, "2028-01-31"), dict(face_remaining_minor=5000, basis_recognized_minor=4000), "order-independent accepted economics")
        draws = f.api.all("/drawdowns")
        f.recognition("2028-01-31", "2028-02-01")
        f.bill("2028-02-01", "2028-02-01")
        equal(f.api.all("/drawdowns"), draws, "repeated operations consumed twice")
    return run


read_order(True)
read_order(False)


def minimum_components(quantity):
    @case("interaction-minimum-excludes-other-sales-" + quantity, 5, "B20", "M5-13 M5-14",
          "X27: fixed fees and capacity purchases are not minimum-qualifying usage")
    def run(c):
        f = c.f
        f.chart(capacity=True)
        u = Usage(f)
        f.api.at("2028-01-01")
        f.subscription(u.customers[0], price="50")
        unrelated_product = f.product("unrelated-meter")
        grant(f, u.customers[0], u.consumers, unrelated_product, 10000, 8000)
        m = f.create("/minimum-agreements", owner_customer_id=u.customers[0]["id"], payer_customer_id=u.customers[0]["id"], currency="USD",
                     window=u.window, consumer_ids=[x["id"] for x in u.consumers], product_ids=[u.product["id"]], minimum_minor=10000)
        f.api.at("2028-02-01")
        u.event("work", quantity)
        c.checkpoint("minimum_qualifies_usage_only")
        u.finish()
        f.recognition("2028-02-01", "2028-02-01")
        q = int(quantity) * 100
        fields(f.api.get(f"/minimum-agreements/{identifier(m['id'])}"),
               dict(qualifying_minor=q, residual_minor=max(10000-q, 0), earned_minor=max(10000-q, 0)), "residual only")
        equal(f.statement(u.customers[0])["ar_minor"], max(q, 10000)+13000, "purchase and fixed fee remain separate consideration")
    return run


for q in ("70", "100", "120"):
    minimum_components(q)


def minimum_overlap(axis):
    @case("interaction-minimum-overlap-" + axis, 5, "B20", "M5-13", "X27: minimum overlap is the intersection of time, product and consumer")
    def run(c):
        f = c.f
        f.chart(capacity=True)
        u = Usage(f, count=2)
        f.api.at("2028-01-01")
        body = dict(owner_customer_id=u.customers[0]["id"], payer_customer_id=u.customers[0]["id"], currency="USD",
                    window=u.window, consumer_ids=[u.consumers[0]["id"]], product_ids=[u.product["id"]], minimum_minor=10000)
        f.create("/minimum-agreements", **body)
        c.checkpoint("three_axis_overlap")
        if axis == "none":
            f.api.error("POST", "/minimum-agreements", dict(body, key="overlap"), 422, "invalid_domain")
        else:
            if axis == "consumer":
                body["consumer_ids"] = [u.consumers[1]["id"]]
            elif axis == "product":
                body["product_ids"] = [f.product("other")["id"]]
            else:
                body["window"] = dict(starts_on="2028-02-01", ends_before="2028-03-01")
            f.create("/minimum-agreements", **body)
            equal(len(f.api.all("/minimum-agreements")), 2, "disjoint minimum allowed")
    return run


for axis in ("none", "consumer", "product", "window"):
    minimum_overlap(axis)


def remaining_pool_correction(quantity, valid):
    @case("interaction-concession-correction-pool-" + quantity, 6, "B25", "M5-15 M6-05 M6-07 M6-08 M6-24",
          "X36 invalid-pool control: preserve a negotiated concession, holding impossible reconstructed carry atomically")
    def run(c):
        f = c.f
        f.chart(capacity=True)
        u = Usage(f)
        f.api.at("2028-01-01")
        g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000, end="2028-03-01")
        f.api.at("2028-02-01")
        event, _ = u.event("work", "50")
        u.finish()
        g = read_grant(f, g)
        response = f.api.action(f"/deals/{identifier(g['deal_id'])}/amendments", dict(key="concession", scope_key=g["scope_key"],
                                 effective_on="2028-02-01", kind="concession", commercial=dict(amount_minor=3000, scope="remaining"),
                                 billing=dict(future_installments=None)), status=(200, 201))
        apply(f, response["data"], "2028-02-01")
        successor = next(x for x in f.api.all("/grants") if g["id"] in x["predecessor_ids"])
        fields(successor, dict(face_minor=5000, basis_minor=1000), "original remaining concession")
        before = (f.api.all("/grants"), f.api.all("/documents"), f.effects(), f.api.all("/amendments"))
        proposed = dict(key="repair-source", reason="Recorded quantity was wrong", posting_date="2028-02-01",
                        change=dict(kind="source", source_id=u.source["id"], event=dict(event, key="revision", revision=2, quantity=quantity)))
        c.checkpoint("recompute_carry_without_renegotiating_concession")
        preview = f.api.preview("/correction-previews", proposed)
        equal((f.api.all("/grants"), f.api.all("/documents"), f.effects(), f.api.all("/amendments")), before, "preview changed accepted state")
        if valid:
            equal(preview["issues"], [], "nonnegative two-dollar pool is valid")
            f.api.create("/corrections", dict(proposed, basis_token=preview["basis_token"]))
            fields(read_grant(f, successor), dict(face_remaining_minor=4000, basis_minor=200), "corrected remaining pool")
            equal(len(f.api.all("/amendments")), 1, "correction created a new agreement")
        else:
            require(preview["issues"], "negative derived pool needs an issue")
            response = f.api.request("POST", "/corrections", dict(proposed, basis_token=preview["basis_token"]), status=200)
            equal(response["operation"]["status"], "held", "negative pool accepted")
            equal((f.api.all("/grants"), f.api.all("/documents"), f.effects(), f.api.all("/amendments")), before, "held correction partly accepted economics")
    return run


remaining_pool_correction("60", True)
remaining_pool_correction("90", False)


def replace_rights(f, g, eligible, product, sold_product, key, date, end, face, price):
    g = read_grant(f, g)
    commercial = dict(carry="all_remaining", price_delta_minor=price, new_face_minor=face,
                      replacement_promise=dict(key=key, product_id=sold_product["id"], ssp="100", attrs={}),
                      replacement_grant=dict(key=key, owner_customer_id=g["owner_customer_id"], currency="USD",
                                             window=dict(starts_on=date, ends_before=end), priority=1,
                                             consumer_ids=[x["id"] for x in eligible], product_ids=[product["id"]]))
    response = f.api.action(f"/deals/{identifier(g['deal_id'])}/amendments", dict(key="replace-"+key, scope_key=g["scope_key"],
                             effective_on=date, kind="modify", commercial=commercial, billing=dict(future_installments=None)), status=(200, 201))
    apply(f, response["data"], date)
    return single([x for x in f.api.all("/grants") if x.get("key") == key], "replacement grant")


def late_first_fact(u, key, quantity, date, posting):
    """M6 expressly permits revision one through corrections after active funding exists."""
    u.complete()
    event = dict(key=key, event_key=key, revision=1, state="active", event_type="request", alias="project-0",
                 occurred_at=date+"T12:00:00Z", quantity=quantity, identity=None, interval=None, dimensions={"billable": "yes"})
    correction(u.f, {}, dict(kind="source", source_id=u.source["id"], event=event), date=posting)
    return event


def meridian(f):
    """Same X32 economics, with the February feed commissioned in February.

    No future feed is required for January. A late first February fact uses the
    published correction endpoint, so blocked ordinary ingestion does not mask
    reconstruction of the subsequent historical revision.
    """
    f.chart(capacity=True)
    root = f.customer("root")
    a, b, child = [f.customer(key, root["id"]) for key in ("a", "b", "c")]
    product, sold = f.product("compute"), f.product("capacity-sale")
    u = Usage(f, customers=[a, b], count=2, owner=root, product=product, group_key="ab", model="volume",
              bands=[dict(up_to="100", unit_price="1"), dict(up_to=None, unit_price="0.8")])
    f.api.at("2028-01-01")
    other = Usage(f, customers=[child], product=product, group_key="c")
    f.api.at("2028-01-01")
    eligible = [u.consumers[0], other.consumers[0]]
    g0 = grant(f, root, eligible, product, 15000, 12000, key="g0", end="2028-03-01", sale_product=sold)
    f.api.at("2028-02-01")
    u.event("a-work", "80", project=0, date="2028-01-10")
    event, _ = u.event("b-work", "40", project=1, date="2028-01-10")
    other.event("c-work", "50", date="2028-01-20")
    for usage in (u, other):
        usage.complete()
    f.bill("2028-02-01", "2028-02-01")
    f.recognition("2028-01-31", "2028-02-01")
    fields(read_grant(f, g0), dict(face_remaining_minor=3600, basis_recognized_minor=9120), "January funded history")
    g1 = replace_rights(f, g0, eligible, product, sold, "g1", "2028-02-01", "2028-03-01", 10000, 9000)
    fields(g1, dict(face_minor=13600, basis_minor=11880), "February successor")
    f.bill("2028-02-01", "2028-02-01")
    later = Usage(f, customers=[child], consumers=other.consumers, product=product, group_key="c-feb",
                  window=dict(starts_on="2028-02-01", ends_before="2028-03-01"))
    late_first_fact(later, "later-work", "150", "2028-02-15", "2028-03-01")
    f.bill("2028-03-01", "2028-03-01")
    f.recognition("2028-02-29", "2028-03-01")
    equal(sum(r["overage_minor"] for r in later.rows()), 1400, "initial later overage")
    fields(read_grant(f, g1), dict(face_remaining_minor=0, basis_recognized_minor=11880), "initial successor consumption")
    return dict(root=root, a=a, b=b, child=child, u=u, later=later, event=event, g0=g0, g1=g1)


def meridian_case(reclassify, settled):
    @case(f"interaction-retained-rights-correction-reclass-{int(reclassify)}-settled-{int(settled)}", 6, "B25",
          "M6-03 M6-05 M6-07 M6-08 M6-09 M6-11 M6-12 M6-13 M6-16 M6-18 M6-20",
          "X32-X35: rebuild derived rights while preserving agreements, actual cash and selectively reclassified revenue")
    def run(c):
        f = c.f
        c.checkpoint("build_complete_retained_rights_history")
        h = meridian(f)
        if settled:
            for buyer, amount in ((h["b"], 3200), (h["child"], 1000)):
                invoice = next(d for d in f.api.all("/documents") if d["customer_id"] == buyer["id"] and d["kind"] == "invoice")
                receipt = f.receipt(buyer, amount, post="2028-03-01")
                f.application(receipt, invoice, amount, post="2028-03-01")
        for month in ("2028-01", "2028-02"):
            f.create("/period-closes", month=month)
        closed = {m: f.report(m) for m in ("2028-01", "2028-02")}
        f.api.at("2028-03-02")
        if reclassify:
            config, addresses = f.chart(effective="2028-03-02", prefix="new", capacity=True)
            ids = [e["id"] for e in f.effects() if e["kind"] == "capacity_consumption" and e["scope_key"] == h["g1"]["scope_key"]]
            require(ids, "successor consumption effects for selective reclassification")
            body = dict(key="move-g1", scope=dict(currency="USD", scope_keys=None, effect_ids=ids, economic_window=None),
                        configuration_id=config["id"], posting_date="2028-03-02")
            preview = f.api.preview("/reclassification-previews", body)
            f.api.create("/reclassifications", dict(body, basis_token=preview["basis_token"]))
        originals = copy.deepcopy(f.api.all("/documents"))
        agreed_fields = ("key", "kind", "scope_key", "effective_on", "commercial", "billing")
        agreements = {a["id"]: agreement_terms(a, agreed_fields)
                      for a in f.api.all("/amendments")}
        ids = {d["id"] for d in originals}
        c.checkpoint("historical_b_revision_changes_a_and_later_c")
        event = dict(h["event"], key="b-ten", revision=2, quantity="10")
        correction(f, {}, dict(kind="source", source_id=h["u"].source["id"], event=event), date="2028-03-02")
        fields(read_grant(f, h["g0"]), dict(basis_recognized_minor=10400, status="superseded"), "revised predecessor")
        # Grant reads include original terms. Corrected funding and current basis,
        # not the spelling of a separate original-face field, prove the new rights.
        fields(read_grant(f, h["g1"]), dict(face_remaining_minor=0, basis_minor=10600, basis_recognized_minor=10600), "reconstructed successor")
        equal(sum(r["overage_minor"] for r in h["later"].rows()), 3000, "untouched later event now has more overage")
        new_docs = [d for d in f.api.all("/documents") if d["id"] not in ids]
        customer_documents(new_docs, [(h["b"]["id"], "credit", 2200),
                                      (h["child"]["id"], "debit", 1600)])
        if settled:
            credit = next(d for d in new_docs if d["kind"] == "credit")
            f.create("/refunds", source=dict(kind="credit", id=credit["id"]), amount_minor=500, posting_date="2028-03-02")
            fields(f.statement(h["b"]), dict(available_backed_minor=1700, cash_refunded_minor=500), "real partial refund")
        if reclassify:
            legs = [leg for e in f.effects() if e["scope_key"] in (h["g0"]["scope_key"], h["g1"]["scope_key"])
                    for leg in e["legs"] if leg["function"] == "service_revenue"]
            distribution(legs, {("book-service_revenue", ()): -10400, ("new-service_revenue", ()): -10600}, "correction respects selectively moved revenue")
        c.checkpoint("next_revision_uses_latest_economics_and_actual_refund")
        ids = {d["id"] for d in f.api.all("/documents")}
        f.api.at("2028-03-03")
        correction(f, {}, dict(kind="source", source_id=h["u"].source["id"], event=dict(event, key="b-twenty", revision=3, quantity="20")), date="2028-03-03")
        revised_docs = [d for d in f.api.all("/documents") if d["id"] not in ids]
        customer_documents(revised_docs, [(h["b"]["id"], "debit", 600),
                                          (h["child"]["id"], "credit", 1600)])
        fields(read_grant(f, h["g1"]), dict(face_remaining_minor=0, basis_minor=11880), "restored derived rights")
        equal(sum(r["overage_minor"] for r in h["later"].rows()), 1400, "restored successor funding")
        if settled:
            fields(f.statement(h["b"]), dict(cash_received_minor=3200, cash_refunded_minor=500), "second correction leaves cash alone")
            debit = next(d for d in revised_docs if d["customer_id"] == h["b"]["id"])
            credit = f.api.get(f"/documents/{identifier(credit['id'])}")
            if debit["open_minor"]:
                f.application(credit, debit, debit["open_minor"], kind="credit", post="2028-03-03")
            fields(f.statement(h["b"]), dict(ar_minor=0, available_backed_minor=1100,
                   available_restricted_minor=0, cash_received_minor=3200, cash_refunded_minor=500),
                   "second revision consumes six of the seventeen remaining credit")
            statement = f.statement(h["child"])
            equal(statement["ar_minor"]-statement["available_backed_minor"]-statement["available_restricted_minor"], 400,
                  "later consumer's debt less available correcting credit")
            equal(statement["cash_received_minor"], 1000, "later consumer's actual cash")
            # Auto-application is to referenced items, not arbitrary other debt.
            # Apply any remaining correction credit explicitly before comparing AR.
            for credit in f.api.all("/documents"):
                if credit["customer_id"] != h["child"]["id"] or credit["kind"] != "credit":
                    continue
                available = credit["available_backed_minor"] + credit["available_restricted_minor"]
                if available:
                    owed = next(d for d in f.api.all("/documents") if d["customer_id"] == h["child"]["id"] and d["open_minor"] >= available)
                    f.application(credit, owed, available, kind="credit", post="2028-03-03")
            equal(f.statement(h["child"])["ar_minor"], 400, "explicitly settled correcting credit")
        if reclassify:
            legs = [leg for e in f.effects() if e["scope_key"] in (h["g0"]["scope_key"], h["g1"]["scope_key"])
                    for leg in e["legs"] if leg["function"] == "service_revenue"]
            distribution(legs, {("book-service_revenue", ()): -9120, ("new-service_revenue", ()): -11880},
                         "restoring amounts does not undo accepted successor reclassification")
        for month, before in closed.items():
            closed_unchanged(before, f.report(month))
        for doc in originals:
            immutable_document(doc, f.api.get(f"/documents/{identifier(doc['id'])}"))
        equal(len(f.api.all("/grants")), 2, "revisions duplicated rights")
        equal(len(f.api.all("/amendments")), 1, "revisions renegotiated agreement")
        equal({a["id"]: agreement_terms(a, agreed_fields) for a in f.api.all("/amendments")}, agreements,
              "corrections changed the accepted commercial agreement")
    return run


meridian_case(False, False)
meridian_case(False, True)
meridian_case(True, False)


@case("interaction-two-rights-replacements-termination-correction", 6, "B25", "M6-05 M6-07 M6-08 M6-09 M6-10 M6-15",
      "X36: an old draw correction propagates through two replacements and retained final termination price")
def deep_rights(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    sold = f.product("capacity-sale")
    f.api.at("2028-01-01")
    g0 = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000, key="g0", end="2028-05-01", sale_product=sold)
    f.api.at("2028-02-01")
    event, _ = u.event("old-work", "25")
    u.finish()
    g1 = replace_rights(f, g0, u.consumers, u.product, sold, "g1", "2028-02-01", "2028-05-01", 2500, 2000)
    f.bill("2028-02-01", "2028-02-01")
    second = Usage(f, customers=u.customers, consumers=u.consumers, product=u.product, group_key="feb",
                   window=dict(starts_on="2028-02-01", ends_before="2028-03-01"))
    late_first_fact(second, "feb-work", "50", "2028-02-15", "2028-03-01")
    f.recognition("2028-02-29", "2028-03-01")
    fields(read_grant(f, g1), dict(face_remaining_minor=5000, basis_recognized_minor=4000), "first successor consumed half")
    g2 = replace_rights(f, g1, u.consumers, u.product, sold, "g2", "2028-03-01", "2028-05-01", 5000, 4000)
    f.bill("2028-03-01", "2028-03-01")
    third = Usage(f, customers=u.customers, consumers=u.consumers, product=u.product, group_key="mar",
                  window=dict(starts_on="2028-03-01", ends_before="2028-04-01"))
    late_first_fact(third, "mar-work", "25", "2028-03-15", "2028-04-01")
    f.recognition("2028-03-31", "2028-04-01")
    c.checkpoint("terminate_latest_rights_without_terminating_predecessors")
    response = f.api.action(f"/deals/{identifier(g2['deal_id'])}/terminations", dict(key="end-g2", scope_key=g2["scope_key"],
                             effective_on="2028-04-01", retained_price_minor=2000, termination_fee=None), status=(200, 201))
    f.api.action(f"/terminations/{identifier(response['data']['id'])}/apply", dict(posting_date="2028-04-01"))
    f.bill("2028-04-01", "2028-04-01")
    ids = {d["id"] for d in f.api.all("/documents")}
    c.checkpoint("old_revision_recomputes_both_carries_and_termination_credit")
    correction(f, {}, dict(kind="source", source_id=u.source["id"], event=dict(event, key="old-revised", revision=2, quantity="50")), date="2028-04-01")
    fields(read_grant(f, g0), dict(basis_recognized_minor=4000), "original corrected earnings")
    fields(read_grant(f, g1), dict(basis_recognized_minor=4000, face_remaining_minor=0, status="superseded"), "first successor reconstructed")
    chain_carries(f.api.all('/position-transfers'), f.api.all('/deals'),
                  [g0['scope_key'], g1['scope_key'], g2['scope_key']],
                  ['2028-02-01', '2028-03-01'], [4000, 2000])
    fields(read_grant(f, g2), dict(basis_recognized_minor=2000, status="terminated"), "last successor retains final agreement")
    new = [d for d in f.api.all("/documents") if d["id"] not in ids]
    document_totals(new, [("debit", 2000)])
    equal(len(f.api.all("/amendments")), 2, "old correction created new commercial agreements")
    equal(len(f.api.all("/terminations")), 1, "old correction repeated termination")


@case("interaction-paid-usage-fixed-commercial-memo", 6, "B26", "M2-21 M6-03 M6-10 M6-11 M6-24",
      "R23: rerating preserves a separately negotiated fixed commercial credit")
def commercial_rerating(c):
    f = c.f
    f.chart()
    u = Usage(f)
    event, _ = u.event("work", "100")
    _, docs = u.finish()
    document_totals(docs, [("invoice", 10000)], "linked usage invoice before commercial memo")
    receipt = f.receipt(u.customers[0], 10000, post="2028-02-01")
    f.application(receipt, docs[0], 10000, post="2028-02-01")
    fixed = f.memo(u.customers[0], docs[0], 2000, post="2028-02-01")
    ids = {d["id"] for d in f.api.all("/documents")}
    c.checkpoint("source_revision_retains_fixed_concession")
    correction(f, {}, dict(kind="source", source_id=u.source["id"], event=dict(event, key="revised", revision=2, quantity="80")), date="2028-02-01")
    document_totals([d for d in f.api.all("/documents") if d["id"] not in ids], [("credit", 2000)])
    fields(f.statement(u.customers[0]), dict(ar_minor=0, available_backed_minor=4000, cash_received_minor=10000), "fixed plus corrective credit")
    equal(sum(earned_minor(r) for r in f.units()), 6000, "80 base less retained 20 concession")
    immutable_document(fixed, f.api.get(f"/documents/{identifier(fixed['id'])}"))
    before = (f.api.all("/documents"), f.effects())
    proposed = dict(key="invalid-smaller-base", reason="Correction would make net negative", posting_date="2028-02-01",
                    change=dict(kind="source", source_id=u.source["id"], event=dict(event, key="third", revision=3, quantity="10")))
    preview = f.api.preview("/correction-previews", proposed)
    require(preview["issues"], "fixed concession exceeds corrected base")
    response = f.api.request("POST", "/corrections", dict(proposed, basis_token=preview["basis_token"]), status=200)
    equal(response["operation"]["status"], "held", "negative consideration must hold")
    equal((f.api.all("/documents"), f.effects()), before, "invalid correction changed posted state")
