"""Subscriptions, document purposes, settlement, and configured accounting."""

import copy
from fractions import Fraction

from .checks import closed_unchanged, distribution, document_totals, equal, fields, integer_fields, require
from .client import identifier
from .oracles import allocate, earned, money
from .suite import case


def single(rows, label):
    equal(len(rows), 1, label + " count")
    return rows[0]


def references(value, resource_id):
    if isinstance(value, dict):
        return any(references(child, resource_id) for child in value.values())
    if isinstance(value, list):
        return any(references(child, resource_id) for child in value)
    return value == resource_id


def economics(f, billed, recognized, sub=None):
    rows = f.units(sub)
    require(rows, "no revenue units after accepted business operations")
    if recognized == 0 and any(r.get("earned_minor") is None for r in rows):
        for row in rows:
            integer_fields(row, ("billed_minor",), "revenue unit before evidence")
            if row.get("earned_minor") is None:
                require(any(i.get("code") == "missing_evidence" for i in row.get("issues", [])),
                        "underivable earnings require missing_evidence")
                require("position_minor" in row, "revenue unit missing position_minor")
                if row["position_minor"] is not None:
                    equal(row["position_minor"], row["billed_minor"], "known position before evidence")
            else:
                integer_fields(row, ("earned_minor", "position_minor"), "known revenue unit")
                equal(row["earned_minor"], 0, "earnings before evidence")
                equal(row["position_minor"], row["billed_minor"], "position before evidence")
        equal(sum(r["billed_minor"] for r in rows), billed, "billed before evidence")
        scopes = {r["scope_key"] for r in rows}
        equal(sum(e["amount_minor"] for e in f.effects()
                  if e["kind"] == "recognition" and e["scope_key"] in scopes),
              0, "no recognition before evidence")
        return
    for index, row in enumerate(rows):
        integer_fields(row, ("billed_minor", "earned_minor", "position_minor"), f"revenue unit {index}")
    equal(sum(r["billed_minor"] for r in rows), billed, "assigned billed consideration")
    equal(sum(r["earned_minor"] for r in rows), recognized, "earned consideration")
    equal(sum(r["position_minor"] for r in rows), billed - recognized, "contract position")


def immutable_document(before, after):
    fields(after, {k: before[k] for k in ("id", "key", "kind", "origin", "customer_id", "currency",
                                        "invoice_date", "posting_date", "total_minor")},
           "original posted document")
    content = ("key", "scope_key", "subscription_id", "charge_key", "product_id", "service_window",
               "amount_minor", "origin_document_id", "origin_item_key")
    for document in (before, after):
        require(isinstance(document.get("items"), list), "posted document missing items")
        for item in document["items"]:
            require(isinstance(item, dict) and all(k in item for k in content),
                    "posted item missing required immutable fields")
    expected = sorted(({k: item[k] for k in content} for item in before["items"]), key=lambda item: item["key"])
    actual = sorted(({k: item[k] for k in content} for item in after["items"]), key=lambda item: item["key"])
    equal(actual, expected, "original posted item content")


def base(c, price="100", **opts):
    f = c.f
    chart, addresses = f.chart()
    buyer = f.customer()
    sub, catalog, product = f.subscription(buyer, price=price, **opts)
    f.api.at("2028-01-31")
    return f, buyer, sub, addresses


@case("subscription-lifecycle", 1, "B04", "C04 C08 M1-08 M1-12 M1-26 M1-33",
      "Invoice, cash, activation and recognized service are not the same event")
def lifecycle(c):
    f, buyer, sub, addr = base(c, price="31", activate=False)
    c.checkpoint("preview_is_read_only")
    before = (f.api.all("/documents"), f.effects())
    run_input = dict(key="preview", customer_ids=None, target_date="2028-01-31",
                     invoice_date="2028-01-31", posting_date="2028-01-31")
    f.api.preview("/bill-runs/preview", run_input)
    f.forecast(sub, "2028-01-31")
    equal((f.api.all("/documents"), f.effects()), before, "preview mutated business state")
    c.checkpoint("draft_then_post")
    run, docs = f.bill(posted=False)
    document_totals(docs, [("invoice", 3100)])
    equal(docs[0]["status"], "draft", "invoice is still draft")
    equal(f.statement(buyer)["ar_minor"], 0, "draft is not receivable")
    equal(f.effects(), before[1], "draft posted journal entries")
    f.api.action(f"/bill-runs/{identifier(run['id'])}/post", {"result_keys": None})
    receipt = f.receipt(buyer, 3100)
    fields(f.statement(buyer), dict(ar_minor=3100, available_backed_minor=3100, cash_received_minor=3100), "unapplied receipt")
    f.recognition("2028-01-31", allow_missing_evidence=True)
    economics(f, 3100, 0, sub)
    c.checkpoint("late_activation_and_cash_application")
    f.evidence(sub, "base", "activation", "2028-01-17")
    f.recognition("2028-01-31")
    economics(f, 3100, 1500, sub)
    f.application(receipt, docs[0], 3100)
    fields(f.statement(buyer), dict(ar_minor=0, available_backed_minor=0, cash_received_minor=3100), "applied receipt")
    economics(f, 3100, 1500, sub)
    effects = f.effects()
    require(effects, "missing double-entry effects")
    for e in effects:
        equal(sum(x["debit_minor"] for x in e["legs"]), sum(x["credit_minor"] for x in e["legs"]), "effect balances")
    distribution([l for e in effects for l in e["legs"]],
                 {(addr["cash"], ()): 3100, (addr["service_revenue"], ()): -1500,
                  (addr["contract_position"], ()): -1600})


