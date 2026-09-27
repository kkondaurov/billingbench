"""Negotiated consideration, performance, retained billing and scope changes."""

from fractions import Fraction

from .checks import earned_minor, document_totals, equal, fields, integer_fields, require
from .client import identifier
from .m1 import immutable_document, single
from .oracles import allocate, earned
from .suite import case
from .scopes import lineage


def promise(key, product, kind="stand_ready", ssp="1000", start="2028-01-01", end="2028-04-02",
            total=None):
    return dict(key=key, product_id=product["id"], kind=kind, ssp=ssp,
                window=None if kind == "acceptance" else dict(starts_on=start, ends_before=end),
                activation_on=start if kind == "stand_ready" else None,
                approved_total=total, attrs={})


def installment(key, when, amount, promise_key, group="group"):
    return dict(key=key, billable_on=when, items=[dict(key=key + "-item", group_key=group,
                                                    promise_key=promise_key, amount_minor=amount)])


def deal(f, buyer, price, promises, installments):
    result = f.create("/deals", customer_id=buyer["id"], currency="USD", groups=[dict(key="group", price_minor=price, promises=promises)],
                      installments=installments, attrs={})
    f.api.action(f"/deals/{identifier(result['id'])}/accept")
    return f.api.get(f"/deals/{identifier(result['id'])}")


def units(f, d, through=None):
    return [u for u in f.units(through=through) if u.get("deal_id") == d["id"]]


def published_scopes(d):
    scopes = d.get("scope_keys", {})
    return {value for kind in ("groups", "promises") for value in scopes.get(kind, {}).values()}


def scope_deal(f, d, scope):
    if scope in published_scopes(d):
        return d
    owners = [row for row in f.api.all("/deals") if scope in published_scopes(row)]
    return single(owners, "deal publishing agreement scope")


def lineage_units(f, d, through=None):
    rows = f.units(through=through)
    transfers = f.api.all('/position-transfers')
    return lineage(rows, transfers, d, f.api.all('/deals'))


def performance(f, d, key, kind, date, completed=None):
    return f.api.create(f"/deals/{identifier(d['id'])}/performance",
                         dict(key=f.key("evidence"), promise_key=key, kind=kind, effective_on=date, completed=completed))


def amend(f, d, date, commercial, future=None, kind="modify", scope=None):
    if scope is None:
        require(isinstance(d.get("scope_keys"), dict) and
                isinstance(d["scope_keys"].get("groups"), dict) and d["scope_keys"]["groups"].get("group"),
                "accepted deal missing required group scope_keys")
    scope = scope or d["scope_keys"]["groups"]["group"]
    owner = scope_deal(f, d, scope)
    response = f.api.action(f"/deals/{identifier(owner['id'])}/amendments",
                            dict(key=f.key("agreement"), scope_key=scope,
                                 effective_on=date, kind=kind, commercial=commercial,
                                 billing=dict(future_installments=future)), status=(200, 201))
    return f.api.resource(response, "amendment")


def apply(f, a, date, key=None):
    f.api.action(f"/amendments/{identifier(a['id'])}/apply", dict(posting_date=date), key=key)
    return f.api.get(f"/amendments/{identifier(a['id'])}")


def amounts(rows, key, field):
    matching = [u for u in rows if u["promise_key"] == key]
    for row in matching:
        integer_fields(row, (field,), "revenue unit")
    return sum(u[field] for u in matching)


@case("allocated-zero-display-delivery", 4, "B13", "M4-01 M4-02 M4-03 M4-04 M4-05",
      "Invoice display prices and cash do not determine promise allocation or earnings")
