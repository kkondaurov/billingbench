"""Independent pricing, funding and payer scopes; consumed versus carried basis."""

from urllib.parse import urlencode

from .checks import document_totals, equal, fields, require
from .client import identifier
from .m2 import Usage
from .m4 import apply
from .suite import case


def grant(f, owner, consumers, product, face, price=0, key="capacity", kind="paid", priority=1,
          start="2028-01-01", end="2028-02-01", sale_product=None):
    body = dict(key=key, owner_customer_id=owner["id"], currency="USD", face_minor=face,
                window=dict(starts_on=start, ends_before=end), priority=priority,
                consumer_ids=[c["id"] for c in consumers], product_ids=[product["id"]], kind=kind, attrs={})
    if kind == "paid":
        sale_product = sale_product or f.product(f.key("capacity-product"))
        body.update(product_id=sale_product["id"], price_minor=price,
                    installments=[dict(key=key + "-purchase", billable_on=start, amount_minor=price)])
    return f.api.create("/grants", body)


def read_grant(f, g, through=None):
    query = "?" + urlencode({"through": through}) if through else ""
    return f.api.get(f"/grants/{identifier(g['id'])}" + query)


@case("paid-face-basis-expiry", 5, "B17", "M5-05 M5-09 M5-10 M5-11 M5-19",
      "Unpaid paid capacity releases consideration, not face; expiry recognizes only its remainder")
def basis_expiry(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000)
    f.api.at("2028-02-01")
    u.event("one", "30", date="2028-01-10")
    u.event("two", "50", date="2028-01-20")
    u.complete()
    c.checkpoint("unpaid_draws_use_allocated_basis")
    f.recognition("2028-01-15", "2028-02-01")
    fields(read_grant(f, g, '2028-01-15'), dict(face_remaining_minor=7000, basis_minor=8000, basis_recognized_minor=2400), "first draw")
    f.recognition("2028-01-31", "2028-02-01")
    fields(read_grant(f, g, '2028-01-31'), dict(face_remaining_minor=2000, basis_recognized_minor=6400), "second draw")
    _, docs = f.bill("2028-02-01", "2028-02-01")
    equal(sum(d["total_minor"] for d in docs), 8000, "only paid purchase is invoiced")
    fields(f.statement(u.customers[0]), dict(ar_minor=8000, cash_received_minor=0), "unpaid purchase")
    c.checkpoint("expiry_and_billing_do_not_double_revenue")
    f.create("/grant-expirations", through="2028-02-01", posting_date="2028-02-01")
    fields(read_grant(f, g), dict(status="expired", basis_recognized_minor=8000, basis_unearned_minor=0), "expired basis")
    effects = f.effects()
    equal(sum(e["amount_minor"] for e in effects if e["kind"] == "capacity_consumption"), 6400, "consumed basis category")
    equal(sum(e["amount_minor"] for e in effects if e["kind"] == "capacity_expiry"), 1600, "expired basis category")
    frozen = f.api.all("/drawdowns")
    f.create("/grant-expirations", through="2028-02-01", posting_date="2028-02-01")
    f.bill("2028-02-01", "2028-02-01")
    equal(f.api.all("/drawdowns"), frozen, "repeated operations duplicated draws")


@case("promotion-priority-overage", 5, "B19", "M5-07 M5-08 M5-09 M5-12", "Zero-basis promotional capacity and paid capacity have distinct revenue")
def promotional(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    paid = grant(f, u.customers[0], u.consumers, u.product, 5000, 4000, key="paid", priority=2)
    promo = grant(f, u.customers[0], u.consumers, u.product, 3000, key="promo", kind="promotional", priority=1)
    f.api.at("2028-02-01")
    u.event("work", "95")
    c.checkpoint("ordered_funding_and_overage")
    _, docs = u.finish()
    equal(sum(d["total_minor"] for d in docs), 5500, "purchase plus unfunded overage")
    fields(read_grant(f, promo), dict(face_remaining_minor=0, basis_minor=0, basis_recognized_minor=0), "promotion")
    fields(read_grant(f, paid), dict(face_remaining_minor=0, basis_minor=4000, basis_recognized_minor=4000), "paid grant")
    equal(sum(r["overage_minor"] for r in u.rows()), 1500, "unfunded remainder")


def minimum_fixture(f, amount="70"):
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    minimum = f.create("/minimum-agreements", owner_customer_id=u.customers[0]["id"], payer_customer_id=u.customers[0]["id"],
                        currency="USD", window=u.window, consumer_ids=[x["id"] for x in u.consumers],
                        product_ids=[u.product["id"]], minimum_minor=10000)
    f.api.at("2028-02-01")
    body, _ = u.event("work", amount)
    u.finish()
    equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "minimum_residual"),
          0, "minimum is not recognized before its exclusive end")
    f.recognition(u.window["ends_before"], u.window["ends_before"])
    return u, minimum, body


