"""Metering contrasts: actual sources, completion, nonlinear pricing and coverage."""

from fractions import Fraction

from .checks import earned_minor, document_totals, equal, fields, require
from .client import identifier
from .oracles import charge, rational
from .suite import case


class Usage:
    def __init__(self, f, model="per_unit", bands=None, aggregation="sum", count=1,
                 included="0", minimum=None, maximum=None, proration="none",
                 start=None, customers=None, product=None, owner=None, group_key="pool", window=None, existing=None,
                 consumers=None):
        self.f, self.api = f, f.api
        self.window = window or dict(starts_on="2028-01-01", ends_before="2028-02-01")
        start = start or self.window["starts_on"]
        self.customers = customers or [f.customer()]
        self.product = product or f.product(f.key("metered-product"))
        self.consumers = consumers or [f.create("/consumers", key=f"{group_key}-project-{i}", customer_id=self.customers[i % len(self.customers)]["id"],
                                   name=f"Project {i}", attrs={}) for i in range(count)]
        self.source = f.create("/sources", key=f"{group_key}-feed", name="Measured events")
        self.metric = f.create("/metrics", key=f"{group_key}-meter", event_type="request", filters={"billable": "yes"}, aggregation=aggregation)
        self.bands = bands or [dict(up_to=None, unit_price="1")]
        self.tariff = f.create("/tariffs", key=f"{group_key}-rates", currency="USD", model=model, bands=self.bands)
        self.group = f.create("/pricing-groups", key=group_key, owner_customer_id=(owner or self.customers[0])["id"],
                              product_id=self.product["id"], metric_id=self.metric["id"],
                              versions=[dict(key="initial", window=self.window, consumer_ids=[x["id"] for x in self.consumers],
                                             tariff_id=self.tariff["id"])])
        self.assignments = [f.create("/assignments", key=f"{group_key}-alias-{i}", source_id=self.source["id"], alias=f"project-{i}",
                                     consumer_id=x["id"], window=self.window) for i, x in enumerate(self.consumers)]
        self.manifest = f.create("/source-manifests", pricing_group_id=self.group["id"], window=self.window, source_ids=[self.source["id"]])
        self.allowance = None
        if rational(included):
            self.allowance = f.create("/allowances", pricing_group_id=self.group["id"], window=self.window,
                                      units=included, mode="fixed", active_windows=[self.window])
        self.subscriptions = []
        for buyer in self.customers:
            members = [x["id"] for x in self.consumers if x["customer_id"] == buyer["id"]]
            options = dict(metric_id=self.metric["id"], pricing_group_id=self.group["id"], consumer_ids=members,
                           period=dict(months=1, anchor="day", day=1), billing="arrears", minimum_minor=minimum,
                           maximum_minor=maximum, usage_proration=proration, trigger=dict(kind="contract", date=None))
            charges = [dict(key="usage", product_id=self.product["id"], kind="usage", options=options, overridable=[], lookup_key=None)]
            if existing:
                catalog = f.create("/catalogs", effective_from="2028-01-01", defaults={}, price_lookups=[],
                                    plans=[dict(key=group_key, name="Metered addition", charges=charges)])
                self.api.action(f"/catalogs/{identifier(catalog['id'])}/publish")
                self.addition = self.api.action(f"/subscriptions/{identifier(existing['id'])}/orders",
                    dict(key=f.key('addition'), effective_on=start, posting_date=start, actions=[dict(kind='add_plan',
                    plan=dict(catalog_id=catalog['id'], plan_key=group_key, overrides={}))]),
                    complete=False, status=(200, 201))
                require(self.addition['operation']['status'] in ('completed', 'held'), 'metering plan addition outcome')
                sub = existing
            else:
                sub, _, _ = f.subscription(buyer, product=self.product, charges=charges, starts=start, end=self.window["ends_before"],
                                           activate=False)
            self.subscriptions.append(sub)
        self.api.at(self.window["ends_before"])

    def event(self, key, quantity="1", project=0, revision=1, date="2028-01-20", identity=None,
              interval=None, event_type="request", dimensions=None, status=(200, 201), extra=None):
        body = dict(key=self.f.key("ingest"), event_key=key, revision=revision, state="active", event_type=event_type,
                    alias=f"project-{project}", occurred_at=date + "T12:00:00Z", quantity=quantity,
                    identity=identity, interval=interval, dimensions={"billable": "yes"} if dimensions is None else dimensions)
        body.update(extra or {})
        response = self.api.request("POST", f"/sources/{identifier(self.source['id'])}/events", body, status=status)
        if status in (201, (200, 201)):
            self.api.completed(response, "source event")
        return body, response

    def complete(self):
        identity = (self.source['id'], self.manifest['id'], self.window['ends_before'])
        if getattr(self, '_completed_boundary', None) != identity:
            response = self.api.action(f"/sources/{identifier(self.source['id'])}/complete",
                                      dict(key=self.f.key("complete"), manifest_id=self.manifest["id"],
                                           through_before=self.window["ends_before"]), status=(200, 201))
            self._completed_boundary, self._completion_response = identity, response
        return self._completion_response

    def rows(self):
        return self.api.all("/rated-charges", group_id=self.group["id"], through=self.api.clock[:10])

    def finish(self):
        self.complete()
        result, docs = self.f.bill("2028-02-01", "2028-02-01")
        self.f.recognition("2028-01-31", "2028-02-01")
        return result, docs