def allocated_delivery(c):
    f = c.f
    f.chart()
    buyer, service, implementation = f.customer(), f.product("service"), f.product("implementation")
    d = deal(f, buyer, 115000, [promise("service", service, ssp="920"), promise("implementation", implementation, "acceptance", "230")],
             [installment("deposit", "2028-01-01", 50000, "service"), installment("later", "2028-03-01", 65000, "service")])
    f.api.at("2028-01-31")
    performance(f, d, "implementation", "acceptance", "2028-01-15")
    _, docs = f.bill()
    document_totals(docs, [("invoice", 50000)])
    c.checkpoint("allocation_independent_of_display")
    equal({a["promise_key"]: a["allocation_minor"] for a in d["allocations"]}, {"service": 92000, "implementation": 23000}, "SSP allocation")
    f.recognition("2028-01-31")
    rows = units(f, d)
    equal(amounts(rows, "service", "earned_minor"), 31000, "stand-ready service")
    equal(amounts(rows, "implementation", "earned_minor"), 23000, "zero-display deliverable")
    equal(amounts(rows, "service", "billed_minor"), 40000, "allocated billed service")
    equal(amounts(rows, "implementation", "billed_minor"), 10000, "allocated billed delivery")
    before = [(u["scope_key"], earned_minor(u)) for u in rows]
    f.receipt(buyer, 50000)
    equal([(u["scope_key"], earned_minor(u)) for u in units(f, d)], before, "receipt recognized revenue")


@case("concession-termination-settlement", 4, "B24", "M4-15 M4-17 M4-18 M4-19 M4-21 M4-22 M4-23",
      "A lower final price can require a new invoice after earlier credit and future billing cancellation")
def concession_termination(c):
    f = c.f
    f.chart()
    buyer, service, implementation = f.customer(), f.product("service"), f.product("implementation")
    d = deal(f, buyer, 115000, [promise("service", service, ssp="920"), promise("implementation", implementation, "acceptance", "230")],
             [installment("deposit", "2028-01-01", 50000, "service"), installment("later", "2028-03-01", 65000, "service")])
    f.api.at("2028-01-31")
    performance(f, d, "implementation", "acceptance", "2028-01-15")
    _, docs = f.bill()
    invoice = single(docs, "deposit")
    receipt = f.receipt(buyer, 50000)
    f.application(receipt, invoice, 50000)
    f.recognition("2028-01-31")
    c.checkpoint("full_sale_concession")
    f.api.at("2028-02-01")
    a = amend(f, d, "2028-02-01", dict(amount_minor=23000, scope="full_sale"), kind="concession")
    apply(f, a, "2028-02-01")
    _, credits = f.bill("2028-02-01", "2028-02-01")
    document_totals(credits, [("credit", 23000)])
    equal(sum(earned_minor(u) for u in units(f, d, "2028-01-31")), 43200, "concession earned target")
    equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "recognition"),
          43200, "concession posted recognition")
    equal(f.statement(buyer)["available_backed_minor"], 23000, "paid concession credit")
    c.checkpoint("termination_derives_positive_invoice")
    response = f.api.action(f"/deals/{identifier(d['id'])}/terminations",
                             dict(key="terminate", scope_key=d["scope_keys"]["groups"]["group"], effective_on="2028-02-01",
                                  retained_price_minor=40000, termination_fee=None), status=(200, 201))
    t = response["data"]
    f.api.action(f"/terminations/{identifier(t['id'])}/apply", dict(posting_date="2028-02-01"))
    _, final = f.bill("2028-02-01", "2028-02-01")
    document_totals(final, [("invoice", 13000)])
    rows = units(f, d)
    expected = allocate(40000, {"service": 310, "implementation": 230})
    for key, amount in expected.items():
        equal(amounts(rows, key, "earned_minor"), amount, "performed SSP allocation " + key)
    allocations = [dict(document_id=doc["id"], item_key=item["key"], amount_minor=item["amount_minor"])
                   for doc in final for item in doc["items"] if item["amount_minor"]]
    f.create("/applications", source=dict(kind="credit", id=credits[0]["id"]), allocations=allocations, posting_date="2028-02-01")
    fields(f.statement(buyer), dict(ar_minor=0, available_backed_minor=10000, cash_received_minor=50000), "settled termination")
    f.create("/refunds", source=dict(kind="credit", id=credits[0]["id"]), amount_minor=10000, posting_date="2028-02-01")
    equal(sum(earned_minor(u) for u in units(f, d)), 40000, "refund must not reduce final consideration")
    old_docs = f.api.all("/documents")
    f.api.at("2028-03-01")
    f.bill("2028-03-01", "2028-03-01")
    equal(f.api.all("/documents"), old_docs, "terminated future installment was billed")
    immutable_document(invoice, f.api.get(f"/documents/{identifier(invoice['id'])}"))


