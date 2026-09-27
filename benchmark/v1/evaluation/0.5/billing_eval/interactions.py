"""Executable cross-feature contrasts from CASES.md, using public operations only."""

import copy
from fractions import Fraction

from .checks import earned_minor, closed_unchanged, document_totals, equal, fields, require
from .client import identifier
from .m1 import immutable_document
from .m2 import Usage, measured
from .m3 import discount, order
from .m4 import apply, deal, promise, installment, performance, amend, units, amounts
from .m5 import grant, read_grant
from .m6 import correction
from .oracles import rational
from .suite import case


def pending_order(f, sub, date, actions):
    """Incomplete metering may legitimately hold acceptance until source completion."""
    path = f"/subscriptions/{identifier(sub['id'])}"
    response = f.api.request("POST", path + "/orders", dict(key=f.key("order"), effective_on=date,
                              posting_date=date, actions=actions), status=(200, 201), version=f.api.get(path)["version"])
    require(response["operation"]["status"] in ("held", "completed"), "atomic order status")
    return response


def retry_orders(f):
    for row in f.api.all("/orders"):
        if row["status"] == "held":
            f.api.action(f"/orders/{identifier(row['id'])}/retry")


def versions(u, boundary="2028-01-16"):
    f = u.f
    f.api.at("2028-01-01")
    second = f.create("/tariffs", currency="USD", model="per_unit", bands=[dict(up_to=None, unit_price="2")])
    current = f.api.get(f"/pricing-groups/{identifier(u.group['id'])}")
    body = {k: current[k] for k in ("key", "owner_customer_id", "product_id", "metric_id")}
    body["versions"] = [dict(key="early", window=dict(starts_on=u.window["starts_on"], ends_before=boundary),
                             consumer_ids=[x["id"] for x in u.consumers], tariff_id=u.tariff["id"]),
                        dict(key="late", window=dict(starts_on=boundary, ends_before=u.window["ends_before"]),
                             consumer_ids=[x["id"] for x in u.consumers], tariff_id=second["id"])]
    f.api.request("PUT", f"/pricing-groups/{identifier(current['id'])}", body, status=200, version=current["version"])
    f.api.at("2028-02-01")


def window_allowance(metric, included, expected):
    @case(f"interaction-window-allowance-{metric}-{included}", 2, "B08", "M2-06 M2-07 M2-09 M2-14 M2-15",
          "X07: metric-specific attribution and tariff segments share one window allowance")
    def run(c):
        f = c.f
        f.chart()
        u = Usage(f, aggregation=metric, included=included)
        versions(u)
        for date, n in (("2028-01-10", 2), ("2028-01-20", 3)):
            if metric == "sum":
                u.event(date, str(n), date=date)
            else:
                for i in range(n):
                    interval = dict(starts_at=date + "T10:00:00Z", ends_before=date + "T11:00:00Z") if metric == "peak" else None
                    extra = dict(occurred_at=date + "T10:00:00Z") if interval else None
                    u.event(f"{date}-{i}", None, identity=f"{date}-seat-{i}", date=date, interval=interval, extra=extra)
                # A duplicate observation is not another seat or allowance.
                u.event(date + "-duplicate", None, identity=date + "-seat-0", date=date, interval=interval, extra=extra)
        c.checkpoint("one_allowance_across_two_rating_segments")
        _, docs = u.finish()
        document_totals(docs, [("invoice", expected)])
        equal(measured(u.rows()), 5, "measured across segments")
        equal(sum(rational(r["included"]) for r in u.rows()), rational(included), "single allowance")
        equal(sum(r["net_minor"] for r in u.rows()), expected, "attributed net price")
        equal(sum(earned_minor(r) for r in f.units()), expected, "recognized segmented usage")
    return run


for metric in ("sum", "distinct", "peak"):
    for included, expected in (("0", 800), ("2", 600), ("2.5", 500)):
        window_allowance(metric, included, expected)


