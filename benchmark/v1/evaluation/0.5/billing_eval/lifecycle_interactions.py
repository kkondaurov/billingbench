"""Old document operations on later sales shapes and retained economic histories."""

import copy

from .checks import earned_minor, document_totals, equal, fields, require, closed_unchanged
from .client import identifier
from .m1 import immutable_document
from .m4 import deal, promise, installment, performance, amend, apply, units, amounts, lineage_units, scope_deal
from .m6 import correction
from .suite import case


@case("interaction-two-successors-original-rebill-termination", 4, "B16", "M4-14 M4-20 M4-22 M4-24",
      "X23: credits trace through two successors to actual original and later invoice sources")
def two_successors(c):
    f = c.f
    f.chart(separate=True)
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 100000, [promise("old", product, end="2028-01-11")], [installment("old-bill", "2028-01-01", 100000, "old")])
    f.api.at("2028-01-06")
    _, original = f.bill("2028-01-06", "2028-01-06")
    f.recognition("2028-01-06")
    f.api.at("2028-01-07")
    scope = d["scope_keys"]["groups"]["group"]
    # This single-promise group can expose its transfer at group or promise scope.
    predecessors = {scope, d["scope_keys"]["promises"]["old"]}
    c.checkpoint("two_replacements_preserve_one_chain")
    for key, delta in (("s1", 30000), ("s2", 0)):
        commercial = dict(price_delta_minor=delta, new_services_only=False, new_services_distinct=True,
                          remaining_distinct=True, changes_ongoing_progress=False,
                          successor_promises=[promise(key, product, ssp="700", start="2028-01-07", end="2028-02-01")], revised_group=None)
        apply(f, amend(f, d, "2028-01-07", commercial, scope=scope), "2028-01-07")
        transfers = [t for t in f.api.all("/position-transfers") if t["predecessor_scope_key"] in predecessors]
        equal(len(transfers), 1, "position transfer for the selected predecessor")
        transfer = transfers[0]
        scope = transfer["successor_scope_key"]
        predecessors = {scope}
        _, extra = f.bill("2028-01-07", "2028-01-07")
        if key == "s1":
            document_totals(extra, [("invoice", 30000)])
            new_invoice = extra[0]
        else:
            document_totals(extra, [], "zero new consideration fabricated billing")
    equal(amounts(lineage_units(f, d, "2028-01-07"), "s2", "allocation_minor"), 70000, "second carry")
    c.checkpoint("reverse_original_document_through_two_transfers")
    f.api.action(f"/billing-results/{identifier(original[0]['result_id'])}/reverse", dict(key="reverse-old", posting_date="2028-01-07"))
    equal(amounts(lineage_units(f, d, "2028-01-07"), "s2", "billed_minor"), 30000, "incoming old coverage removed")
    _, rebill = f.bill("2028-01-07", "2028-01-07")
    document_totals(rebill, [("invoice", 100000)])
    equal(amounts(lineage_units(f, d, "2028-01-07"), "s2", "billed_minor"), 70000, "incoming old coverage restored")
    f.api.at("2028-01-16")
    f.recognition("2028-01-16")
    f.api.at("2028-01-17")
    c.checkpoint("terminate_last_scope_reaches_retained_source_documents")
    owner = scope_deal(f, d, scope)
    response = f.api.action(f"/deals/{identifier(owner['id'])}/terminations", dict(key="terminate", scope_key=scope,
                             effective_on="2028-01-17", retained_price_minor=20000, termination_fee=None), status=(200, 201))
    f.api.action(f"/terminations/{identifier(response['data']['id'])}/apply", dict(posting_date="2028-01-17"))
    _, credits = f.bill("2028-01-17", "2028-01-17")
    equal(sum(d["total_minor"] for d in credits if d["kind"] == "credit"), 50000, "last scope credit magnitude")
    # The 0.2 policy orders actual source items by issuance, not predecessor depth.
    origins = {}
    for doc in credits:
        for item in doc["items"]:
            origins[item["origin_document_id"]] = origins.get(item["origin_document_id"], 0) + item["amount_minor"]
    sources = sorted([(new_invoice, 30000), (rebill[0], 40000)],
                     key=lambda pair: (pair[0]["posting_date"], pair[0]["key"], pair[0]["items"][0]["key"]), reverse=True)
    expected_origins, remaining = {}, 50000
    for doc, available in sources:
        take = min(remaining, available)
        if take:
            expected_origins[doc["id"]] = take
        remaining -= take
    equal(origins, expected_origins, "latest-issued actual source attribution")
    equal(amounts(lineage_units(f, d), "old", "earned_minor"), 60000, "old earnings retained")
    equal(amounts(lineage_units(f, d), "s2", "earned_minor"), 20000, "final successor consideration")
    equal(len(f.api.all("/amendments")), 2, "rebill repeated accepted commercial changes")