@case("minimum-is-residual", 5, "B20", "M5-13 M5-14", "Minimum excludes purchases and is not a spendable wallet")
def minimum(c):
    f = c.f
    u, m, _ = minimum_fixture(f)
    c.checkpoint("minimum_components")
    result = f.api.get(f"/minimum-agreements/{identifier(m['id'])}")
    fields(result, dict(qualifying_minor=7000, residual_minor=3000, billed_minor=3000, earned_minor=3000), "minimum")
    equal(sum(d["total_minor"] for d in f.api.all("/documents")), 10000, "usage plus residual")
    equal(f.api.all("/grants"), [], "minimum created spendable capacity")


def enterprise_history(f, later_quantity="200"):
    """One small, fully specified predecessor/successor history shared by M5/M6 continuations."""
    f.chart(capacity=True)
    parent = f.customer("enterprise")
    a, b, c = [f.customer(key, parent["id"]) for key in ("a", "b", "c")]
    product = f.product("compute")
    pooled = Usage(f, model="volume", bands=[dict(up_to="100", unit_price="1"), dict(up_to=None, unit_price="0.8")],
                   count=2, customers=[a, b], product=product, owner=parent, group_key="ab")
    f.api.at("2028-01-01")
    standalone = Usage(f, customers=[c], product=product, group_key="c")
    f.api.at("2028-01-01")
    later = Usage(f, customers=[c], product=product, group_key="c-later",
                  window=dict(starts_on="2028-02-01", ends_before="2028-03-01"))
    f.api.at("2028-01-01")
    eligible = [pooled.consumers[0], *standalone.consumers, *later.consumers]
    capacity_product = f.product("prepaid-capacity")
    g0 = grant(f, parent, eligible, product, 15000, 12000, key="g0", end="2028-03-01",
               sale_product=capacity_product)
    f.api.at("2028-02-01")
    pooled.event("a-work", "80", project=0, date="2028-01-10")
    body, _ = pooled.event("b-work", "40", project=1, date="2028-01-10")
    standalone.event("c-work", "50", date="2028-01-20")
    # Record February's first fact before purchase coverage protects its inputs.
    # Its period remains incomplete until March; January can still finish.
    later.event("later-work", later_quantity, date="2028-02-01")
    for u in (pooled, standalone):
        u.complete()
    f.bill("2028-02-01", "2028-02-01")
    f.recognition("2028-01-31", "2028-02-01")
    fields(read_grant(f, g0), dict(face_remaining_minor=3600, basis_earned_minor=9120), "predecessor before replacement")
    g0 = read_grant(f, g0)
    commercial = dict(carry="all_remaining", price_delta_minor=9000, new_face_minor=10000,
                       replacement_promise=dict(key="replacement", product_id=capacity_product["id"], ssp="90", attrs={}),
                       replacement_grant=dict(key="g1", owner_customer_id=parent["id"], currency="USD",
                                              window=dict(starts_on="2028-02-01", ends_before="2028-03-01"), priority=1,
                                              consumer_ids=[x["id"] for x in eligible], product_ids=[product["id"]]))
    response = f.api.action(f"/deals/{identifier(g0['deal_id'])}/amendments",
                             dict(key="replace", scope_key=g0["scope_key"], effective_on="2028-02-01", kind="modify",
                                  commercial=commercial, billing=dict(future_installments=None)), status=(200, 201))
    apply(f, response["data"], "2028-02-01")
    g1s = [g for g in f.api.all("/grants") if g["key"] == "g1"]
    equal(len(g1s), 1, "one successor grant")
    g1 = g1s[0]
    fields(g1, dict(face_minor=13600, basis_minor=11880), "derived successor face and consideration")
    f.bill("2028-02-01", "2028-02-01")
    f.api.at("2028-03-01")
    later.complete()
    f.bill("2028-03-01", "2028-03-01")
    f.recognition("2028-02-29", "2028-03-01")
    return dict(parent=parent, a=a, b=b, c=c, pooled=pooled, standalone=standalone,
                later=later, g0=g0, g1=g1, original_event=body, amendment=response["data"])


@case("shared-pricing-rights-replacement", 5, "B18", "M5-01 M5-02 M5-05 M5-16 M5-17 M5-18 M5-20",
      "Pricing A/B and funding A/C are independent, with one recomputed successor basis")
def enterprise(c):
    f = c.f
    h = enterprise_history(f)
    c.checkpoint("shared_scopes_and_successor_consumption")
    by_customer = {customer["id"]: sum(r["net_minor"] for r in h["pooled"].rows() if r["customer_id"] == customer["id"])
                   for customer in (h["a"], h["b"])}
    equal(by_customer, {h["a"]["id"]: 6400, h["b"]["id"]: 3200}, "pooled volume attribution")
    fields(read_grant(f, h["g0"]), dict(status="superseded", basis_recognized_minor=9120), "superseded predecessor")
    fields(read_grant(f, h["g1"]), dict(face_remaining_minor=0, basis_recognized_minor=11880), "successor earnings")
    equal(sum(r["overage_minor"] for r in h["later"].rows()), 6400, "later overage")
    equal(len(f.api.all("/grants")), 2, "replacement duplicated purchase/rights")
    transfers = f.api.all("/position-transfers")
    equal(sum(t["billed_transfer_minor"] for t in transfers), 2880, "predecessor deferred basis transfer")