def prospective_case(billed):
    @case(f"prospective-position-{billed}", 4, "B16", "M4-09 M4-12 M4-13", "Carry is unearned consideration, while billed transfer is bounded by actual position")
    def run(c):
        f = c.f
        f.chart(separate=True)
        buyer, product = f.customer(), f.product()
        old = promise("old", product, ssp="1000", start="2028-01-01", end="2028-01-11")
        installments = [installment("first", "2028-01-01", billed, "old")]
        if billed < 100000:
            installments.append(installment("unissued", "2028-01-10", 100000 - billed, "old"))
        d = deal(f, buyer, 100000, [old], installments)
        f.api.at("2028-01-06")
        f.bill("2028-01-06", "2028-01-06")
        f.recognition("2028-01-06")
        equal(sum(earned_minor(u) for u in units(f, d)), 60000, "pre-replacement earned")
        c.checkpoint("apply_prospective_replacement")
        f.api.at("2028-01-07")
        promises = [promise("next-a", product, ssp="500", start="2028-01-07", end="2028-02-01"),
                    promise("next-b", product, ssp="200", start="2028-01-07", end="2028-02-01")]
        commercial = dict(price_delta_minor=30000, new_services_only=False, new_services_distinct=True,
                          remaining_distinct=True, changes_ongoing_progress=False, successor_promises=promises, revised_group=None)
        a = amend(f, d, "2028-01-07", commercial)
        apply(f, a, "2028-01-07", key="apply-agreement")
        transfers = f.api.all("/position-transfers")
        if transfers:
            equal(sum(t["consideration_carry_minor"] for t in transfers), 40000, "carried unearned consideration")
        equal(sum(t["billed_transfer_minor"] for t in transfers), max(billed - 60000, 0), "billed transfer")
        # Zero billed position need not create an accounting-transfer record.
        # These input promise keys are unique in this isolated fixture.
        rows = [u for u in f.units() if u.get('promise_key') in ('old', 'next-a', 'next-b')]
        for key, amount in (("next-a", 50000), ("next-b", 20000)):
            equal(amounts(rows, key, "allocation_minor"), amount, "successor allocation")
            matched = [u for u in rows if u['promise_key'] == key]
            require(matched and all(u['customer_id'] == buyer['id'] and u['product_id'] == product['id']
                                    for u in matched), 'successor promise retains customer and product')
        equal(sum(u['billed_minor'] for u in rows if u['promise_key'] in ('next-a', 'next-b')),
              max(billed - 60000, 0), 'successor assigned billing before new sale is billed')
        equal(amounts(rows, "old", "earned_minor"), 60000, "prospective change rewrote old earnings")
        before = f.api.all("/documents")
        apply(f, a, "2028-01-07", key="apply-agreement")
        equal(f.api.all("/documents"), before, "agreement replay created a document")
        equal(len(f.api.all("/position-transfers")), len(transfers), "agreement replay transferred twice")
        effects = f.effects()
        repeated = f.api.action(f"/amendments/{identifier(a['id'])}/apply", dict(posting_date="2028-01-07"),
                                complete=False, status=(200, 409))
        if "error" in repeated:
            equal(repeated["error"]["code"], "already_final", "applied agreement rejection")
        else:
            f.api.completed(repeated, "already applied agreement")
        equal(f.api.all("/documents"), before, "fresh-key duplicate created a document")
        equal(f.api.all("/position-transfers"), transfers, "fresh-key duplicate transferred again")
        equal(f.effects(), effects, "fresh-key duplicate posted effects")
    return run


