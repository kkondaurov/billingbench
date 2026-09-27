"""Dated terms and discounts exercised through subsequent bill runs."""

from .checks import document_totals, equal, require
from .client import identifier
from .m1 import base, economics, immutable_document
from .suite import case


def order(f, sub, date, actions):
    path = f"/subscriptions/{identifier(sub['id'])}"
    version = f.api.get(path)["version"]
    # This route creates a record while guarding the subscription it changes.
    response = f.api.request("POST", path + "/orders",
                             dict(key=f.key("order"), effective_on=date, actions=actions, posting_date=date),
                             status=(200, 201), version=version)
    f.api.completed(response, path + "/orders")
    return response


def discount(f, buyer, kind="fixed", budget=4000, percentages=None, mode="sequential", priority=1,
             start="2028-01-01", end="2028-02-01", subscriptions=None, partial_window="fixed"):
    return f.create("/discounts", currency="USD", window=dict(starts_on=start, ends_before=end), priority=priority,
                    scope=dict(customer_ids=[buyer["id"]], subscription_ids=subscriptions or [], plan_keys=[], product_ids=[], charge_keys=[]),
                    kind=kind, percentage_group=dict(mode=mode, percentages=percentages) if kind == "percentage" else None,
                    budget_minor=budget if kind == "fixed" else None, partial_window=partial_window)