@case("bundled-paid-capacity", 5, "B17", "M5-06 M5-10 M5-12", "Bundled capacity earns its SSP allocation, not displayed purchase price or face")
def bundled(c):
    from .m4 import deal, promise, installment
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    service, capacity = f.product("support"), f.product("capacity")
    terms = dict(key="bundled-capacity", owner_customer_id=u.customers[0]["id"], currency="USD", face_minor=10000,
                 window=u.window, priority=1, consumer_ids=[x["id"] for x in u.consumers], product_ids=[u.product["id"]])
    promises = [promise("support", service, ssp="100", end="2028-02-01"),
                dict(key="capacity", product_id=capacity["id"], kind="paid_capacity", ssp="100", window=u.window,
                     activation_on=None, approved_total=None, attrs={}, grant=terms)]
    d = deal(f, u.customers[0], 10000, promises, [installment("all-support-display", "2028-01-01", 10000, "support")])
    f.api.at("2028-02-01")
    u.event("work", "80")
    c.checkpoint("allocated_basis_not_display_or_face")
    _, docs = u.finish()
    equal(sum(d["total_minor"] for d in docs), 10000, "bundle and funded usage invoices")
    matches = [g for g in f.api.all("/grants") if g.get("key") == "bundled-capacity"]
    equal(len(matches), 1, "accepted bundled grant with supplied key bundled-capacity")
    g = matches[0]
    g = read_grant(f, g, through="2028-01-31")
    fields(g, dict(basis_minor=5000, basis_recognized_minor=4000, face_remaining_minor=2000), "bundled basis release")
    equal(sum(r["overage_minor"] for r in u.rows()), 0, "fully funded usage")


@case("payer-policy-old-debt", 5, "B18", "M5-03 M5-04 M5-21", "Parent payment policy changes future debtor assignment, not existing child debt")
def payer(c):
    from .m1 import immutable_document
    f = c.f
    f.chart(capacity=True)
    parent = f.customer("parent")
    child = f.customer("child", parent["id"])
    old, _, _ = f.subscription(child, price="20")
    _, original = f.bill("2028-01-01", "2028-01-01")
    product = f.product("new-service")
    u = Usage(f, customers=[child], product=product, window=dict(starts_on="2028-02-01", ends_before="2028-03-01"))
    f.api.at("2028-01-01")
    f.create("/payer-policies", consumer_customer_id=child["id"], product_ids=[product["id"]],
             window=u.window, payer_customer_id=parent["id"])
    f.api.at("2028-03-01")
    u.event("work", "30", date="2028-02-15")
    u.complete()
    c.checkpoint("new_parent_debt_old_child_debt")
    _, docs = f.bill("2028-03-01", "2028-03-01")
    document_totals(docs, [("invoice", 3000)])
    equal(docs[0]["customer_id"], parent["id"], "configured invoice payer")
    equal(f.statement(child)["ar_minor"], 2000, "old child debt retained")
    equal(f.statement(parent)["ar_minor"], 3000, "new parent debt")
    immutable_document(original[0], f.api.get(f"/documents/{identifier(original[0]['id'])}"))
    receipt = f.receipt(parent, 3000, post="2028-03-01")
    body = dict(key="wrong-debtor", source=dict(kind="receipt", id=receipt["id"]),
                allocations=[dict(document_id=original[0]["id"], item_key=original[0]["items"][0]["key"], amount_minor=2000)],
                posting_date="2028-03-01")
    f.api.error("POST", "/applications", body, 422, "invalid_domain")
    f.application(receipt, docs[0], 3000, post="2028-03-01")
    equal(f.statement(parent)["ar_minor"], 0, "permitted parent settlement")


@case("paid-capacity-remaining-concession", 5, "B22", "M5-15 M5-18", "A price-only concession changes remaining basis without increasing face")
def capacity_concession(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000, end="2028-03-01")
    f.api.at("2028-02-01")
    u.event("work", "50")
    u.finish()
    g = read_grant(f, g)
    c.checkpoint("derive_remaining_face_and_reduced_basis")
    response = f.api.action(f"/deals/{identifier(g['deal_id'])}/amendments", dict(key="reduce-remaining-price",
                             scope_key=g["scope_key"], effective_on="2028-02-01", kind="concession",
                             commercial=dict(amount_minor=3000, scope="remaining"), billing=dict(future_installments=None)), status=(200, 201))
    apply(f, response["data"], "2028-02-01")
    successors = [x for x in f.api.all("/grants") if g["id"] in x["predecessor_ids"]]
    equal(len(successors), 1, "one concession successor")
    fields(successors[0], dict(face_minor=5000, face_remaining_minor=5000, basis_minor=1000), "remaining rights and consideration")
    fields(read_grant(f, g), dict(basis_recognized_minor=4000, status="superseded"), "old earned basis retained")