for billed in (50000, 60000, 100000):
    prospective_case(billed)


@case("progress-cumulative-catchup", 4, "B23", "M4-06 M4-10 M4-11", "Increasing total price can decrease earned revenue after a progress estimate change")
def progress(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    promises = [promise("build", product, "progress", "200", total="100"),
                promise("support", product, "progress", "100", total="100")]
    d = deal(f, buyer, 100000, promises, [installment("all", "2028-01-01", 100000, "build")])
    f.api.at("2028-01-31")
    for key in ("build", "support"):
        performance(f, d, key, "progress", "2028-01-31", "50")
    f.bill()
    f.recognition("2028-01-31")
    allocation = allocate(100000, {"build": 200, "support": 100})
    prior_earned = sum(earned(amount, 50, 100) for amount in allocation.values())
    equal(sum(earned_minor(u) for u in units(f, d)), prior_earned, "prior progress revenue")
    f.api.at("2028-02-01")
    f.create("/period-closes", month="2028-01")
    closed = f.report("2028-01")
    c.checkpoint("remeasure_closed_progress")
    revised = [dict(promises[0], approved_total="200"), promises[1]]
    commercial = dict(price_delta_minor=20000, new_services_only=False, new_services_distinct=False,
                      remaining_distinct=False, changes_ongoing_progress=True, successor_promises=[],
                      revised_group=dict(key="group", price_minor=120000, promises=revised))
    a = amend(f, d, "2028-02-01", commercial)
    apply(f, a, "2028-02-01")
    equal(sum(earned_minor(u) for u in units(f, d)), 40000, "negative catch-up despite higher price")
    equal(f.report("2028-01"), closed, "cumulative adjustment rewrote closed report")


@case("customer-deal-redaction", 4, "B13", "C12 M4-01", "Customer reads retain commercial facts without exposing internal allocations")
def redaction(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 70000, [promise("service", product)], [installment("all", "2028-01-01", 70000, "service")])
    c.checkpoint("commercial_view_without_internal_finance")
    view = f.api.actor("customer", buyer["id"]).get(f"/deals/{identifier(d['id'])}")
    require(isinstance(view.get("groups"), list) and len(view["groups"]) == 1,
            "customer deal missing commercial groups")
    equal(view["groups"][0]["price_minor"], 70000, "customer price")
    require("installments" in view, "customer deal missing billing schedule")
    equal(view["installments"], d["installments"], "customer billing schedule")
    def inspect(node):
        if isinstance(node, dict):
            for key, value in node.items():
                require(key not in {"ssp", "allocation_minor", "allocations", "scope_keys", "position_minor", "context"},
                        f"internal field leaked: {key}")
                inspect(value)
        elif isinstance(node, list):
            for value in node:
                inspect(value)
    inspect(view)


@case("billed-ssp-cumulative-cents", 4, "B15", "C10 M4-03 M4-04 M4-12", "Allocate cumulative billed position, not each invoice's rounded split independently")
def cumulative_billing(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 2, [promise("a", product, "acceptance", "1"), promise("b", product, "acceptance", "1")],
             [installment("first", "2028-01-01", 1, "b"), installment("second", "2028-01-02", 1, "b")])
    f.bill("2028-01-01", "2028-01-01")
    equal({u["promise_key"]: u["billed_minor"] for u in units(f, d)}, {"a": 1, "b": 0}, "first cumulative cent")
    c.checkpoint("second_cent_changes_other_promise_position")
    f.api.at("2028-01-02")
    f.bill("2028-01-02", "2028-01-02")
    equal({u["promise_key"]: u["billed_minor"] for u in units(f, d)}, {"a": 1, "b": 1}, "second cumulative cent")


@case("separate-addition", 4, "B21", "M4-08 M4-22", "An SSP-priced distinct addition does not reallocate the old sale")
def separate(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 100000, [promise("original", product, ssp="1000", end="2028-01-11")],
             [installment("all", "2028-01-01", 100000, "original")])
    f.api.at("2028-01-06")
    f.bill("2028-01-06", "2028-01-06")
    f.recognition("2028-01-06")
    before = {u["scope_key"]: (u["allocation_minor"], u["billed_minor"], earned_minor(u))
              for u in units(f, d, "2028-01-06")}
    f.api.at("2028-01-07")
    new = promise("addition", product, "acceptance", "300")
    commercial = dict(price_delta_minor=30000, new_services_only=True, new_services_distinct=True,
                      remaining_distinct=True, changes_ongoing_progress=False, successor_promises=[new], revised_group=None)
    c.checkpoint("separate_new_sale_scope")
    a = amend(f, d, "2028-01-07", commercial)
    apply(f, a, "2028-01-07")
    for u in units(f, d, "2028-01-06"):
        if u["scope_key"] in before:
            equal((u["allocation_minor"], u["billed_minor"], earned_minor(u)), before[u["scope_key"]], "separate addition changed predecessor")
    equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "recognition"),
          60000, "separate addition changed posted predecessor revenue")
    equal(f.api.all("/position-transfers"), [], "separate sale transferred old position")
    _, docs = f.bill("2028-01-07", "2028-01-07")
    document_totals(docs, [("invoice", 30000)])


