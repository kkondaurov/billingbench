"""Configured gross accounting, effective addresses and corrected report history."""

import copy

from .checks import earned_minor, equal, fields, require, document_totals, distribution, closed_unchanged
from .client import identifier
from .m2 import Usage
from .m5 import grant
from .m6 import correction
from .funding_interactions import shared_discount
from .interactions import retry_orders
from .suite import case


def presentation(f, mode):
    kinds = {"cash": "asset", "receivable": "asset", "customer_funds": "liability", "service_revenue": "revenue",
             "contract_position": "asset", "capacity_expiry_revenue": "revenue", "discount": "revenue"}
    accounts = [dict(key="book-"+k, name=k, **{"class": v}, parent_key=None, posting=True, starts_on="2020-01-01",
                     ends_before=None, required_segments=[]) for k, v in kinds.items()]
    rules = [dict(key=k, function=k, priority=1, when={"all": []}, distribution=[dict(key="all", weight="100",
                  account={"constant": "book-"+k}, segments={})]) for k in kinds]
    return f.chart(accounts=accounts, rules=rules, capacity=True, revenue_presentation=mode)


def gross_funding(mode, face):
    @case(f"interaction-funded-{mode}-presentation-{face}", 5, "B30", "M3-02 M5-09 M5-10 M5-12",
          "R11: gross and discount apply only to unfunded usage, not paid capacity basis")
    def run(c):
        f = c.f
        presentation(f, mode)
        u = Usage(f)
        f.api.at("2028-01-01")
        shared_discount(f, u.customers, u.subscriptions, percentage="10")
        grant(f, u.customers[0], u.consumers, u.product, face, face*4//5)
        f.api.at("2028-02-01")
        u.event("work", "80")
        u.complete()
        retry_orders(f)
        c.checkpoint("gross_discount_and_paid_basis_are_different_components")
        u.finish()
        overage = max(7200-face, 0)
        basis = min(face, 7200)*4//5
        equal(sum(r["overage_minor"] for r in u.rows()), overage, "discounted funding shortfall")
        legs = [l for e in f.effects() for l in e["legs"] if l["function"] in ("service_revenue", "discount")]
        if mode == "gross" and overage:
            expected = {("book-service_revenue", ()): -(2000+basis), ("book-discount", ()): 200}
        else:
            expected = {("book-service_revenue", ()): -(overage+basis)}
        distribution(legs, expected, "gross presentation without grossing up grant consumption")
    return run


for mode in ("gross", "net"):
    for face in (5400, 7200):
        gross_funding(mode, face)


@case("interaction-report-opening-and-correction-month", 6, "B28", "M6-19 M6-20",
      "R22: corrected historical openings do not double-count the later posting-month adjustment")
def current_report(c):
    f = c.f
    _, addresses = f.chart()
    buyer = f.customer()
    april, _, _ = f.subscription(buyer, price="40", starts="2028-04-01", end="2028-05-01")
    may, _, _ = f.subscription(buyer, starts="2028-05-01", end="2028-06-01")
    f.api.at("2028-06-01")
    f.bill("2028-06-01", "2028-05-31")
    f.recognition("2028-04-30", "2028-04-30")
    f.recognition("2028-05-31", "2028-05-31")
    f.create("/period-closes", month="2028-04")
    f.create("/period-closes", month="2028-05")
    closed = f.report("2028-05")
    c.checkpoint("correct_may_without_counting_june_twice")
    f.api.at("2028-06-20")
    correction(f, {}, dict(kind="recorded_term", resource=dict(kind="subscription", id=may["id"]),
                           path=["charges", "base", "price"], replacement="80"), date="2028-06-20")
    expected = {("2028-05", "as_posted"): (-4000, -10000, -14000),
                ("2028-05", "current"): (-4000, -8000, -12000),
                ("2028-06", "as_posted"): (-14000, 2000, -12000),
                ("2028-06", "current"): (-12000, 0, -12000)}
    for (month, view), (opening, movement, closing) in expected.items():
        report = f.report(month, view)
        matches = [r for r in report["accounts"] if r["account_key"] == addresses["service_revenue"] and not r["segments"]]
        require(len(matches) == 1, "report missing unique service-revenue account row")
        row = matches[0]
        fields(row, dict(opening_net_debit_minor=opening, net_debit_minor=movement, closing_net_debit_minor=closing), month+" "+view)
    closed_unchanged(closed, f.report("2028-05"))


@case("interaction-source-typed-idempotency", 2, "B33", "C05 M2-02", "R15: typed quantity and instant spellings replay, literal strings do not normalize")
def logical_identity(c):
    f = c.f
    f.chart()
    u = Usage(f)
    path = f"/sources/{identifier(u.source['id'])}/events"
    body = dict(key="typed", event_key="typed", revision=1, state="active", event_type="request", alias="project-0",
                occurred_at="2028-01-20T12:00:00Z", quantity="10", identity=None, interval=None, dimensions={"billable": "yes"})
    original = f.api.request("POST", path, body, key="same-logical-request", status=201)
    c.checkpoint("logical_not_serialized_request_identity")
    replay = f.api.request("POST", path, dict(body, quantity="10.000000", occurred_at="2028-01-20T12:00:00+00:00"),
                           key="same-logical-request", status=201)
    equal(replay, original, "equivalent typed request returns saved response")
    f.api.error("POST", path, dict(body, dimensions={"billable": "no"}), 409, "idempotency_conflict", key="same-logical-request")
    reader = f.api.actor("customer", u.customers[0]["id"])
    reader.error("POST", path, body, 403, "forbidden", key="same-logical-request")
    u.complete()
    _, docs = f.bill("2028-02-01", "2028-02-01")
    document_totals(docs, [("invoice", 1000)])


@case("interaction-literal-context-segment", 1, "B30", "M1-28 M1-29 M1-30", "R18: a context attribute containing a dot remains one literal attribute name")
def literal_context(c):
    f = c.f
    chart, addresses = f.chart()
    body = {k: copy.deepcopy(chart[k]) for k in ("position_mode", "correction_routing", "accounts", "segments", "lookups", "rules")}
    body.update(key="literal-context", effective_from="2028-01-02")
    body["segments"] = [dict(key="region", values=[dict(key="east", parent_key=None), dict(key="west", parent_key=None)])]
    account = next(a for a in body["accounts"] if a["key"] == addresses["service_revenue"])
    account["required_segments"] = ["region"]
    revenue = next(r for r in body["rules"] if r["function"] == "service_revenue")
    revenue["distribution"][0]["segments"] = {"region": {"field": "customer.attrs.region.name"}}
    config = f.api.create("/accounting-configurations", body)
    f.api.action(f"/accounting-configurations/{identifier(config['id'])}/publish")
    buyer = f.customer(attrs={"region.name": "east"})
    sub, _, _ = f.subscription(buyer, price="1.01", starts="2028-01-02", kind="one_time", recognition="acceptance", activate=False)
    f.api.at("2028-01-31")
    f.evidence(sub, "base", "acceptance", "2028-01-31")
    f.bill()
    c.checkpoint("literal_attribute_drives_required_segment")
    f.recognition("2028-01-31")
    legs = [l for e in f.effects() for l in e["legs"] if l["function"] == "service_revenue"]
    distribution(legs, {(addresses["service_revenue"], (("region", "east"),)): -101}, "literal context address")


@case("interaction-one-time-acceptance-null-window", 1, "B04", "M1-04 M1-08 M1-26", "R16: acceptance delivery has no fabricated service window and earns only on evidence")
def one_time(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price="20", kind="one_time", recognition="acceptance", activate=False)
    f.api.at("2028-01-31")
    _, docs = f.bill()
    document_totals(docs, [("invoice", 2000)])
    c.checkpoint("unperformed_delivery_without_day_window")
    require(docs[0]["items"], "one-time invoice has no items")
    fields(docs[0]["items"][0], {"service_window": None}, "one-time delivery window")
    f.recognition("2028-01-31", allow_missing_evidence=True)
    equal(sum(earned_minor(u) for u in f.units(sub)), 0, "invoicing did not satisfy delivery")
    f.evidence(sub, "base", "acceptance", "2028-01-31")
    f.recognition("2028-01-31")
    equal(sum(earned_minor(u) for u in f.units(sub)), 2000, "accepted delivery recognized once")


@case("interaction-held-run-new-posting-month", 1, "B33", "M1-12 M1-14 M1-32 M1-34",
      "R21: a held run retains its selection and invoice label while retry uses the new posting configuration")
def held_posting(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price="20", kind="one_time", recognition="acceptance", activate=False,
                               trigger=dict(kind="acceptance", date=None))
    f.api.at("2028-02-01")
    f.create("/period-closes", month="2028-01")
    original = f.report("2028-01")
    body = dict(key="pending", customer_ids=[buyer["id"]], target_date="2028-01-31", invoice_date="2028-01-31", posting_date="2028-01-31")
    response = f.api.request("POST", "/bill-runs", body, status=(200, 201))
    run = response["data"]
    # Late-recorded acceptance makes the selected January charge billable.
    f.evidence(sub, "base", "acceptance", "2028-01-31")
    config, addresses = f.chart(effective="2028-02-01", prefix="feb")
    c.checkpoint("retry_replaces_posting_date_not_invoice_date_or_selection")
    f.api.action(f"/bill-runs/{identifier(run['id'])}/retry", dict(mode="generate", posting_date="2028-02-01"))
    f.post_bill(run)
    docs = f.api.all("/documents")
    document_totals(docs, [("invoice", 2000)])
    fields(docs[0], dict(invoice_date="2028-01-31", posting_date="2028-02-01", status="posted"), "retained invoice label and new posting date")
    legs = [l for e in f.effects() if e["kind"] == "billing" for l in e["legs"] if l["function"] == "receivable"]
    distribution(legs, {(addresses["receivable"], ()): 2000}, "new posting configuration")
    closed_unchanged(original, f.report("2028-01"))