def price_case(key, options, expected, start="2028-01-01", end="2028-02-01"):
    @case(key, 1, "B03", "C09 C10 M1-04 M1-05 M1-09", "Exact configured quantity, bounds and period proration")
    def run(c):
        f, buyer, sub, _ = base(c, starts=start, end=end, **options)
        c.checkpoint("committed_price")
        _, docs = f.bill()
        if expected:
            document_totals(docs, [("invoice", expected)])
        else:
            equal(sum(d["total_minor"] for d in docs), 0, "zero-price documents")
        f.recognition("2028-01-31")
        economics(f, expected, expected, sub)
        first = f.api.all("/documents")
        f.bill()
        equal(f.api.all("/documents"), first, "overlapping run duplicated coverage")
    return run


price_case("licensed-included", dict(price="7.50", model="per_unit", quantity="9", included="4"), 3750)
price_case("licensed-at-included", dict(price="7.50", model="per_unit", quantity="4", included="4"), 0)
price_case("zero-with-minimum", dict(price="7.50", model="per_unit", quantity="0", included="4", options={"minimum_minor": 1900}), 1900)
price_case("cap-before-partial-period", dict(price="10", model="per_unit", quantity="12", options={"maximum_minor": 3100},
           period={"months": 1, "anchor": "day", "day": 1}), 1700, "2028-01-15", "2028-02-01")
price_case("half-cent-tie", dict(price="0.005", model="per_unit", quantity="1"), 1)


@case("commercial-memo-backing", 1, "B34", "C11 M1-17 M1-18 M1-19 M1-21 M1-27",
      "A commercial credit retains coverage; refunding its backing does not reduce revenue again")
def memo_backing(c):
    f, buyer, sub, addr = base(c)
    _, docs = f.bill()
    invoice = single(docs, "invoice")
    receipt = f.receipt(buyer, 5000)
    app = f.application(receipt, invoice, 5000)
    f.recognition("2028-01-31")
    c.checkpoint("credit_changes_price_not_coverage")
    credit = f.memo(buyer, invoice, 7000)
    fields(f.statement(buyer), dict(ar_minor=0, available_backed_minor=2000, cash_received_minor=5000), "credit backing")
    current_app = f.api.get(f"/applications/{identifier(app['id'])}")
    allocation = single(current_app["allocations"], "allocation")
    fields(allocation, dict(currently_applied_minor=5000, backing_released_minor=2000, unappliable_minor=3000), "overlapping backing counters")
    economics(f, 3000, 3000, sub)
    original = f.api.get(f"/documents/{identifier(invoice['id'])}")
    immutable_document(invoice, original)
    count = len(f.api.all("/documents"))
    f.bill()
    equal(len(f.api.all("/documents")), count, "commercial credit released billing coverage")
    c.checkpoint("refund_preserves_consideration")
    f.create("/refunds", source=dict(kind="credit", id=credit["id"]), amount_minor=1200, posting_date="2028-01-31")
    fields(f.statement(buyer), dict(ar_minor=0, available_backed_minor=800, cash_refunded_minor=1200), "refunded credit")
    economics(f, 3000, 3000, sub)
    snapshot = (f.statement(buyer), f.effects())
    refund_legs = [leg for effect in snapshot[1] if effect["kind"] == "refund" for leg in effect["legs"]]
    distribution(refund_legs, {(addr["customer_funds"], ()): 1200, (addr["cash"], ()): -1200},
                 "refund journal reduces backed funds and cash")
    f.api.error("POST", "/refunds", dict(key="over-refund", source=dict(kind="credit", id=credit["id"]),
                 amount_minor=801, posting_date="2028-01-31"), 422, "invalid_domain")
    equal((f.statement(buyer), f.effects()), snapshot, "rejected refund mutated balances")


@case("reverse-rebill", 1, "B35", "M1-20 M1-22 M1-23 M1-24", "Reversing coverage does not reverse service or create cash")
def reverse_rebill(c):
    f, buyer, sub, _ = base(c)
    _, docs = f.bill()
    invoice = single(docs, "invoice")
    f.recognition("2028-01-31")
    receipt = f.receipt(buyer, 10000)
    app = f.application(receipt, invoice, 10000)
    result_path = f"/billing-results/{identifier(invoice['result_id'])}"
    c.checkpoint("applied_receipt_blocks_reversal")
    preview = f.api.preview(result_path + "/reversal-preview", dict(posting_date="2028-01-31"))
    require(references(preview, app["id"]) or references(preview, app["key"]) or
            any(i.get("code") == "prerequisite_failed" and i.get("message") for i in preview.get("issues", [])),
            "reversal preview omitted settlement prerequisite")
    version = f.api.get(result_path)["version"]
    f.api.error("POST", result_path + "/reverse", dict(key="blocked", posting_date="2028-01-31"),
                422, "prerequisite_failed", version=version)
    economics(f, 10000, 10000, sub)
    c.checkpoint("unapply_reverse_rebill")
    f.api.action(f"/applications/{identifier(app['id'])}/unapply",
                 dict(allocations=[dict(document_id=invoice["id"], item_key=invoice["items"][0]["key"], amount_minor=10000)],
                      posting_date="2028-01-31"))
    f.api.action(result_path + "/reverse", dict(key="reverse", posting_date="2028-01-31"))
    economics(f, 0, 10000, sub)
    fields(f.statement(buyer), dict(ar_minor=0, available_backed_minor=10000, cash_received_minor=10000), "after reversal")
    _, replacement = f.bill()
    document_totals(replacement, [("invoice", 10000)])
    require(replacement[0]["id"] != invoice["id"], "rebill reused original invoice")
    require(any(i.get("origin_document_id") == invoice["id"] for i in replacement[0]["items"])
            or invoice["id"] in replacement[0]["related_ids"], "rebill lacks predecessor lineage")
    f.application(receipt, replacement[0], 10000)
    economics(f, 10000, 10000, sub)
    fields(f.statement(buyer), dict(ar_minor=0, cash_received_minor=10000), "rebill settlement")
    immutable_document(invoice, f.api.get(f"/documents/{identifier(invoice['id'])}"))