@case("remaining-concession", 4, "B22", "M4-16", "A remaining-only reduction preserves correctly earned consideration")
def remaining_concession(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 100000, [promise("original", product, ssp="1000", end="2028-01-11")],
             [installment("all", "2028-01-01", 100000, "original")])
    f.api.at("2028-01-06")
    f.bill("2028-01-06", "2028-01-06")
    f.recognition("2028-01-06")
    f.api.at("2028-01-07")
    c.checkpoint("remaining_pool_only")
    commercial = dict(amount_minor=10000, scope="remaining", successor_promises=[promise("rest", product, ssp="400", start="2028-01-07", end="2028-01-11")])
    a = amend(f, d, "2028-01-07", commercial, kind="concession")
    apply(f, a, "2028-01-07")
    rows = units(f, d)
    equal(amounts(rows, "original", "earned_minor"), 60000, "past earned amount after remaining concession")
    equal(amounts(rows, "rest", "allocation_minor"), 30000, "remaining pool reduced once")
    _, docs = f.bill("2028-01-07", "2028-01-07")
    document_totals(docs, [("credit", 10000)])


@case("progress-close-recovery", 4, "B14", "M4-06 M4-07", "A missing progress confirmation is not zero progress and must be recoverable")
def close_recovery(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 10000, [promise("build", product, "progress", "100", total="100")],
             [installment("all", "2028-01-01", 10000, "build")])
    f.api.at("2028-02-01")
    f.bill("2028-02-01", "2028-02-01")
    c.checkpoint("missing_confirmation_holds_close")
    response = f.api.request("POST", "/period-closes", dict(key="close", month="2028-01"), status=200)
    equal(response["operation"]["status"], "held", "missing progress was silently zero")
    performance(f, d, "build", "progress", "2028-01-31", "0")
    f.recognition("2028-01-31", "2028-02-01")
    c.checkpoint("confirmed_zero_can_close")
    response = f.api.request("POST", "/period-closes", dict(key="close", month="2028-01"), status=(200, 201))
    f.api.completed(response, "recovered close")
    equal(sum(earned_minor(u) for u in units(f, d)), 0, "confirmed zero progress")