def measured(rows):
    return sum((rational(r["measured"]) for r in rows), Fraction(0))


def tariff_case(name, model, q, included="0", maximum=None, minimum=None, proration="none", start="2028-01-01"):
    @case(name, 2, "B36" if "proration" in name else "B07", "M2-08 M2-10 M2-11 M2-12 M2-15", "Price the whole bucket once; do not prorate source units")
    def run(c):
        f = c.f
        f.chart()
        bands = [dict(up_to="10", unit_price="2"), dict(up_to="30", unit_price="1.25"), dict(up_to=None, unit_price="0.75")]
        if model == "per_unit":
            bands = [dict(up_to=None, unit_price="1")]
        u = Usage(f, model=model, bands=bands, included=included, maximum=maximum,
                  minimum=minimum, proration=proration, start=start)
        if rational(q):
            u.event("measured", q)
        ratio = Fraction(17, 31) if proration == "actual_day_amount" else Fraction(1)
        expected = charge(q, bands, model, included, minimum, maximum, ratio)
        c.checkpoint("complete_rate_post_recognize")
        _, docs = u.finish()
        equal(sum(d["total_minor"] for d in docs), expected, "billed rated consideration")
        rows = u.rows()
        require(rows, "complete meter has no rated rows")
        equal(measured(rows), rational(q), "unscaled measured quantity")
        equal(sum(rational(r["included"]) for r in rows), min(rational(q), rational(included)), "one shared allowance")
        equal(sum(r["net_minor"] for r in rows), expected, "rated monetary target")
        equal(sum(earned_minor(r) for r in f.units()), expected, "metered earned amount")
        saved = f.api.all("/documents")
        f.bill("2028-02-01", "2028-02-01")
        equal(f.api.all("/documents"), saved, "repeated usage billing")
    return run


for model in ("graduated", "volume"):
    for q in ("9.999999", "10", "10.000001", "30", "37"):
        tariff_case(f"{model}-{q.replace('.', '_')}", model, q)
tariff_case("usage-cap-and-proration", "per_unit", "31", "10", maximum=2000, proration="actual_day_amount", start="2028-01-15")
tariff_case("usage-cap-without-proration", "per_unit", "31", "10", maximum=2000, start="2028-01-15")
tariff_case("complete-zero-minimum", "per_unit", "0", minimum=700)


@case("source-revisions", 2, "B05", "M2-02 M2-04 M2-05 M2-16 M2-17", "Revisions replace current facts and completion does not hide changed input")
def revisions(c):
    f = c.f
    f.chart()
    u = Usage(f)
    u.event("identity", "12", revision=2)
    u.event("excluded-type", "500", event_type="other")
    u.event("excluded-dimension", "500", dimensions={"billable": "no"})
    body, _ = u.event("identity", "7", revision=3)
    path = f"/sources/{identifier(u.source['id'])}/events"
    c.checkpoint("revision_identity")
    response = f.api.request("POST", path, dict(body, key="new-record-key"), status=(200, 201))
    f.api.completed(response, "source revision replay")
    f.api.error("POST", path, dict(body, key="conflict", quantity="8"), 409, "revision_conflict")
    f.api.error("POST", path, dict(body, key="older", revision=1), 409, "stale_revision")
    u.complete()
    _, docs = f.bill("2028-02-01", "2028-02-01")
    document_totals(docs, [("invoice", 700)])
    c.checkpoint("billed_revision_is_held")
    before = (f.effects(), f.statement(u.customers[0]))
    _, proposed = u.event("identity", "4", revision=4, status=200)
    equal(proposed["operation"]["status"], "held", "active coverage must hold source change")
    require(any(i["code"] == "active_billing" for i in proposed["operation"]["issues"]), "missing active billing issue")
    # A held rating may expose null prices; accepted billing and journals must stay fixed.
    equal(sum(r["billed_minor"] for r in u.rows()), 700, "held revision changed accepted coverage")
    equal((f.effects(), f.statement(u.customers[0])), before, "held revision changed accepted economics")
    result_path = f"/billing-results/{identifier(docs[0]['result_id'])}"
    f.api.action(result_path + "/reverse", dict(key="release", posting_date="2028-02-01"))
    # The proposal route is an action on an event revision, not on a guessed DB record.
    retry_path = path + "/identity/proposals/4/retry"
    proposals = f.api.all(path, event_key="identity")
    f.api.action(retry_path, version=proposal_version(proposals, 4))
    _, rebill = f.bill("2028-02-01", "2028-02-01")
    document_totals(rebill, [("invoice", 400)])