@case("memo-compensation", 1, "B34", "M1-17 M1-25", "Compensation changes consideration without making service unbilled")
def compensation(c):
    f, buyer, sub, _ = base(c)
    _, docs = f.bill()
    invoice = single(docs, "invoice")
    credit = f.memo(buyer, invoice, 2500)
    f.recognition("2028-01-31")
    economics(f, 7500, 7500, sub)
    c.checkpoint("compensate_then_sweep")
    f.unapply_source(credit)
    f.api.action(f"/documents/{identifier(credit['id'])}/compensate", dict(key="compensate", posting_date="2028-01-31"))
    economics(f, 10000, 10000, sub)
    docs = f.api.all("/documents")
    document_totals(docs, [("invoice", 10000), ("credit", 2500), ("debit", 2500)])
    f.bill()
    equal(f.api.all("/documents"), docs, "compensation reopened coverage")


@case("close-and-cumulative-cents", 1, "B04", "C10 C11 M1-26 M1-32 M1-34",
      "Cumulative rounding and real close are preserved after later operations")
def close_cents(c):
    from .fixtures import currency_report
    from .checks import report_journal_movements
    f, buyer, sub, addr = base(c, price="0.31", end="2028-03-01", kind="one_time")
    f.api.at("2028-01-01")
    f.bill(target="2028-01-01", post="2028-01-01")
    for date, completed in (("2028-01-01", 1), ("2028-01-17", 17), ("2028-01-31", 31)):
        f.api.at(date)
        f.recognition(date)
        economics(f, 31, earned(31, completed, 60), sub)
    c.checkpoint("closed_month_remains_fixed")
    f.api.at("2028-02-01")
    f.create("/period-closes", month="2028-01")
    report = f.report("2028-01")
    january = currency_report(report)
    equal(january["closed"], True, "January close status")
    accounts = {r["account_key"]: r for r in january["accounts"] if not r["segments"]}
    fields(accounts.get(addr["contract_position"]), dict(opening_net_debit_minor=0,
           net_debit_minor=-15, closing_net_debit_minor=-15), "January contract position")
    fields(accounts.get(addr["service_revenue"]), dict(opening_net_debit_minor=0,
           net_debit_minor=-16, closing_net_debit_minor=-16), "January revenue")
    entries = f.api.all("/journal-entries")
    c.observations.append(dict(measurement='report_gross_reconciliation', month='2028-01',
                              checked=report_journal_movements(january['accounts'], entries, '2028-01')))
    f.api.at("2028-02-29")
    f.recognition("2028-02-29")
    economics(f, 31, 31, sub)
    february = currency_report(f.report("2028-02"))
    accounts = {r["account_key"]: r for r in february["accounts"] if not r["segments"]}
    fields(accounts.get(addr["contract_position"]), dict(opening_net_debit_minor=-15,
           net_debit_minor=15, closing_net_debit_minor=0), "February contract position")
    fields(accounts.get(addr["service_revenue"]), dict(opening_net_debit_minor=-16,
           net_debit_minor=-15, closing_net_debit_minor=-31), "February revenue")
    c.observations.append(dict(measurement='report_gross_reconciliation', month='2028-02',
                              checked=report_journal_movements(february['accounts'], f.api.all('/journal-entries'), '2028-02')))
    f.recognition("2028-01-17", "2028-02-29")
    economics(f, 31, 31, sub)
    closed_unchanged(report, f.report("2028-01"))
    after = {e["id"]: e for e in f.api.all("/journal-entries")}
    for entry in entries:
        equal(after[entry["id"]], entry, "posted journal immutable")