@case("interaction-prospective-unissued-old-earned", 4, "B16", "M4-12 M4-13 M4-14",
      "X20: the old earned-but-unbilled portion stays old when future installments are issued")
def unissued_old(c):
    f = c.f
    f.chart(separate=True)
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 100000, [promise("old", product, end="2028-01-11")],
             [installment("first", "2028-01-01", 50000, "old"), installment("future", "2028-01-10", 50000, "old")])
    f.api.at("2028-01-06")
    f.bill("2028-01-06", "2028-01-06")
    f.recognition("2028-01-06")
    f.api.at("2028-01-07")
    change = dict(price_delta_minor=30000, new_services_only=False, new_services_distinct=True,
                  remaining_distinct=True, changes_ongoing_progress=False,
                  successor_promises=[promise("new", product, ssp="700", start="2028-01-07", end="2028-02-01")], revised_group=None)
    apply(f, amend(f, d, "2028-01-07", change), "2028-01-07")
    c.checkpoint("future_installment_splits_old_earned_and_new_remaining")
    f.api.at("2028-01-10")
    f.bill("2028-01-10", "2028-01-10")
    rows = lineage_units(f, d, "2028-01-10")
    equal(amounts(rows, "old", "billed_minor"), 60000, "old earned portion billed to original")
    equal(amounts(rows, "new", "billed_minor"), 70000, "future carry plus new price billed to successor")
    equal(sum(x["total_minor"] for x in f.api.all("/documents")), 130000, "old and new consideration once")


@case("interaction-progress-dated-evidence", 4, "B14", "M4-05 M4-06 M4-07", "R20/X18: progress is chronological, current-period and distinct from delivery acceptance")
def progress_evidence(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 100000, [promise("build", product, "progress", "600", total="100", end="2028-05-01"),
                              promise("delivery", product, "acceptance", "400")],
             [installment("all", "2028-01-01", 100000, "build")])
    f.api.at("2028-02-01")
    performance(f, d, "build", "progress", "2028-01-31", "0")
    f.recognition("2028-01-31", "2028-02-01")
    f.create("/period-closes", month="2028-01")
    closed = f.report("2028-01")
    c.checkpoint("later_recorded_earlier_progress_is_not_a_regression")
    f.api.at("2028-03-01")
    performance(f, d, "build", "progress", "2028-02-29", "60")
    performance(f, d, "build", "progress", "2028-02-10", "20")
    f.recognition("2028-02-29", "2028-03-01")
    equal(amounts(units(f, d, "2028-02-29"), "build", "earned_minor"), 36000, "latest dated progress")
    equal(amounts(units(f, d, "2028-02-29"), "delivery", "earned_minor"), 0, "unaccepted delivery")
    path = f"/deals/{identifier(d['id'])}/performance"
    f.api.error("POST", path, dict(key="invalid-earlier", promise_key="build", kind="progress", effective_on="2028-02-11", completed="70"), 422, "invalid_domain")
    f.api.error("POST", path, dict(key="wrong-type", promise_key="delivery", kind="progress", effective_on="2028-02-20", completed="20"), 422, "invalid_domain")
    c.checkpoint("new_period_requires_confirmation_then_completes")
    f.api.at("2028-04-01")
    response = f.api.request("POST", "/period-closes", dict(key="missing-march", month="2028-03"), status=(200, 201))
    equal(response["operation"]["status"], "held", "last month's progress reused silently")
    performance(f, d, "build", "progress", "2028-03-31", "100")
    performance(f, d, "delivery", "acceptance", "2028-03-15")
    f.recognition("2028-03-31", "2028-04-01")
    equal(sum(earned_minor(u) for u in units(f, d, "2028-03-31")), 100000, "fully performed mixed bundle")
    closed_unchanged(closed, f.report("2028-01"))