def attribution(metric, withdraw_early):
    @case(f"interaction-{metric}-withdraw-{'early' if withdraw_early else 'late'}", 2, "B06",
          "M2-02 M2-06 M2-07 M2-16", "X09: unchanged bucket quantity can acquire a different consumer")
    def run(c):
        f = c.f
        f.chart()
        u = Usage(f, aggregation=metric, count=2, bands=[dict(up_to=None, unit_price="10")])
        events = []
        for side, date in enumerate(("2028-01-10", "2028-01-20")):
            for i in range(1 if metric == "distinct" else 2):
                interval = dict(starts_at=date + "T10:00:00Z", ends_before=date + "T11:00:00Z") if metric == "peak" else None
                event, _ = u.event(f"side-{side}-{i}", None, project=side, identity=f"seat-{i}", date=date,
                                   interval=interval, extra=dict(occurred_at=date + "T10:00:00Z") if interval else None)
                events.append(event)
        u.complete()
        total = 1 if metric == "distinct" else 2
        equal(measured([r for r in u.rows() if r["consumer_id"] == u.consumers[0]["id"]]), total, "initial earliest owner")
        c.checkpoint("withdraw_observation_not_bucket")
        side = 0 if withdraw_early else 1
        # Removing one of the earlier peak seats moves the earliest full peak to B.
        event = next(e for e in events if e["event_key"] == f"side-{side}-0")
        response = f.api.request("POST", f"/sources/{identifier(u.source['id'])}/events",
                                 dict(key="withdraw", event_key=event["event_key"], revision=2, state="withdrawn"),
                                 status=(200, 201))
        f.api.completed(response, "event withdrawal")
        rows = u.rows()
        equal(measured(rows), total, "quantity after withdrawal")
        winner = u.consumers[1 if withdraw_early else 0]["id"]
        equal(sum(r["net_minor"] for r in rows if r["consumer_id"] == winner), total * 1000, "new attributed price")
        _, docs = f.bill("2028-02-01", "2028-02-01")
        document_totals(docs, [("invoice", total * 1000)])
    return run


for metric in ("distinct", "peak"):
    for early in (True, False):
        attribution(metric, early)


@case("interaction-peak-alias-and-tariff-boundary", 2, "B06", "M2-03 M2-07 M2-14", "R04: an interval crossing midnight uses both dated owners")
def peak_alias(c):
    f = c.f
    f.chart()
    u = Usage(f, aggregation="peak", count=2)
    versions(u)
    f.api.at("2028-01-01")
    old = u.assignments[0]
    body = dict(key=old["key"], source_id=u.source["id"], alias="project-0", consumer_id=u.consumers[0]["id"],
                window=dict(starts_on="2028-01-01", ends_before="2028-01-16"))
    f.api.request("PUT", f"/assignments/{identifier(old['id'])}", body, version=old["version"], status=200)
    f.create("/assignments", source_id=u.source["id"], alias="project-0", consumer_id=u.consumers[1]["id"],
             window=dict(starts_on="2028-01-16", ends_before="2028-02-01"))
    f.api.at("2028-02-01")
    u.event("cross-midnight", None, identity="seat", interval=dict(starts_at="2028-01-15T23:00:00Z", ends_before="2028-01-16T01:00:00Z"),
            extra=dict(occurred_at="2028-01-15T23:00:00Z"))
    c.checkpoint("interval_intersects_both_effective_segments")
    u.finish()
    equal({x["id"]: sum(r["net_minor"] for r in u.rows() if r["consumer_id"] == x["id"]) for x in u.consumers},
          {u.consumers[0]["id"]: 100, u.consumers[1]["id"]: 200}, "dated alias/tariff amounts")