@case("tenant-roles-pagination", 1, "B29", "C01 C03 C12 C13 C14", "Tenant/role scope is enforced at HTTP, with complete stable reads")
def roles(c):
    f = c.f
    buyer, sibling = f.customer("buyer"), f.customer("sibling")
    product = f.product("service")
    c.checkpoint("role_and_tenant_boundaries")
    customer_api = f.api.actor("customer", buyer["id"])
    equal(customer_api.get(f"/customers/{identifier(buyer['id'])}")["id"], buyer["id"], "own customer")
    customer_api.error("GET", f"/customers/{identifier(sibling['id'])}", None, 404, "not_found")
    customer_api.error("POST", "/products", dict(key="forbidden", name="Bad", attrs={}), 403, "forbidden")
    f.api.request("GET", f"/customers/{identifier(buyer['id'])}", status=401, authenticated=False)
    from .fixtures import Fixture
    other = Fixture(f.api.base_url, f.api.secret, "other", f.api.trace)
    other_buyer = other.customer("buyer")
    other.api.error("GET", f"/customers/{identifier(buyer['id'])}", None, 404, "not_found")
    f.api.error("PUT", f"/customers/{identifier(buyer['id'])}",
                dict(name="Buyer", attrs={}, parent_id=other_buyer["id"]), 404, "not_found", version=buyer["version"])
    for key in ("z", "a", "middle"):
        f.customer(key)
    c.checkpoint("pagination")
    rows, cursor = [], None
    from urllib.parse import urlencode
    for _ in range(5):
        query = {"limit": 2}
        if cursor:
            query["cursor"] = cursor
        response = f.api.request("GET", "/customers?" + urlencode(query), status=200)
        rows.extend(response["data"])
        cursor = response["next_cursor"]
        if cursor is None:
            break
    equal([r["key"] for r in rows], ["a", "buyer", "middle", "sibling", "z"], "stable complete paging")
    visible = customer_api.all("/customers")
    equal([r["id"] for r in visible], [buyer["id"]], "customer collection scope")
    f.api.error("PUT", f"/customers/{identifier(buyer['id'])}",
                dict(name="Buyer", attrs={}, parent_id=buyer["id"]), 422, "invalid_domain", version=buyer["version"])


@case("mutation-replay", 1, "B33", "C05 C06", "Replay precedes version guards; rejected input does not consume identity")
def replay(c):
    f, buyer, sub, _ = base(c)
    c.checkpoint("replay_and_conflict")
    path = "/receipts"
    body = dict(key="cash", customer_id=buyer["id"], currency="USD", amount_minor=1000,
                payment_method="bank", posting_date="2028-01-31")
    response = f.api.request("POST", path, body, status=201, key="receipt-retry")
    f.api.at("2028-02-01")
    equal(f.api.request("POST", path, body, status=201, key="receipt-retry"), response, "accepted replay")
    f.api.error("POST", path, dict(body, amount_minor=999), 409, "idempotency_conflict", key="receipt-retry")
    equal(len(f.api.all("/receipts")), 1, "replay receipt count")
    invalid = dict(body, key="later", amount_minor=-1)
    f.api.error("POST", path, invalid, 400, "invalid_request", key="reusable")
    f.api.create(path, dict(invalid, amount_minor=500), key="reusable")
    equal(f.statement(buyer)["cash_received_minor"], 1500, "rejected request poisoned key")
    c.checkpoint("accepted_replay_precedes_stale_version")
    customer_path = f"/customers/{identifier(buyer['id'])}"
    update = dict(name="Updated", parent_id=None, attrs={})
    response = f.api.request("PUT", customer_path, update, status=200,
                             key="customer-update", version=buyer["version"])
    equal(f.api.request("PUT", customer_path, update, status=200,
                        key="customer-update", version=buyer["version"]), response, "versioned update replay")
    f.api.error("PUT", customer_path, dict(update, name="Stale"), 409, "stale_version",
                key="stale-update", version=buyer["version"])
    equal(f.api.get(customer_path)["name"], "Updated", "stale version changed resource")


@case("split-chart", 1, "B30", "C02 C10 M1-28 M1-29 M1-30", "Balanced journals still must use tenant-defined split addresses")
def chart_split(c):
    f = c.f
    chart, addresses = f.chart()
    body = {k: copy.deepcopy(chart[k]) for k in ("effective_from", "position_mode", "correction_routing",
                                                "accounts", "segments", "lookups", "rules")}
    body.update(key="split-chart", effective_from="2028-02-01")
    revenue = next(r for r in body["rules"] if r["function"] == "service_revenue")
    body["segments"] = [dict(key="division", values=[dict(key="east", parent_key=None), dict(key="west", parent_key=None)])]
    for a in body["accounts"]:
        if a["key"] == addresses["service_revenue"]:
            a["required_segments"] = ["division"]
    revenue["distribution"] = [dict(key="alpha", weight="50", account={"constant": addresses["service_revenue"]}, segments={"division": {"constant": "east"}}),
                               dict(key="beta", weight="50", account={"constant": addresses["service_revenue"]}, segments={"division": {"constant": "west"}})]
    new = f.api.create("/accounting-configurations", body)
    f.api.action(f"/accounting-configurations/{identifier(new['id'])}/publish")
    f.api.at("2028-02-01")
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price="0.05", starts="2028-02-01", end="2028-03-01",
                               kind="one_time", recognition="acceptance", activate=False)
    f.api.at("2028-02-29")
    f.bill("2028-02-29", "2028-02-29")
    f.evidence(sub, "base", "acceptance", "2028-02-29")
    c.checkpoint("configured_cent_split")
    f.recognition("2028-02-29")
    recognized = [e for e in f.effects() if e["kind"] == "recognition"]
    require(recognized, "no recognition effects")
    legs = [l for e in recognized for l in e["legs"]]
    distribution(legs, {(addresses["contract_position"], ()): 5,
                         (addresses["service_revenue"], (("division", "east"),)): -3,
                         (addresses["service_revenue"], (("division", "west"),)): -2})
    economics(f, 5, 5, sub)