@case("interaction-high-precision-ssp", 4, "B13", "C10 M4-03", "R24: the published numeric range still requires exact largest-remainder allocation")
def precise_ssp(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    price = 8999999999996
    d = deal(f, buyer, price, [promise(k, product, "acceptance", ssp) for k, ssp in
                              (("a", "333333.333336"), ("b", "333333.333330"), ("c", "333333.333334"))],
             [installment("all", "2028-01-01", price, "a")])
    c.checkpoint("exact_large_allocation_not_binary_float")
    equal({r["promise_key"]: r["allocation_minor"] for r in d["allocations"]},
          {"a": 3000000000022, "b": 2999999999969, "c": 3000000000005}, "high precision allocation")
    f.api.at("2028-01-31")
    for key in ("a", "b", "c"):
        performance(f, d, key, "acceptance", "2028-01-31")
    f.bill()
    f.recognition("2028-01-31")
    equal(sum(earned_minor(u) for u in units(f, d)), price, "exact conserved recognized total")


def memo_backing(cash):
    @case("interaction-commercial-credit-cash-" + str(cash), 1, "B34", "M1-18 M1-19 M1-20 M1-21",
          "X03: identical credits release only actual paid backing and preserve application provenance")
    def run(c):
        f = c.f
        f.chart()
        buyer = f.customer()
        f.subscription(buyer)
        f.api.at("2028-01-31")
        _, docs = f.bill()
        document_totals(docs, [("invoice", 10000)])
        if cash:
            receipt = f.receipt(buyer, cash)
            application = f.application(receipt, docs[0], cash)
        credit = f.memo(buyer, docs[0], 7000)
        c.checkpoint("credit_backing_and_refund")
        fields(f.statement(buyer), dict(ar_minor=max(3000-cash, 0), available_backed_minor=max(cash-3000, 0)), "credit against actual cash")
        if cash == 5000:
            f.create("/refunds", source=dict(kind="credit", id=credit["id"]), amount_minor=2000, posting_date="2028-01-31")
            fields(f.statement(buyer), dict(cash_received_minor=5000, cash_refunded_minor=2000, available_backed_minor=0), "real refunded backing")
            f.api.error("POST", f"/applications/{identifier(application['id'])}/unapply",
                        dict(allocations=[dict(document_id=docs[0]["id"], item_key=docs[0]["items"][0]["key"], amount_minor=5000)],
                             posting_date="2028-01-31"), 422, "prerequisite_failed",
                        version=f.api.get(f"/applications/{identifier(application['id'])}")["version"])
    return run


for cash in (0, 5000, 10000):
    memo_backing(cash)


def compensated_paid(refunded):
    @case("interaction-paid-credit-compensation-" + str(refunded), 1, "B34", "M1-20 M1-21 M1-25",
          "R07: compensation restores released backing only when none was refunded")
    def run(c):
        f = c.f
        f.chart()
        buyer = f.customer()
        f.subscription(buyer)
        f.api.at("2028-01-31")
        _, docs = f.bill()
        document_totals(docs, [("invoice", 10000)])
        receipt = f.receipt(buyer, 10000)
        application = f.application(receipt, docs[0], 10000)
        credit = f.memo(buyer, docs[0], 3000)
        if refunded:
            f.create("/refunds", source=dict(kind="credit", id=credit["id"]), amount_minor=refunded, posting_date="2028-01-31")
        else:
            f.unapply_source(credit)
        before = (f.statement(buyer), f.effects(), f.api.all("/documents"))
        c.checkpoint("compensation_preserves_real_cash_history")
        response = f.api.action(f"/documents/{identifier(credit['id'])}/compensate", dict(key="undo", posting_date="2028-01-31"),
                                complete=False, status=(200, 201, 422))
        if refunded:
            require("error" in response or response["operation"]["status"] == "held", "refunded credit compensated")
            equal((f.statement(buyer), f.effects(), f.api.all("/documents")), before, "invalid compensation partly committed")
        else:
            f.api.completed(response, "compensation")
            fields(f.statement(buyer), dict(ar_minor=0, available_backed_minor=0, cash_received_minor=10000), "compensation restores paid sale")
            app = f.api.get(f"/applications/{identifier(application['id'])}")
            equal(sum(x["unappliable_minor"] for x in app["allocations"]), 10000, "released receipt backing restored")
    return run


compensated_paid(0)
compensated_paid(100)


@case("interaction-earlier-recognition-does-not-reverse", 6, "B28", "M1-26 M6-02 M6-19", "R12: moving a read cutoff backwards is not a historical price correction")
def earlier_recognition(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, starts="2028-04-01", end="2028-04-04", kind="one_time")
    f.api.at("2028-04-04")
    f.bill("2028-04-04", "2028-04-04")
    f.recognition("2028-04-03", "2028-04-04")
    original = f.effects()
    c.checkpoint("earlier_cutoff_is_not_a_reversal")
    f.recognition("2028-04-01", "2028-04-04")
    equal(f.effects(), original, "earlier horizon reversed known service")
    c.checkpoint("actual_correction_remeasures_known_horizon")
    correction(f, {}, dict(kind="recorded_term", resource=dict(kind="subscription", id=sub["id"]),
                           path=["charges", "base", "price"], replacement="90"), date="2028-04-04")
    equal(sum(earned_minor(u) for u in f.units(sub, "2028-04-03")), 9000, "real correction against complete service horizon")


@case("interaction-literal-charge-key-correction", 6, "B26", "M6-02 M6-24", "R09: dotted business keys are literal path elements, not nested properties")
def literal_key(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    seed, catalog, product = f.subscription(buyer, accept=False, activate=False)
    options = copy.deepcopy(catalog["plans"][0]["charges"][0]["options"])
    options.update(model="per_unit", price="10", quantity="2")
    charges = [dict(key=k, product_id=product["id"], kind="recurring", options=dict(options), overridable=[], lookup_key=None)
               for k in ("seats.eu", "other")]
    sub, _, _ = f.subscription(buyer, product=product, charges=charges)
    f.api.at("2028-02-01")
    f.bill("2028-02-01", "2028-02-01")
    f.recognition("2028-01-31", "2028-02-01")
    c.checkpoint("literal_key_and_unchanged_sibling")
    correction(f, {}, dict(kind="recorded_term", resource=dict(kind="subscription", id=sub["id"]),
                           path=["charges", "seats.eu", "price"], replacement="12"), date="2028-02-01")
    equal({k: sum(earned_minor(u) for u in f.units(sub) if u["charge_key"] == k) for k in ("seats.eu", "other")},
          {"seats.eu": 2400, "other": 2000}, "literal key corrected without changing sibling")


def anchored_activation(year, trigger):
    @case(f"interaction-clipped-anchor-activation-{year}-{trigger}", 1, "B02", "M1-07 M1-08 M1-09 M1-26",
          "X02: clipped calendar periods, billing triggers and actual service activation remain independent")
    def run(c):
        f = c.f
        f.chart()
        buyer = f.customer()
        start, active = f"{year}-01-31", f"{year}-02-10"
        end, last, expected = ("2028-02-29", "2028-02-28", 18345) if year == 2028 else ("2029-02-28", "2029-02-27", 18000)
        f.api.at(start)
        sub, _, _ = f.subscription(buyer, price="280", starts=start, end=end, activate=False,
                                   trigger=dict(kind=trigger, date=None))
        c.checkpoint("billing_trigger_does_not_supply_service_evidence")
        response = f.api.request("POST", "/bill-runs", dict(key="first", customer_ids=None, target_date=start,
                                  invoice_date=start, posting_date=start), status=(200, 201))
        if trigger == "contract":
            f.api.action(f"/bill-runs/{identifier(response['data']['id'])}/post", dict(result_keys=None))
            equal(f.statement(buyer)["ar_minor"], 28000, "contract-triggered first invoice")
        else:
            equal(response["operation"]["status"], "held", "missing activation trigger")
        equal(sum(earned_minor(u) for u in f.units(sub, start)), 0, "no actual activation")
        f.api.at(active)
        f.evidence(sub, "base", "activation", active)
        f.bill(active, active)
        f.api.at(end)
        f.recognition(last, end)
        equal(sum(earned_minor(u) for u in f.units(sub, last)), expected, "eligible days over clipped anchored period")
        equal(f.statement(buyer)["ar_minor"], 28000, "no second fee or shifted first cycle")
    return run


for year in (2028, 2029):
    for trigger in ("contract", "activation"):
        anchored_activation(year, trigger)


@case("interaction-expired-discount-renewal-old-rebill", 3, "B12", "M3-06 M3-12 M3-16",
      "X16: renewal does not reset an expired promotion or rewrite the old discounted rebill")
def discounted_renewal(c):
    from .m3 import order, discount
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, catalog, _ = f.subscription(buyer)
    d = discount(f, buyer, kind="percentage", percentages=["10"])
    order(f, sub, "2028-01-01", [dict(kind="attach_discount", discount_id=d["id"])])
    f.api.at("2028-01-31")
    _, old = f.bill()
    document_totals(old, [("invoice", 9000)])
    latest = {k: copy.deepcopy(catalog[k]) for k in ("defaults", "plans", "price_lookups")}
    latest.update(key="feb", effective_from="2028-02-01")
    latest["plans"][0]["charges"][0]["options"]["price"] = "120"
    version = f.api.create("/catalogs", latest)
    f.api.action(f"/catalogs/{identifier(version['id'])}/publish")
    order(f, sub, "2028-02-01", [dict(kind="renew", months=1, pricing="catalog", catalog_id=version["id"])])
    latest["key"] = "newer-feb"
    latest["plans"][0]["charges"][0]["options"]["price"] = "130"
    newer = f.api.create("/catalogs", latest)
    f.api.action(f"/catalogs/{identifier(newer['id'])}/publish")
    c.checkpoint("accepted_renewal_ignores_later_catalog_and_expired_discount")
    f.api.at("2028-02-01")
    _, feb = f.bill("2028-02-01", "2028-02-01")
    document_totals(feb, [("invoice", 12000)])
    f.api.action(f"/billing-results/{identifier(old[0]['result_id'])}/reverse", dict(key="reverse-january", posting_date="2028-02-01"))
    _, rebill = f.bill("2028-02-01", "2028-02-01")
    document_totals(rebill, [("invoice", 9000)])
    immutable_document(old[0], f.api.get(f"/documents/{identifier(old[0]['id'])}"))


@case("interaction-future-amendment-delayed-application", 4, "B23", "M4-06 M4-10 M4-11 M4-22",
      "R06: a held future amendment applies at its accepted boundary after evidence arrives")
def delayed_amendment(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    p = promise("build", product, "progress", "100", total="100", end="2028-03-01")
    d = deal(f, buyer, 10000, [p], [installment("all", "2028-01-01", 10000, "build")])
    f.api.at("2028-01-10")
    commercial = dict(price_delta_minor=2000, new_services_only=False, new_services_distinct=False,
                      remaining_distinct=False, changes_ongoing_progress=True, successor_promises=[],
                      revised_group=dict(key="group", price_minor=12000, promises=[dict(p, approved_total="200")]))
    a = amend(f, d, "2028-01-16", commercial)
    c.checkpoint("not_effective_yet_does_not_apply")
    response = f.api.action(f"/amendments/{identifier(a['id'])}/apply", dict(posting_date="2028-01-10"), complete=False, status=(200, 422))
    require(f.api.get(f"/amendments/{identifier(a['id'])}")["status"] != "applied", "future amendment applied early")
    f.api.at("2028-01-16")
    response = f.api.action(f"/amendments/{identifier(a['id'])}/apply", dict(posting_date="2028-01-16"), complete=False)
    equal(response["operation"]["status"], "held", "missing progress boundary")
    f.api.at("2028-02-01")
    performance(f, d, "build", "progress", "2028-01-15", "50")
    f.recognition("2028-01-15", "2028-02-01")
    c.checkpoint("late_apply_uses_boundary_not_today")
    apply(f, a, "2028-02-01")
    equal(sum(earned_minor(u) for u in units(f, d, "2028-01-15")), 3000, "50 of revised 200 with price 120")
    performance(f, d, "build", "progress", "2028-01-31", "100")
    f.recognition("2028-01-31", "2028-02-01")
    equal(sum(earned_minor(u) for u in units(f, d, "2028-01-31")), 6000, "post-boundary progress continues")