def proposal_version(rows, revision):
    versions = []
    for row in rows:
        if row.get("revision") == revision:
            versions.append(row.get("version"))
        for proposal in row.get("proposals", []):
            if proposal.get("revision") == revision:
                versions.append(proposal.get("version", row.get("version")))
    equal(len(versions), 1, "readable source proposal count")
    require(type(versions[0]) is int and versions[0] >= 1, "source proposal missing version")
    return versions[0]


@case("distinct-attribution", 2, "B06", "M2-03 M2-06 M2-08 M2-13 M2-15", "Distinct identities follow earliest retained observation, not per-consumer counts")
def distinct(c):
    f = c.f
    f.chart()
    u = Usage(f, aggregation="distinct", count=2)
    u.event("later-duplicate", None, project=1, identity="seat-a", date="2028-01-21")
    u.event("earlier", None, project=0, identity="seat-a", date="2028-01-20")
    u.event("second", None, project=1, identity="seat-b", date="2028-01-22")
    c.checkpoint("distinct_bucket_and_owners")
    _, docs = u.finish()
    document_totals(docs, [("invoice", 200)])
    rows = u.rows()
    equal(measured(rows), 2, "distinct union")
    for consumer in u.consumers:
        own = [r for r in rows if r["consumer_id"] == consumer["id"]]
        equal(measured(own), 1, "earliest observation attribution")


@case("peak-half-open-union", 2, "B06", "C09 M2-07 M2-15", "Peak counts unique occupied seats, not event rows or adjacent endpoints")
def peak(c):
    f = c.f
    f.chart()
    u = Usage(f, aggregation="peak", count=2)
    intervals = [("a", "2028-01-20T10:00:00Z", "2028-01-20T11:00:00Z", 0),
                 ("a", "2028-01-20T10:30:00Z", "2028-01-20T11:30:00Z", 0),
                 ("b", "2028-01-20T10:45:00Z", "2028-01-20T11:00:00Z", 1),
                 ("c", "2028-01-20T11:00:00Z", "2028-01-20T12:00:00Z", 1)]
    for i, (seat, start, end, owner) in enumerate(intervals):
        u.event(f"session-{i}", None, project=owner, identity=seat, interval=dict(starts_at=start, ends_before=end),
                extra={"occurred_at": start})
    c.checkpoint("peak_and_earliest_ownership")
    _, docs = u.finish()
    document_totals(docs, [("invoice", 200)])
    equal(measured(u.rows()), 2, "peak union")
    for consumer in u.consumers:
        equal(measured([r for r in u.rows() if r["consumer_id"] == consumer["id"]]), 1, "peak consumer attribution")


@case("missing-feed-recovery", 2, "B05", "C06 C08 M2-04 M2-18 M2-19", "Missing completion holds a scope; a certified empty feed permits real billing")
def missing_feed(c):
    f = c.f
    f.chart()
    u = Usage(f, minimum=500)
    c.checkpoint("incomplete_feed_holds")
    body = dict(key="incomplete", customer_ids=None, target_date="2028-02-01", invoice_date="2028-02-01", posting_date="2028-02-01")
    response = f.api.request("POST", "/bill-runs", body, status=200)
    require(response["operation"]["status"] in ("held", "partial"), "incomplete source was silently zero")
    equal(sum(d["total_minor"] for d in f.api.all("/documents") if d["status"] == "posted"), 0, "held scope billed")
    run = response["data"]
    u.complete()
    c.checkpoint("complete_empty_feed_recovery")
    f.api.action(f"/bill-runs/{identifier(run['id'])}/retry", dict(mode="generate"))
    f.api.action(f"/bill-runs/{identifier(run['id'])}/post", {"result_keys": None})
    document_totals(f.api.all("/documents"), [("invoice", 500)])
    equal(measured(u.rows()), 0, "empty feed fabricated usage")