@case("interaction-two-feeds-independent-fixed-charge", 2, "B05", "M2-04 M2-18 M2-19", "X10: required missing source holds usage, not independent fixed service")
def two_feeds(c):
    f = c.f
    f.chart()
    u = Usage(f)
    f.api.at("2028-01-01")
    second = f.create("/sources", key="second", name="required empty feed")
    f.create("/sources", key="unrelated", name="not in manifest")
    manifest = f.api.get(f"/source-manifests/{identifier(u.manifest['id'])}")
    body = {k: manifest[k] for k in ("key", "pricing_group_id", "window")}
    body["source_ids"] = [u.source["id"], second["id"]]
    f.api.request("PUT", f"/source-manifests/{identifier(manifest['id'])}", body, version=manifest["version"], status=200)
    equal(f.api.get(f"/source-manifests/{identifier(manifest['id'])}")["key"], manifest["key"],
          "manifest update preserves immutable key")
    f.subscription(u.customers[0], price="7")
    f.api.at("2028-02-01")
    u.event("work", "60")
    u.complete()
    c.checkpoint("partial_billing_keeps_unknown_separate_from_zero")
    response = f.api.request("POST", "/bill-runs", dict(key="run", customer_ids=None, target_date="2028-02-01",
                              invoice_date="2028-02-01", posting_date="2028-02-01"), status=(200, 201))
    equal(response["operation"]["status"], "partial", "fixed service remains independently billable")
    f.api.action(f"/bill-runs/{identifier(response['data']['id'])}/post", dict(result_keys=None), complete=False)
    equal(sum(d["total_minor"] for d in f.api.all("/documents") if d["status"] == "posted"), 700, "only fixed service posted")
    f.api.action(f"/sources/{identifier(second['id'])}/complete", dict(key="empty", manifest_id=manifest["id"], through_before="2028-02-01"), status=(200, 201))
    c.checkpoint("required_empty_feed_resolves_without_unrelated_feed")
    f.bill("2028-02-01", "2028-02-01")
    equal(f.statement(u.customers[0])["ar_minor"], 6700, "one fixed fee plus completed usage")
    f.recognition("2028-01-31", "2028-02-01")
    equal(sum(earned_minor(r) for r in f.units()), 6700, "fixed and metered recognition")


def late_released_revision(changed):
    @case(f"interaction-closed-usage-rebill-{'revised' if changed else 'unchanged'}", 2, "B08",
          "M2-17 M2-20 M2-21", "X11: releasing billing is distinct from correcting a closed service period")
    def run(c):
        f = c.f
        f.chart(separate=True)
        u = Usage(f)
        event, _ = u.event("work", "100")
        u.complete()
        f.recognition("2028-01-31", "2028-02-01")
        f.create("/period-closes", month="2028-01")
        closed = f.report("2028-01")
        _, docs = f.bill("2028-02-01", "2028-02-01")
        c.checkpoint("release_then_reconstruct_service")
        document_totals(docs, [("invoice", 10000)], "linked usage invoice before reversal")
        f.api.action(f"/billing-results/{identifier(docs[0]['result_id'])}/reverse", dict(key="reverse", posting_date="2028-02-01"))
        equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "unfunded_usage"), 10000, "reversal did not reverse service")
        if changed:
            u.event("work", "80", revision=2)
        f.recognition("2028-01-31", "2028-02-01")
        _, rebill = f.bill("2028-02-01", "2028-02-01")
        expected = 8000 if changed else 10000
        document_totals(rebill, [("invoice", expected)])
        equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "unfunded_usage"), expected, "net service after actual revision")
        closed_unchanged(closed, f.report("2028-01"))
        immutable_document(docs[0], f.api.get(f"/documents/{identifier(docs[0]['id'])}"))
    return run


late_released_revision(True)
late_released_revision(False)


def percent_fixed(mode, percentages, expected):
    @case(f"interaction-percent-fixed-{mode}-{'-'.join(percentages)}", 3, "B09", "M3-02 M3-03 M3-04",
          "X12: fixed budget follows capped percentage groups, including zero eligible value")
    def run(c):
        f = c.f
        f.chart()
        buyer = f.customer()
        sub, _, _ = f.subscription(buyer)
        p = discount(f, buyer, kind="percentage", percentages=percentages, mode=mode)
        fixed = discount(f, buyer, budget=1000, priority=2)
        for d in (p, fixed):
            order(f, sub, "2028-01-01", [dict(kind="attach_discount", discount_id=d["id"])])
        f.api.at("2028-02-01")
        c.checkpoint("percentage_then_fixed_budget")
        f.bill("2028-02-01", "2028-02-01")
        f.recognition("2028-01-31", "2028-02-01")
        equal(sum(earned_minor(r) for r in f.units()), expected, "combined discount result")
        equal(f.statement(buyer)["ar_minor"], expected, "discounted invoice")
        before = f.api.all("/documents")
        f.bill("2028-02-01", "2028-02-01")
        equal(f.api.all("/documents"), before, "fixed budget repeated")
    return run