@case("catalog-lookup-retention", 1, "B01", "M1-01 M1-02 M1-03", "Accepted options preserve lookup, override and catalog provenance across profile changes")
def catalog_retention(c):
    f = c.f
    f.chart()
    buyer = f.customer(attrs={"segment": "enterprise"})
    product = f.product()
    # Fully typed lower defaults remain available to charge variants and overrides.
    opt = dict(model="per_unit", price="9", quantity="4", included="1", minimum_minor=None, maximum_minor=None,
               period=dict(months=1, anchor="service_start", day=None), billing="advance",
               trigger=dict(kind="contract", date=None), recognition="stand_ready")
    body = dict(key="catalog-one", effective_from="2028-01-01", defaults={}, price_lookups=[dict(key="segment-price",
                rows=[dict(key="enterprise", priority=1, when={"eq": {"field": "customer.attrs.segment", "value": "enterprise"}},
                           options={"price": "3"})], fallback={"price": "5"})],
                plans=[dict(key="seat-plan", name="Seats", charges=[dict(key="seats", product_id=product["id"], kind="recurring",
                     options=opt, overridable=["quantity"], lookup_key="segment-price")]),
                       dict(key="base-plan", name="Base", charges=[dict(key="base", product_id=product["id"], kind="recurring",
                     options=dict(opt, model="flat", quantity="1", included="0", price="1"), overridable=[], lookup_key=None)])])
    catalog = f.api.create("/catalogs", body)
    f.api.action(f"/catalogs/{identifier(catalog['id'])}/publish")
    def subscribe(cat, key):
        sub = f.create("/subscriptions", key=key, customer_id=buyer["id"], currency="USD", starts_on="2028-01-01", ends_before="2028-02-01",
                       renewal_months=None, plans=[dict(catalog_id=cat["id"], plan_key="seat-plan", overrides={"seats": {"quantity": "6"}}),
                                                  dict(catalog_id=cat["id"], plan_key="base-plan", overrides={})], attrs={})
        f.api.action(f"/subscriptions/{identifier(sub['id'])}/accept")
        return sub
    sub = subscribe(catalog, "original")
    resolved = f.api.get(f"/subscriptions/{identifier(sub['id'])}")["resolved_charges"]
    seats = next(r for r in resolved if r["key"] == "seats")
    equal(Fraction(seats["options"]["price"]), Fraction(3), "lookup-selected price")
    equal(Fraction(seats["options"]["quantity"]), Fraction(6), "allowed override")
    require(seats["source_versions"], "missing retained option provenance")
    c.checkpoint("profile_and_catalog_change_preserve_old_sale")
    f.api.request("PUT", f"/customers/{identifier(buyer['id'])}", dict(name="Renamed buyer", parent_id=None, attrs={"segment": "small"}),
                  status=200, version=buyer["version"])
    new_body = copy.deepcopy(body)
    new_body["key"] = "catalog-two"
    new_body["price_lookups"][0]["fallback"] = {"price": "7"}
    newer = f.api.create("/catalogs", new_body)
    f.api.action(f"/catalogs/{identifier(newer['id'])}/publish")
    subscribe(newer, "new-sale")
    equal(f.api.get(f"/subscriptions/{identifier(sub['id'])}")["resolved_charges"], resolved, "retained accepted terms")
    f.api.at("2028-01-31")
    _, docs = f.bill()
    document_totals(docs, [("invoice", 5200)])
    equal(sum(i["amount_minor"] for d in docs for i in d["items"] if i["subscription_id"] == sub["id"]), 1600, "old retained lookup price")


@case("calendar-anchors-and-finite-term", 1, "B02", "M1-06 M1-07 M1-09", "Month clipping does not drift the anchor or extend a finite term")
def calendar(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price="29", starts="2028-01-31", end="2028-05-31", activate=False)
    f.api.at("2028-05-31")
    f.evidence(sub, "base", "activation", "2028-01-31")
    c.checkpoint("restored_anchor_and_posted_windows")
    _, docs = f.bill("2028-05-31", "2028-05-31")
    document_totals(docs, [("invoice", 11600)])
    windows = sorted((i["service_window"]["starts_on"], i["service_window"]["ends_before"]) for d in docs for i in d["items"])
    equal(windows, [("2028-01-31", "2028-02-29"), ("2028-02-29", "2028-03-31"),
                    ("2028-03-31", "2028-04-30"), ("2028-04-30", "2028-05-31")], "anchored periods")
    future = f.forecast(sub, "2030-01-01")
    equal(sum(r["net_minor"] for r in future), 11600, "finite forecast does not invent renewal")
    f.recognition("2028-05-31")
    economics(f, 11600, 11600, sub)