@case("metered-addition-old-debt", 2, "B08", "M2-01 M2-20 M2-21", "Metering extends an existing subscription without recreating its old sale or debt")
def addition(c):
    from .m1 import immutable_document
    f = c.f
    f.chart()
    buyer = f.customer()
    old, _, _ = f.subscription(buyer, price="30", end="2028-03-01")
    _, old_docs = f.bill("2028-01-01", "2028-01-01")
    document_totals(old_docs, [("invoice", 3000)])
    u = Usage(f, customers=[buyer], window=dict(starts_on="2028-02-01", ends_before="2028-03-01"), existing=old)
    u.event("new-work", "8", date="2028-02-15")
    u.complete()
    c.checkpoint("old_subscription_new_metered_charge")
    _, docs = f.bill("2028-03-01", "2028-03-01")
    document_totals(docs, [("invoice", 3800)])
    f.recognition("2028-02-29", "2028-03-01")
    equal(sum(earned_minor(r) for r in f.units(old)), 6800, "both old service and new usage earned")
    immutable_document(old_docs[0], f.api.get(f"/documents/{identifier(old_docs[0]['id'])}"))
    c.checkpoint("usage_memo_retains_source_and_coverage")
    usage_item = next(i for i in docs[0]["items"] if i["charge_key"] == "usage")
    credit = f.memo(buyer, docs[0], 200, post="2028-03-01", item=usage_item["key"])
    f.unapply_source(credit, post="2028-03-01")
    f.api.action(f"/documents/{identifier(credit['id'])}/compensate", dict(key="undo-credit", posting_date="2028-03-01"))
    f.api.action(f"/billing-results/{identifier(docs[0]['result_id'])}/reverse", dict(key="reverse", posting_date="2028-03-01"))
    _, rebill = f.bill("2028-03-01", "2028-03-01")
    document_totals(rebill, [("invoice", 3800)])
    equal(measured(u.rows()), 8, "reversal erased usage")
    equal(sum(earned_minor(r) for r in f.units(old)), 6800, "rebilling duplicated or reversed service")


@case("tariff-boundary-window-allowance", 2, "B08", "M2-09 M2-14", "Tariff segments reset bands but do not reset a window-wide allowance")
def segments(c):
    f = c.f
    f.chart()
    u = Usage(f, included="10")
    f.api.at("2028-01-01")
    second = f.create("/tariffs", currency="USD", model="per_unit", bands=[dict(up_to=None, unit_price="2")])
    group = f.api.get(f"/pricing-groups/{identifier(u.group['id'])}")
    body = {k: group[k] for k in ("key", "owner_customer_id", "product_id", "metric_id")}
    body["versions"] = [dict(key="early", window=dict(starts_on="2028-01-01", ends_before="2028-01-16"),
                             consumer_ids=[x["id"] for x in u.consumers], tariff_id=u.tariff["id"]),
                        dict(key="late", window=dict(starts_on="2028-01-16", ends_before="2028-02-01"),
                             consumer_ids=[x["id"] for x in u.consumers], tariff_id=second["id"])]
    f.api.request("PUT", f"/pricing-groups/{identifier(group['id'])}", body, status=200, version=group["version"])
    f.api.at("2028-02-01")
    u.event("early", "6", date="2028-01-10")
    u.event("late", "9", date="2028-01-20")
    c.checkpoint("window_allowance_survives_boundary")
    _, docs = u.finish()
    document_totals(docs, [("invoice", 1000)])
    rows = u.rows()
    equal(sum(rational(r["included"]) for r in rows), 10, "allowance reset at tariff boundary")
    equal(sum(rational(r["billable"]) for r in rows), 5, "remaining billable units")