@case("fixed-budget-redistribution", 3, "B10", "M3-03 M3-04 M3-05 M3-09 M3-10", "One shared budget reallocates to untouched charges after a dated price change")
def fixed_budget(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    a, _, _ = f.subscription(buyer, price="150", starts="2028-04-01", end="2028-05-01", activate=False)
    b, _, _ = f.subscription(buyer, price="50", starts="2028-04-01", end="2028-05-01", activate=False)
    d = discount(f, buyer, start="2028-04-01", end="2028-05-01")
    for sub in (a, b):
        order(f, sub, "2028-04-01", [dict(kind="attach_discount", discount_id=d["id"])])
    f.api.at("2028-04-01")
    f.evidence(a, "base", "activation", "2028-04-01")
    f.evidence(b, "base", "activation", "2028-04-01")
    _, docs = f.bill("2028-04-01", "2028-04-01")
    document_totals(docs, [("invoice", 16000)])
    by_sub = {sub["id"]: sum(i["amount_minor"] for d in docs for i in d["items"] if i["subscription_id"] == sub["id"]) for sub in (a, b)}
    equal(by_sub, {a["id"]: 12000, b["id"]: 4000}, "initial fixed-budget allocation")
    c.checkpoint("dated_price_change_reallocates_budget")
    f.api.at("2028-04-16")
    order(f, a, "2028-04-16", [dict(kind="price", charge_key="base", price="350")])
    _, adjustments = f.bill("2028-04-16", "2028-04-16")
    document_totals(adjustments, [("invoice", 10000)])
    allocated = {sub["id"]: sum(i["amount_minor"] for d in adjustments for i in d["items"] if i["subscription_id"] == sub["id"]) for sub in (a, b)}
    equal(allocated, {a["id"]: 9667, b["id"]: 333}, "nonlocal discount difference")
    f.api.at("2028-04-30")
    f.recognition("2028-04-30")
    economics(f, 21667, 21667, a)
    economics(f, 4333, 4333, b)


def percent_case(key, groups, expected, price="0.05", mode="sequential"):
    @case(key, 3, "B09", "C10 M3-01 M3-02", "Round once per declared discount group, not once per rate")
    def run(c):
        f, buyer, sub, _ = base(c, price=price)
        f.api.at("2028-01-01")
        for i, percentages in enumerate(groups):
            d = discount(f, buyer, kind="percentage", percentages=percentages, priority=i, mode=mode)
            order(f, sub, "2028-01-01", [dict(kind="attach_discount", discount_id=d["id"])])
        c.checkpoint("discount_group_rounding")
        f.api.at("2028-01-31")
        _, docs = f.bill()
        document_totals(docs, [("invoice", expected)])
        f.recognition("2028-01-31")
        economics(f, expected, expected, sub)
    return run


percent_case("two-rates-one-group", [["10", "10"]], 4)
percent_case("two-rates-two-groups", [["10"], ["10"]], 5)
percent_case("additive-percentage-basis", [["10", "20"]], 7000, price="100", mode="additive")
percent_case("sequential-percentage-basis", [["10", "20"]], 7200, price="100")


def partial_budget_case(policy, expected, allocation):
    @case("partial-budget-" + policy, 3, "B10", "M3-03 M3-04 M3-06 M3-09",
          "Overlapping eligible service contributes a union of days, not one duration per charge")
    def run(c):
        f = c.f
        f.chart()
        buyer = f.customer()
        a, _, _ = f.subscription(buyer, price="50", starts="2028-04-01", end="2028-05-01")
        b, _, _ = f.subscription(buyer, price="150", starts="2028-04-01", end="2028-05-01")
        _, original = f.bill("2028-04-01", "2028-04-01")
        document_totals(original, [("invoice", 20000)])
        reduction = discount(f, buyer, start="2028-04-01", end="2028-05-01", partial_window=policy)
        f.api.at("2028-04-16")
        for sub in (a, b):
            order(f, sub, "2028-04-16", [dict(kind="attach_discount", discount_id=reduction["id"])])
        c.checkpoint("one_budget_over_union_of_eligible_days")
        _, adjustments = f.bill("2028-04-16", "2028-04-16")
        document_totals(adjustments, [("credit", expected)])
        amounts = {sub["id"]: sum(i["amount_minor"] for d in adjustments for i in d["items"]
                                  if i["subscription_id"] == sub["id"]) for sub in (a, b)}
        equal(amounts, {a["id"]: allocation[0], b["id"]: allocation[1]}, "partial-window allocation")
        _, repeated = f.bill("2028-04-16", "2028-04-16")
        equal(repeated, [], "repeat run spent the budget again")
        immutable_document(original[0], f.api.get(f"/documents/{identifier(original[0]['id'])}"))
    return run


partial_budget_case("actual_day", 2000, (500, 1500))
partial_budget_case("fixed", 4000, (1000, 3000))


@case("atomic-subscription-order", 3, "B11", "C02 M3-07",
      "An invalid later action cannot leave an earlier price change applied")
def atomic_order(c):
    f = c.f
    f.chart()
    sub, catalog, _ = f.subscription(f.customer(), price="100")
    f.api.at("2028-01-01")
    path = f"/subscriptions/{identifier(sub['id'])}"
    version = f.api.get(path)["version"]
    before = f.effects()
    body = dict(key="atomic-invalid", effective_on="2028-01-01", posting_date="2028-01-01",
                actions=[dict(kind="price", charge_key="base", price="200"),
                         dict(kind="add_plan", plan=dict(catalog_id=catalog['id'], plan_key="standard", overrides={}))])
    c.checkpoint("invalid_later_action_rolls_back_whole_order")
    f.api.error("POST", path + "/orders", body, 422, "invalid_domain", version=version)
    equal(f.api.get(path)["version"], version, "invalid order changed subscription version")
    equal(f.effects(), before, "invalid order changed journals")
    _, original = f.bill()
    document_totals(original, [("invoice", 10000)])
    order(f, sub, "2028-01-01", [dict(kind="price", charge_key="base", price="200")])
    stale = dict(key="stale-price", effective_on="2028-01-01", posting_date="2028-01-01",
                 actions=[dict(kind="price", charge_key="base", price="300")])
    f.api.error("POST", path + "/orders", stale, 409, "stale_version", version=version)
    _, increment = f.bill()
    document_totals(increment, [("invoice", 10000)])


@case("zero-net-amendment-result", 3, "B35", "M3-10 M3-15",
      "Equal opposing component changes survive posting, reversal and regenerated coverage")
def opposing_result(c):
    f = c.f
    f.chart()
    buyer, product = f.customer(), f.product()
    options = dict(model="flat", price="100", quantity="1", included="0", minimum_minor=None,
                   maximum_minor=None, period=dict(months=1, anchor="service_start", day=None),
                   billing="advance", trigger=dict(kind="contract", date=None), recognition="stand_ready")
    charges = [dict(key=key, product_id=product["id"], kind="recurring", options=dict(options),
                    overridable=[], lookup_key=None) for key in ("first", "second")]
    sub, _, _ = f.subscription(buyer, product=product, charges=charges, starts="2028-04-01", end="2028-05-01")
    _, original = f.bill("2028-04-01", "2028-04-01")
    document_totals(original, [("invoice", 20000)])
    f.api.at("2028-04-16")
    order(f, sub, "2028-04-16", [dict(kind="price", charge_key="first", price="200"),
                                  dict(kind="price", charge_key="second", price="0")])
    c.checkpoint("opposing_amounts_are_not_netted_away")
    _, adjustments = f.bill("2028-04-16", "2028-04-16")
    document_totals(adjustments, [("invoice", 5000), ("credit", 5000)])
    equal(len({d["result_id"] for d in adjustments}), 1, "opposing documents need one atomic result")
    for document in adjustments:
        expected_charge = "first" if document["kind"] == "invoice" else "second"
        equal({i["charge_key"] for i in document["items"]}, {expected_charge}, "signed component attribution")
        if document["kind"] == "credit":
            f.unapply_source(document, post="2028-04-16")
    result = adjustments[0]["result_id"]
    f.api.action(f"/billing-results/{identifier(result)}/reverse", dict(key="reverse-pair", posting_date="2028-04-16"))
    _, regenerated = f.bill("2028-04-16", "2028-04-16")
    document_totals(regenerated, [("invoice", 5000), ("credit", 5000)])
    f.api.at("2028-04-30")
    f.recognition("2028-04-30")
    economics(f, 20000, 20000, sub)
    units = f.units(sub)
    equal({charge: sum(u["earned_minor"] for u in units if u["charge_key"] == charge)
           for charge in ("first", "second")}, {"first": 15000, "second": 5000}, "amended component recognition")
    immutable_document(original[0], f.api.get(f"/documents/{identifier(original[0]['id'])}"))


@case("quantity-amendment", 3, "B11", "M3-06 M3-07 M3-13", "A mid-cycle quantity order retains the full-period denominator")
def quantity(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price="10", model="per_unit", quantity="5", starts="2028-04-01", end="2028-05-01", activate=False)
    f.api.at("2028-04-01")
    f.evidence(sub, "base", "activation", "2028-04-01")
    _, docs = f.bill("2028-04-01", "2028-04-01")
    document_totals(docs, [("invoice", 5000)])
    c.checkpoint("partial_cycle_increment")
    f.api.at("2028-04-16")
    order(f, sub, "2028-04-16", [dict(kind="quantity", charge_key="base", quantity="14")])
    _, extra = f.bill("2028-04-16", "2028-04-16")
    document_totals(extra, [("invoice", 4500)])
    f.api.at("2028-04-30")
    f.recognition("2028-04-30")
    economics(f, 9500, 9500, sub)


@case("cancellation-credit-reversal", 3, "B12", "M3-08 M3-11 M3-14 M3-15 M3-16",
      "Reversing a generated negative result does not undo the cancellation")
def cancellation(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price="300", starts="2028-04-01", end="2028-05-01", activate=False)
    f.api.at("2028-04-01")
    f.evidence(sub, "base", "activation", "2028-04-01")
    _, original = f.bill("2028-04-01", "2028-04-01")
    document_totals(original, [("invoice", 30000)])
    receipt = f.receipt(buyer, 30000, post="2028-04-01")
    f.application(receipt, original[0], 30000, post="2028-04-01")
    f.api.at("2028-04-16")
    order(f, sub, "2028-04-16", [dict(kind="cancel")])
    _, credits = f.bill("2028-04-16", "2028-04-16")
    document_totals(credits, [("credit", 15000)])
    c.checkpoint("reverse_negative_coverage_then_rebill")
    result = credits[0]["result_id"]
    f.api.action(f"/billing-results/{identifier(result)}/reverse", dict(key="reverse-credit", posting_date="2028-04-16"))
    _, regenerated = f.bill("2028-04-16", "2028-04-16")
    document_totals(regenerated, [("credit", 15000)])
    f.api.at("2028-04-30")
    f.recognition("2028-04-30")
    economics(f, 15000, 15000, sub)


@case("renewal-catalog-choice", 3, "B12", "M3-12", "Renewal explicitly chooses retained versus newly published pricing")
def renewal(c):
    import copy
    f = c.f
    f.chart()
    buyer = f.customer()
    retained, catalog, _ = f.subscription(buyer, price="30")
    adopted, _, _ = f.subscription(buyer, price="30")
    old = f.api.get(f"/catalogs/{identifier(catalog['id'])}")
    body = {k: copy.deepcopy(old[k]) for k in ("effective_from", "defaults", "plans", "price_lookups")}
    body.update(key="new-price", effective_from="2028-02-01")
    body["plans"][0]["charges"][0]["options"]["price"] = "50"
    new = f.api.create("/catalogs", body)
    f.api.action(f"/catalogs/{identifier(new['id'])}/publish")
    c.checkpoint("explicit_renewal_price_policy")
    order(f, retained, "2028-02-01", [dict(kind="renew", months=1, pricing="retain", catalog_id=None)])
    order(f, adopted, "2028-02-01", [dict(kind="renew", months=1, pricing="catalog", catalog_id=new["id"])])
    f.api.at("2028-02-29")
    _, docs = f.bill("2028-02-29", "2028-02-29")
    document_totals(docs, [("invoice", 14000)])
    for sub, expected in ((retained, 6000), (adopted, 8000)):
        equal(sum(i["amount_minor"] for d in docs for i in d["items"] if i["subscription_id"] == sub["id"]), expected, "renewed price")