@case("bill-run-held-scope-recovery", 1, "B33", "M1-08 M1-10 M1-14 M1-15", "Independent held charges recover inside the original frozen selection")
def partial_bill(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    a, _, _ = f.subscription(buyer, price="30")
    b, _, _ = f.subscription(buyer, price="70", trigger=dict(kind="acceptance", date=None), activate=False)
    f.api.at("2028-01-31")
    body = dict(key="original-selection", customer_ids=None, target_date="2028-01-31", invoice_date="2028-01-31", posting_date="2028-01-31")
    response = f.api.request("POST", "/bill-runs", body, status=(200, 201))
    run = response["data"]
    c.checkpoint("independent_scope_posts")
    response = f.api.action(f"/bill-runs/{identifier(run['id'])}/post", {"result_keys": None}, complete=False)
    require(response["operation"]["status"] in ("partial", "completed"), "ready scope did not post")
    posted = [d for d in f.api.all("/documents") if d["status"] == "posted"]
    document_totals(posted, [("invoice", 3000)])
    newcomer = f.customer("new-buyer")
    f.subscription(newcomer, price="99")
    f.evidence(b, "base", "acceptance", "2028-01-20", "2028-01-01")
    f.api.action(f"/bill-runs/{identifier(run['id'])}/retry", dict(mode="generate"))
    f.api.action(f"/bill-runs/{identifier(run['id'])}/post", {"result_keys": None})
    all_posted = [d for d in f.api.all("/documents") if d["status"] == "posted"]
    document_totals(all_posted, [("invoice", 3000), ("invoice", 7000)])
    equal(f.statement(newcomer)["ar_minor"], 0, "retry swept a newly created customer")


@case("schedule-occurrences", 1, "B33", "M1-06 M1-11", "Skipped processing dates materialize anchored occurrences once")
def schedules(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    f.subscription(buyer, price="10", starts="2028-01-01", end="2028-04-01")
    schedule = f.create("/bill-schedules", starts_on="2028-01-31", ends_before="2028-04-01",
                         cadence="monthly", month_day=31, customer_ids=[buyer["id"]])
    f.api.at("2028-03-31")
    c.checkpoint("missed_months_and_exact_replay")
    path = f"/bill-schedules/{identifier(schedule['id'])}/process"
    body = dict(through="2028-03-31", invoice_date="2028-03-31", posting_date="2028-03-31")
    f.api.action(path, body)
    runs = f.api.all("/bill-runs")
    equal(len(runs), 3, "schedule occurrence count")
    f.api.action(path, body)
    equal(f.api.all("/bill-runs"), runs, "schedule processing duplicated occurrences")
    # Scheduling generates runs; explicit posting still belongs to the operator.
    for run in runs:
        response = f.api.action(f"/bill-runs/{identifier(run['id'])}/post", dict(result_keys=None), complete=False)
        if response["operation"]["status"] in ("held", "partial"):
            f.api.action(f"/bill-runs/{identifier(run['id'])}/retry", dict(mode="generate"), complete=False)
            f.api.action(f"/bill-runs/{identifier(run['id'])}/post", dict(result_keys=None))
    equal(sum(d["total_minor"] for d in f.api.all("/documents") if d["status"] == "posted"), 3000, "scheduled posted coverage")


@case("currency-isolation", 1, "B29", "C07 M1-15 M1-18", "One customer can owe two currencies, but a receipt cannot cross between them")
def currencies(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    f.subscription(buyer, price="40", currency="USD")
    f.subscription(buyer, price="40", currency="EUR")
    f.api.at("2028-01-31")
    _, docs = f.bill()
    equal(sorted((d["currency"], d["total_minor"]) for d in docs), [("EUR", 4000), ("USD", 4000)], "currency grouping")
    invoices = {d["currency"]: d for d in docs}
    cash = f.receipt(buyer, 4000)
    before = (f.statement(buyer, "USD"), f.statement(buyer, "EUR"), f.effects())
    c.checkpoint("reject_cross_currency_allocation_atomically")
    f.api.error("POST", "/applications", dict(key="cross-currency", source=dict(kind="receipt", id=cash["id"]),
                allocations=[dict(document_id=invoices["EUR"]["id"], item_key=invoices["EUR"]["items"][0]["key"], amount_minor=4000)],
                posting_date="2028-01-31"), 422, "invalid_domain")
    equal((f.statement(buyer, "USD"), f.statement(buyer, "EUR"), f.effects()), before, "rejected currency application changed books")
    f.application(cash, invoices["USD"], 4000)
    fields(f.statement(buyer, "USD"), dict(ar_minor=0, cash_received_minor=4000), "USD settlement")
    fields(f.statement(buyer, "EUR"), dict(ar_minor=4000, cash_received_minor=0), "EUR remains unpaid")


@case("draft-cancel-and-competing-coverage", 1, "B33", "M1-12 M1-13", "Unrelated activity leaves a draft valid; cancellation releases work and competitors cannot double bill")
def draft_coverage(c):
    f, buyer, sub, _ = base(c, price="40")
    run, docs = f.bill(posted=False)
    f.customer("unrelated")
    f.product("unrelated")
    c.checkpoint("unrelated_change_does_not_stale_draft")
    f.api.action(f"/bill-runs/{identifier(run['id'])}/post", dict(result_keys=None))
    equal(f.statement(buyer)["ar_minor"], 4000, "unrelated changes blocked posting")
    other = f.customer("second")
    f.subscription(other, price="60")
    cancelled, draft = f.bill(customers=[other["id"]], posted=False)
    document_totals(draft, [("invoice", 6000)], "linked draft awaiting cancellation")
    f.api.action(f"/documents/{identifier(draft[0]['id'])}/cancel")
    first, _ = f.bill(customers=[other["id"]], posted=False)
    second = f.api.request("POST", "/bill-runs", dict(key="competitor", customer_ids=[other["id"]],
                           target_date="2028-01-31", invoice_date="2028-01-31", posting_date="2028-01-31"), status=(200, 201))
    f.api.action(f"/bill-runs/{identifier(first['id'])}/post", dict(result_keys=None))
    c.checkpoint("competing_run_cannot_repost_covered_work")
    if second.get("data"):
        path = f"/bill-runs/{identifier(second['data']['id'])}"
        response = f.api.request("POST", path + "/post", dict(result_keys=None), status=(200, 409),
                                 version=f.api.get(path)["version"])
        if "error" in response:
            require(response["error"]["code"] in ("stale_basis", "already_final"), "unexpected competing coverage rejection")
    equal(f.statement(other)["ar_minor"], 6000, "cancel or competitor changed billed amount")
    posted = [d for d in f.api.all("/documents") if d["status"] == "posted"]
    document_totals(posted, [("invoice", 4000), ("invoice", 6000)])
    rows = f.units({"id": f.api.all("/subscriptions", customer_id=other["id"])[0]["id"]})
    equal(sum(r["billed_minor"] for r in rows), 6000, "assigned billed consideration")
    scopes = {r["scope_key"] for r in rows}
    require(not any(e["kind"] == "recognition" and e["scope_key"] in scopes for e in f.effects()),
            "billing posted recognition without a recognition run")


@case("separate-positions-not-customer-net", 1, "B30", "M1-31 M1-33", "Asset and deferred balances are per sale even for a single customer")
def separate_positions(c):
    f = c.f
    _, addr = f.chart(separate=True)
    buyer = f.customer()
    delivered, _, _ = f.subscription(buyer, price="40", billing="arrears")
    waiting, _, _ = f.subscription(buyer, price="40", activate=False)
    f.api.at("2028-01-31")
    f.bill()
    f.recognition("2028-01-31", allow_missing_evidence=True)
    economics(f, 0, 4000, delivered)
    economics(f, 4000, 0, waiting)
    c.checkpoint("gross_asset_and_deferred_survive_equal_net")
    distribution([leg for e in f.effects() for leg in e["legs"]],
                 {(addr["receivable"], ()): 4000, (addr["contract_asset"], ()): 4000,
                  (addr["deferred"], ()): -4000, (addr["service_revenue"], ()): -4000})
    f.api.at("2028-02-01")
    f.bill("2028-02-01", "2028-02-01")
    economics(f, 4000, 4000, delivered)
    economics(f, 4000, 0, waiting)
    distribution([leg for e in f.effects() for leg in e["legs"]],
                 {(addr["receivable"], ()): 8000, (addr["deferred"], ()): -4000,
                  (addr["service_revenue"], ()): -4000})


def invoice_grouping(mode, expected):
    @case("invoice-grouping-" + mode, 1, "B33", "C02 M1-15", "Configured grouping changes document layout, not charge economics")
    def run(c):
        f = c.f
        f.chart()
        if mode != "payer":
            f.api.request("PUT", "/settings", dict(defaults={}, grouping=mode), status=200, version=f.tenant["version"])
        buyer = f.customer()
        a, _, _ = f.subscription(buyer, price="25")
        b, _, _ = f.subscription(buyer, price="75")
        f.api.at("2028-01-31")
        c.checkpoint("configured_document_partition")
        _, docs = f.bill()
        document_totals(docs, [("invoice", amount) for amount in expected])
        equal(sorted((i["subscription_id"], i["amount_minor"]) for d in docs for i in d["items"]),
              sorted([(a["id"], 2500), (b["id"], 7500)]), "retained item attribution")
        equal(f.statement(buyer)["ar_minor"], 10000, "grouping preserves total debt")
    return run


invoice_grouping("payer", [10000])
invoice_grouping("payer_subscription", [2500, 7500])


@case("zero-price-coverage", 1, "B33", "C08 M1-16", "Completed free service is covered once; an empty customer selection stays empty")
def zero_coverage(c):
    f, buyer, sub, _ = base(c, price="0")
    empty = f.api.request("POST", "/bill-runs", dict(key="empty", customer_ids=[], target_date="2028-01-31",
                         invoice_date="2028-01-31", posting_date="2028-01-31"), status=(200, 201))
    f.api.completed(empty, "empty customer selection")
    if empty["data"] is not None:
        require(not f.bill_scopes(empty["data"]), "empty selection swept all customers")
    equal(f.api.all("/documents"), [], "empty selection generated documents")
    c.checkpoint("free_service_has_real_coverage")
    first, _ = f.bill()
    require(any(s["status"] in ("posted", "covered") for s in first["scopes"]), "free service was not completed")
    second, _ = f.bill()
    require(not any(s["status"] in ("draft", "posted", "held") for s in second["scopes"]),
            "repeated free service generated new or held work")
    require(not any(d["total_minor"] for d in f.api.all("/documents")), "free service generated nonzero document")
    economics(f, 0, 0, sub)


def routing_contrast(mode):
    @case("account-routing-" + mode, 1, "B30", "C06 M1-28 M1-29 M1-30", "Selected missing context cannot fall through; equal-priority rules compare resolved addresses")
    def run(c):
        f = c.f
        chart, addresses = f.chart()
        body = {k: copy.deepcopy(chart[k]) for k in ("effective_from", "position_mode", "correction_routing",
                                                    "accounts", "segments", "lookups", "rules")}
        body.update(key="routing-contrast", effective_from="2028-01-02")
        revenue = next(r for r in body["rules"] if r["function"] == "service_revenue")
        selected = copy.deepcopy(revenue)
        selected.update(key="chosen", priority=1)
        if mode == "missing-context":
            selected["distribution"][0]["account"] = {"field": "customer.attrs.posting_account"}
        elif mode == "conflicting":
            selected["priority"] = revenue["priority"]
            alternate = copy.deepcopy(next(a for a in body["accounts"] if a["key"] == addresses["service_revenue"]))
            alternate["key"] = "another-revenue-account"
            body["accounts"].append(alternate)
            selected["distribution"][0]["account"] = {"constant": alternate["key"]}
        else:
            selected["priority"] = revenue["priority"]
        body["rules"].append(selected)
        config = f.api.create("/accounting-configurations", body)
        f.api.action(f"/accounting-configurations/{identifier(config['id'])}/publish")
        buyer = f.customer()
        sub, _, _ = f.subscription(buyer, price="50", starts="2028-01-02", kind="one_time", recognition="acceptance", activate=False)
        f.api.at("2028-01-31")
        f.evidence(sub, "base", "acceptance", "2028-01-31")
        f.bill()
        before = f.effects()
        c.checkpoint("resolve_matching_rule_set")
        response = f.api.request("POST", "/recognition-runs", dict(key="recognize", through="2028-01-31", posting_date="2028-01-31"),
                                 status=(200, 201) if mode == "identical" else 200)
        if mode == "identical":
            f.api.completed(response, "identical resolved rule ties")
            economics(f, 5000, 5000, sub)
            recognition = [e for e in f.effects() if e["kind"] == "recognition"]
            legs = [leg for e in recognition for leg in e["legs"] if leg["function"] == "service_revenue"]
            require(legs, "missing resolved revenue legs")
            equal({leg["rule_key"] for leg in legs}, {"chosen"}, "lexicographic identical-rule provenance")
        else:
            equal(response["operation"]["status"], "held", "invalid selected routing must hold")
            require(response["operation"]["issues"], "held routing lacks explanation")
            equal(f.effects(), before, "held recognition partially posted")
            # Earned service can be reported even while its journal posting is held.
            equal(sum(r["billed_minor"] for r in f.units(sub)), 5000, "held recognition changed billing")
    return run


for routing_mode in ("missing-context", "conflicting", "identical"):
    routing_contrast(routing_mode)


@case("commercial-credit-separate-position", 1, "B30", "M1-17 M1-27 M1-31",
      "A credit and its revenue remeasurement can cross asset/deferred zero within one operation")
def commercial_separate(c):
    f = c.f
    _, addr = f.chart(separate=True)
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price="20", activate=False)
    f.api.at("2028-01-31")
    f.evidence(sub, "base", "activation", "2028-01-17")
    _, docs = f.bill()
    f.recognition("2028-01-31")
    economics(f, 2000, earned(2000, 15, 31), sub)
    c.checkpoint("credit_and_remeasurement_preserve_separate_positions")
    f.memo(buyer, single(docs, "invoice"), 1800)
    recognized = earned(200, 15, 31)
    economics(f, 200, recognized, sub)
    distribution([leg for effect in f.effects() for leg in effect["legs"]],
                 {(addr["receivable"], ()): 200,
                  (addr["service_revenue"], ()): -recognized,
                  (addr["deferred"], ()): -(200 - recognized)}, "actual separate-mode balances")


def small_correction_routing(routing):
    @case("rounded-correction-routing-" + routing, 1, "B30", "M1-17 M1-27 M1-32 M1-34",
          "A changed chart affects target addresses even on days whose rounded revenue does not change")
    def run(c):
        f, buyer, sub, old = base(c, price="0.31")
        _, docs = f.bill()
        f.recognition("2028-01-31")
        economics(f, 31, 31, sub)
        f.api.at("2028-02-01")
        f.create("/period-closes", month="2028-01")
        closed = f.report("2028-01")
        before = f.effects()
        _, new = f.chart(effective="2028-02-01", prefix="new", routing=routing)
        equal(f.effects(), before, "chart publication changed past effects")
        c.checkpoint("remeasure_target_distribution_not_only_changed_amounts")
        f.memo(buyer, single(docs, "invoice"), 1, post="2028-02-01")
        economics(f, 30, 30, sub)
        ids = {effect["id"] for effect in before}
        after = f.effects()
        added = [effect for effect in after if effect["id"] not in ids]
        legs = [leg for effect in added if effect["kind"] == "recognition"
                for leg in effect["legs"] if leg["function"] == "service_revenue"]
        expected = {(old["service_revenue"], ()): 1} if routing == "original" else {
            (old["service_revenue"], ()): 31, (new["service_revenue"], ()): -30}
        distribution(legs, expected, "old and target revenue addresses after one-cent correction")
        by_id = {effect["id"]: effect for effect in after}
        for effect in before:
            equal(by_id[effect["id"]], effect, "historical effect changed")
        closed_unchanged(closed, f.report("2028-01"))
    return run


small_correction_routing("original")
small_correction_routing("current")