@case("fractional-active-day-allowance", 2, "B07", "M2-08 M2-12 M2-14", "Allowance proration retains a rational quantity independently of monetary proration")
def fractional_allowance(c):
    f = c.f
    f.chart()
    u = Usage(f)
    f.api.at("2028-01-01")
    f.create("/allowances", pricing_group_id=u.group["id"], window=u.window, units="1.1", mode="actual_day",
             active_windows=[dict(starts_on="2028-01-17", ends_before="2028-02-01")])
    f.api.at("2028-02-01")
    u.event("one-unit", "1")
    c.checkpoint("exact_quantity_before_money_rounding")
    _, docs = u.finish()
    document_totals(docs, [("invoice", 47)])
    rows = u.rows()
    equal(sum(rational(r["included"]) for r in rows), Fraction(33, 62), "fractional included allowance")
    equal(sum(rational(r["billable"]) for r in rows), Fraction(29, 62), "fractional remaining units")


@case("one-event-two-product-coverage", 2, "B08", "M2-13 M2-18 M2-21", "Billing one registered product does not mark the source event globally billed")
def product_coverage(c):
    f = c.f
    f.chart()
    u = Usage(f)
    f.api.at("2028-01-01")
    product = f.product("second-product")
    tariff = f.create("/tariffs", currency="USD", model="per_unit", bands=[dict(up_to=None, unit_price="2")])
    group = f.create("/pricing-groups", owner_customer_id=u.customers[0]["id"], product_id=product["id"], metric_id=u.metric["id"],
                     versions=[dict(key="second", window=u.window, consumer_ids=[u.consumers[0]["id"]], tariff_id=tariff["id"])])
    manifest = f.create("/source-manifests", pricing_group_id=group["id"], window=u.window, source_ids=[u.source["id"]])
    opts = dict(metric_id=u.metric["id"], pricing_group_id=group["id"], consumer_ids=[u.consumers[0]["id"]],
                period=dict(months=1, anchor="day", day=1), billing="arrears", minimum_minor=None, maximum_minor=None,
                usage_proration="none", trigger=dict(kind="date", date="2028-02-02"))
    second, _, _ = f.subscription(u.customers[0], product=product, activate=False,
                                  charges=[dict(key="other-usage", product_id=product["id"], kind="usage", options=opts, overridable=[], lookup_key=None)])
    f.api.at("2028-02-01")
    u.event("shared-fact", "12")
    u.complete()
    f.api.action(f"/sources/{identifier(u.source['id'])}/complete", dict(key="second-complete", manifest_id=manifest["id"], through_before="2028-02-01"), status=(200, 201))
    c.checkpoint("first_product_bills_alone")
    _, docs = f.bill("2028-02-01", "2028-02-01")
    document_totals(docs, [("invoice", 1200)])
    f.api.at("2028-02-02")
    c.checkpoint("second_product_bills_same_source_fact")
    _, docs = f.bill("2028-02-02", "2028-02-02")
    document_totals(docs, [("invoice", 2400)])
    equal({i["subscription_id"] for d in docs for i in d["items"]}, {second["id"]}, "second registered charge attribution")
    equal(f.statement(u.customers[0])["ar_minor"], 3600, "both product receivables")
    f.recognition("2028-01-31", "2028-02-02")
    equal(sum(earned_minor(r) for r in f.units()), 3600, "independent product earnings")


def licensed_tariff(model):
    @case("licensed-" + model + "-included-boundary", 2, "B07", "M1-04 M2-10", "Licensed tiers extend existing options and price after included quantity")
    def run(c):
        f = c.f
        f.chart()
        buyer, product = f.customer(), f.product()
        tariff = f.create("/tariffs", currency="USD", model=model,
                         bands=[dict(up_to="10", unit_price="2"), dict(up_to=None, unit_price="1")])
        options = dict(model=model, tariff_id=tariff["id"], quantity="14", included="4", minimum_minor=None, maximum_minor=None,
                       period=dict(months=1, anchor="service_start", day=None), billing="advance",
                       trigger=dict(kind="contract", date=None), recognition="stand_ready")
        sub, _, _ = f.subscription(buyer, product=product, charges=[dict(key="seats", product_id=product["id"], kind="recurring",
                                   options=options, overridable=[], lookup_key=None)])
        f.api.at("2028-01-31")
        c.checkpoint("licensed_tier_not_metered_usage")
        _, docs = f.bill()
        expected = 2000 if model == "graduated" else 1000
        document_totals(docs, [("invoice", expected)])
        f.recognition("2028-01-31")
        equal(sum(earned_minor(r) for r in f.units(sub)), expected, "licensed tier revenue")
    return run


licensed_tariff("graduated")
licensed_tariff("volume")