@case("successor-rebill-terminate", 4, "B16", "M4-14 M4-20 M4-24", "Old billing attribution survives replacement, reversal/rebill, and successor termination")
def successor_lifecycle(c, segmented=True):
    f = c.f
    functions = ("cash", "receivable", "customer_funds", "service_revenue", "contract_position")
    rules = [dict(key=fn, function=fn, priority=1, when={"all": []}, distribution=[dict(key="whole", weight="100",
                   account={"constant": "book-" + fn}, segments={"component": {"field": "obligation.key"}} if fn == "service_revenue" else {})])
             for fn in functions]
    if segmented:
        f.chart(rules=rules, segments=[dict(key="component", values=[dict(key=k, parent_key=None) for k in ("original", "next")])])
    else:
        f.chart()
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 100000, [promise("original", product, ssp="1000", end="2028-01-11")],
             [installment("all", "2028-01-01", 100000, "original")])
    f.api.at("2028-01-06")
    _, old_docs = f.bill("2028-01-06", "2028-01-06")
    f.recognition("2028-01-06")
    f.api.at("2028-01-07")
    commercial = dict(price_delta_minor=30000, new_services_only=False, new_services_distinct=True,
                      remaining_distinct=True, changes_ongoing_progress=False,
                      successor_promises=[promise("next", product, ssp="700", start="2028-01-07", end="2028-02-01")], revised_group=None)
    apply(f, amend(f, d, "2028-01-07", commercial), "2028-01-07")
    _, extra = f.bill("2028-01-07", "2028-01-07")
    document_totals(extra, [("invoice", 30000)])
    transfers = f.api.all("/position-transfers")
    equal(sum(t["billed_transfer_minor"] for t in transfers), 40000, "initial assigned position")
    c.checkpoint("successor_invoice_reversal_and_rebill")
    f.api.action(f"/billing-results/{identifier(extra[0]['result_id'])}/reverse", dict(key="release-next", posting_date="2028-01-07"))
    rows = lineage_units(f, d)
    equal(amounts(rows, "next", "billed_minor"), 40000, "incoming old coverage retained after new invoice reversal")
    _, replaced = f.bill("2028-01-07", "2028-01-07")
    document_totals(replaced, [("invoice", 30000)])
    equal(f.api.all("/position-transfers"), transfers, "rebill repeated commercial transfer")
    f.api.at("2028-01-16")
    f.recognition("2028-01-16")
    rows = lineage_units(f, d)
    equal(amounts(rows, "next", "earned_minor"), 28000, "successor actual service")
    c.checkpoint("successor_termination_reaches_original_sources")
    f.api.at("2028-01-17")
    successor_scope = transfers[0]["successor_scope_key"]
    owner = scope_deal(f, d, successor_scope)
    response = f.api.action(f"/deals/{identifier(owner['id'])}/terminations", dict(key="terminate-successor", scope_key=successor_scope,
                             effective_on="2028-01-17", retained_price_minor=20000, termination_fee=None), status=(200, 201))
    f.api.action(f"/terminations/{identifier(response['data']['id'])}/apply", dict(posting_date="2028-01-17"))
    _, credits = f.bill("2028-01-17", "2028-01-17")
    equal(sum(d["total_minor"] for d in credits if d["kind"] == "credit"), 50000, "successor credit includes transferred coverage")
    by_source = {}
    for doc in credits:
        equal(doc["kind"], "credit", "termination document kind")
        for item in doc["items"]:
            by_source[item["origin_document_id"]] = by_source.get(item["origin_document_id"], 0) + item["amount_minor"]
    equal(by_source, {replaced[0]["id"]: 30000, old_docs[0]["id"]: 20000}, "latest-issued source allocation")
    rows = lineage_units(f, d)
    equal(amounts(rows, "original", "earned_minor"), 60000, "old performance survives successor termination")
    equal(amounts(rows, "next", "earned_minor"), 20000, "terminated successor final consideration")
    from .checks import distribution
    revenue_legs = [l for e in f.effects() for l in e["legs"] if l["function"] == "service_revenue"]
    expected = {("book-service_revenue", (("component", "original"),)): -60000,
                ("book-service_revenue", (("component", "next"),)): -20000} if segmented else {
                    ("book-service_revenue", ()): -80000}
    distribution(revenue_legs, expected, "successor lifecycle revenue distribution")


@case("successor-rebill-terminate-default-chart", 4, "B16", "M4-14 M4-20 M4-24",
      "Exercise retained billing sources independently of new account-context field validation")
def successor_default_chart(c):
    successor_lifecycle(c, segmented=False)