percent_fixed("sequential", ["10", "20"], 6200)
percent_fixed("additive", ["10", "20"], 6000)
percent_fixed("additive", ["70", "50"], 0)


@case("interaction-discount-detachment-service-dates", 3, "B09", "M3-01 M3-06 M3-08 M3-13",
      "R03: a definition is not attachment, and detaching does not spread discount across unqualified days")
def detach(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, starts="2028-04-01", end="2028-05-01")
    d = discount(f, buyer, kind="percentage", percentages=["10"], start="2028-04-01", end="2028-05-01")
    equal(sum(r["net_minor"] for r in f.units(sub, "2028-04-30")), 10000, "definition alone must not discount")
    order(f, sub, "2028-04-01", [dict(kind="attach_discount", discount_id=d["id"])])
    f.api.at("2028-04-16")
    order(f, sub, "2028-04-16", [dict(kind="detach_discount", discount_id=d["id"])])
    c.checkpoint("dated_discount_and_earned_portion")
    f.bill("2028-04-16", "2028-04-16")
    f.recognition("2028-04-15", "2028-04-16")
    equal(f.statement(buyer)["ar_minor"], 9500, "full month price after detachment")
    equal(sum(earned_minor(r) for r in f.units(sub, "2028-04-15")), 4500, "earned discounted days only")


@case("interaction-capped-prorated-discount", 3, "B36", "M2-11 M2-12 M3-02", "X08: amount cap precedes proration and discount, without scaling measured usage")
def capped_discount(c):
    f = c.f
    f.chart()
    u = Usage(f, included="10", maximum=2000, start="2028-01-15", proration="actual_day_amount")
    f.api.at("2028-01-01")
    d = discount(f, u.customers[0], kind="percentage", percentages=["10"])
    pending_order(f, u.subscriptions[0], "2028-01-15", [dict(kind="attach_discount", discount_id=d["id"])])
    f.api.at("2028-02-01")
    u.event("work", "31")
    u.complete()
    retry_orders(f)
    c.checkpoint("rating_cap_proration_discount")
    _, docs = u.finish()
    document_totals(docs, [("invoice", 987)])
    equal(measured(u.rows()), 31, "measured units unchanged")


@case("interaction-shared-discount-incomplete-usage", 3, "B10", "M3-04 M3-05", "X13: a shared discount cannot be spent before all eligible values are known")
def incomplete_discount(c):
    f = c.f
    f.chart()
    u = Usage(f)
    f.api.at("2028-01-01")
    sub, _, _ = f.subscription(u.customers[0], price="150")
    d = discount(f, u.customers[0], budget=4000)
    proposals = [pending_order(f, s, "2028-01-01", [dict(kind="attach_discount", discount_id=d["id"])])
                 for s in (sub, u.subscriptions[0])]
    f.api.at("2028-02-01")
    c.checkpoint("unknown_eligible_input_holds_discount")
    if all(p["operation"]["status"] == "completed" for p in proposals):
        response = f.api.request("POST", "/bill-runs", dict(key="held", customer_ids=None, target_date="2028-02-01",
                                  invoice_date="2028-02-01", posting_date="2028-02-01"), status=(200, 201))
        equal(response["operation"]["status"], "held", "shared scope must hold")
        equal([d for d in f.api.all("/documents") if d["status"] == "posted"], [], "no premature posted discount")
    u.event("work", "50")
    u.complete()
    retry_orders(f)
    c.checkpoint("complete_discount_pool")
    f.bill("2028-02-01", "2028-02-01")
    equal({s["id"]: sum(r["net_minor"] for r in f.units(s)) for s in (sub, u.subscriptions[0])},
          {sub["id"]: 12000, u.subscriptions[0]["id"]: 4000}, "shared 40-dollar budget")
    equal(f.statement(u.customers[0])["ar_minor"], 16000, "completed pool billed once")
