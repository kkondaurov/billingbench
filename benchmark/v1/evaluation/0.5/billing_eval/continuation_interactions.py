"""Close controls for saved work, fractional amounts and reused funding rights."""

import copy
from fractions import Fraction
import json
import time

from .checks import earned_minor, equal, fields, require, document_totals, distribution, closed_unchanged
from .client import identifier
from .m1 import immutable_document
from .m2 import Usage, proposal_version
from .m4 import deal, promise, installment, performance, units, amend, apply
from .m5 import grant, read_grant
from .m6 import correction
from .funding_interactions import replace_rights, late_first_fact
from .integrity import exported_entries_match
from .oracles import rational
from .suite import case


@case("interaction-saved-partial-competing-sweep", 1, "B33", "M1-10 M1-12 M1-13 M1-14 M1-15",
      "X05: a saved partial selection survives competing coverage without sweeping a newcomer")
def saved_sweep(c):
    f = c.f
    f.chart()
    a, b = f.customer("a"), f.customer("b")
    f.subscription(a)
    sub, _, _ = f.subscription(b, price="60", trigger=dict(kind="activation", date=None), activate=False)
    f.api.at("2028-01-31")
    r = f.api.request("POST", "/bill-runs", dict(key="saved", customer_ids=None, target_date="2028-01-31",
                      invoice_date="2028-01-31", posting_date="2028-01-31"), status=(200, 201))["data"]
    newcomer = f.customer("c")
    f.subscription(newcomer, price="40")
    # Release the first draft explicitly; live reservations need not be stolen.
    for document in f.api.all("/documents"):
        if document["customer_id"] == a["id"] and document["status"] == "draft":
            f.api.action(f"/documents/{identifier(document['id'])}/cancel")
    f.bill(customers=[a["id"]])
    c.checkpoint("competitor_then_resolve_saved_work")
    response = f.api.action(f"/bill-runs/{identifier(r['id'])}/post", dict(result_keys=None), complete=False)
    require(response["operation"]["status"] in ("completed", "partial", "held"), "invalid saved run state")
    document_totals([d for d in f.api.all("/documents") if d["status"] == "posted"], [("invoice", 10000)])
    f.evidence(sub, "base", "activation", "2028-01-20")
    f.api.action(f"/bill-runs/{identifier(r['id'])}/retry", dict(mode="generate"))
    f.post_bill(r)
    document_totals([d for d in f.api.all("/documents") if d["status"] == "posted"], [("invoice", 10000), ("invoice", 6000)])
    equal(f.statement(newcomer)["ar_minor"], 0, "saved selection swept the new customer")
    f.bill()
    equal(sum(f.statement(buyer)["ar_minor"] for buyer in (a, b, newcomer)), 20000, "exact combined debt")
    equal(len([d for d in f.api.all("/documents") if d["status"] == "posted"]), 3, "one invoice per selected debtor")


@case("interaction-partial-period-performance", 1, "B04", "M1-07 M1-09 M1-26",
      "R02: price uses full month but performance uses the contracted partial period")
def partial_performance(c):
    f = c.f
    f.chart()
    sub, _, _ = f.subscription(f.customer(), starts="2028-04-16", end="2028-05-01",
                              period=dict(months=1, anchor="day", day=1))
    f.api.at("2028-04-30")
    _, docs = f.bill("2028-04-30", "2028-04-30")
    document_totals(docs, [("invoice", 5000)])
    c.checkpoint("partial_period_is_not_prorated_twice")
    for through, earned in (("2028-04-20", 1667), ("2028-04-30", 5000)):
        f.recognition(through, "2028-04-30")
        equal(sum(earned_minor(u) for u in f.units(sub, through=through)), earned, "partial performance target")


def fractional_usage(prorated):
    @case(f"interaction-fractional-usage-prorated-{int(prorated)}", 2, "B36", "M2-10 M2-12 M2-15",
          "R05: round after amount proration, not before it")
    def run(c):
        f = c.f
        f.chart()
        u = Usage(f, bands=[dict(up_to=None, unit_price="0.005")], start="2028-04-16",
                  window=dict(starts_on="2028-04-01", ends_before="2028-05-01"),
                  proration="actual_day_amount" if prorated else "none")
        u.event("half-cent", "1", date="2028-04-20")
        u.complete()
        c.checkpoint("exact_fraction_before_final_rounding")
        f.bill("2028-05-01", "2028-05-01")
        rows = u.rows()
        equal(sum(rational(r["rated_exact_minor"]) for r in rows), Fraction(1, 2), "bounded amount before proration")
        equal(sum(r["prorated_minor"] for r in rows), 0 if prorated else 1, "round only after proration")
        equal(sum(r["net_minor"] for r in rows), 0 if prorated else 1, "final rounded cents")
    return run


fractional_usage(True)
fractional_usage(False)


def display_case(reverse, split):
    @case(f"interaction-allocation-display-{int(reverse)}-split-{int(split)}", 4, "B15", "C10 M4-03 M4-04 M4-05",
          "X17/R25: business keys own residual cents regardless of display and insertion order")
    def run(c):
        f = c.f
        f.chart()
        buyer, p = f.customer(), f.product()
        ps = [promise(k, p, "acceptance", "1") for k in (["b", "a"] if reverse else ["a", "b"])]
        total = 2 if split else 101
        payments = [installment("first", "2028-01-01", 1, "b"), installment("second", "2028-01-02", 1, "b")] if split else [installment("only", "2028-01-01", 101, "b" if reverse else "a")]
        d = deal(f, buyer, total, ps, payments)
        f.bill("2028-01-01", "2028-01-01")
        if split:
            equal({u["promise_key"]: u["billed_minor"] for u in units(f, d)}, {"a": 1, "b": 0}, "first cumulative cent")
        f.api.at("2028-01-02")
        f.bill("2028-01-02", "2028-01-02")
        docs = copy.deepcopy(f.api.all("/documents"))
        c.checkpoint("perform_all_promises_without_false_positions")
        for key in ("a", "b"):
            performance(f, d, key, "acceptance", "2028-01-02")
        f.recognition("2028-01-02", "2028-01-02")
        expected = {"a": 1, "b": 1} if split else {"a": 51, "b": 50}
        rows = units(f, d, "2028-01-02")
        equal(sorted(u["promise_key"] for u in rows), sorted(expected), "complete allocated promise population")
        for u in rows:
            fields(u, dict(billed_minor=expected[u["promise_key"]], earned_minor=expected[u["promise_key"]],
                           position_minor=0), "fully performed promise")
        reported = f.report("2028-01")["units"]
        equal(sorted(u["scope_key"] for u in reported), sorted(u["scope_key"] for u in rows),
              "report retains all allocated promises")
        for u in reported:
            fields(u, dict(asset_minor=0, deferred_minor=0), "no false reporting positions")
        equal(f.api.all("/documents"), docs, "recognition rewrote invoice display")
    return run


for reverse in (False, True):
    for split in (False, True):
        display_case(reverse, split)


def termination_case(retained):
    @case(f"interaction-concession-termination-retained-{retained}", 4, "B24", "M4-15 M4-17 M4-18 M4-19",
          "X22: billing sign depends on retained price versus assigned net billing")
    def run(c):
        f = c.f
        f.chart()
        buyer, p = f.customer(), f.product()
        d = deal(f, buyer, 115000, [promise("service", p, ssp="920"), promise("delivery", p, "acceptance", "230")],
                 [installment("deposit", "2028-01-01", 50000, "service"), installment("later", "2028-03-01", 65000, "service")])
        f.api.at("2028-01-31")
        performance(f, d, "delivery", "acceptance", "2028-01-15")
        f.bill()
        f.recognition("2028-01-31")
        f.api.at("2028-02-01")
        a = amend(f, d, "2028-02-01", dict(amount_minor=23000, scope="full_sale"), kind="concession")
        apply(f, a, "2028-02-01")
        f.bill("2028-02-01", "2028-02-01")
        before = {x["id"] for x in f.api.all("/documents")}
        c.checkpoint("derive_zero_or_negative_final_billing")
        t = f.api.action(f"/deals/{identifier(d['id'])}/terminations", dict(key="stop", scope_key=d["scope_keys"]["groups"]["group"],
                         effective_on="2028-02-01", retained_price_minor=retained, termination_fee=None), status=(200, 201))["data"]
        f.api.action(f"/terminations/{identifier(t['id'])}/apply", dict(posting_date="2028-02-01"))
        f.bill("2028-02-01", "2028-02-01")
        document_totals([x for x in f.api.all("/documents") if x["id"] not in before], [] if retained == 27000 else [("credit", 7000)])
        equal(sum(earned_minor(u) for u in units(f, d)), retained, "terminated consideration")
        equal(f.statement(buyer)["ar_minor"], retained, "unpaid retained debt")
    return run


termination_case(27000)
termination_case(20000)


@case("interaction-grant-reverse-source-rebill", 5, "B35", "M5-05 M5-09 M5-10 M5-19 M2-17",
      "X29/R19: paid purchase coverage gates source revision without recreating the grant")
def grant_reuse(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000, end="2028-03-01")
    f.api.at("2028-02-01")
    u.event("work", "20")
    u.complete()
    _, docs = f.bill("2028-02-01", "2028-02-01")
    document_totals(docs, [("invoice", 8000)])
    f.recognition("2028-01-31", "2028-02-01")
    fields(read_grant(f, g), dict(face_remaining_minor=8000, basis_recognized_minor=1600), "original funded service")
    c.checkpoint("release_real_affected_purchase_then_retry")
    effects = f.effects()
    _, proposed = u.event("work", "30", revision=2, status=200)
    equal(proposed["operation"]["status"], "held", "active purchase coverage must hold ordinary revision")
    equal(f.effects(), effects, "held revision changed journals")
    f.api.action(f"/billing-results/{identifier(docs[0]['result_id'])}/reverse", dict(key="release", posting_date="2028-02-01"))
    equal(read_grant(f, g)["basis_recognized_minor"], 1600, "reversal does not undo recognized service")
    path = f"/sources/{identifier(u.source['id'])}/events"
    version = proposal_version(f.api.all(path, event_key="work"), 2)
    f.api.action(path+"/work/proposals/2/retry", version=version)
    f.recognition("2028-01-31", "2028-02-01")
    fields(read_grant(f, g), dict(face_remaining_minor=7000, basis_recognized_minor=2400), "revised funded service")
    _, reissued = f.bill("2028-02-01", "2028-02-01")
    document_totals(reissued, [("invoice", 8000)])
    equal(len(f.api.all("/grants")), 1, "rebilling issued a second grant")
    fields(read_grant(f, g), dict(face_remaining_minor=7000, basis_recognized_minor=2400), "rebilling did not consume twice")


@case("interaction-grant-customer-redaction", 5, "B29", "C12 M5-05 M5-21",
      "R26: customer can see its rights without allocated or recognized accounting basis")
def grant_redaction(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000, end="2028-03-01")
    f.api.at("2028-02-01")
    u.complete()
    c.checkpoint("commercial_rights_without_internal_basis")
    internal = read_grant(f, g)
    equal(internal["basis_minor"], 8000, "internal basis positive control")
    reader = f.api.actor("customer", u.customers[0]["id"])
    own = reader.get(f"/grants/{identifier(g['id'])}")
    fields(own, dict(face_minor=10000, face_remaining_minor=10000), "customer rights")
    forbidden = {"basis_minor", "basis_recognized_minor", "basis_unearned_minor", "allocated_minor", "earned_minor"}
    def inspect(value):
        if isinstance(value, dict):
            require(not (set(value) & forbidden), "customer grant exposes internal basis")
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    inspect(own)
    other = f.customer("stranger")
    f.api.actor("customer", other["id"]).error("GET", f"/grants/{identifier(g['id'])}", None, 404, "not_found")


@case("interaction-freed-capacity-displaces-later-overage", 6, "B25", "M6-03 M6-05 M6-14",
      "X34: correcting earlier consumption must fund later service before calculating expiry")
def freed_rights(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    f.api.at("2028-01-01")
    g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000, end="2028-03-01")
    f.api.at("2028-02-01")
    event, _ = u.event("early", "80", date="2028-01-10")
    u.event("later", "40", date="2028-01-20")
    u.complete()
    u.finish()
    before = {d["id"] for d in f.api.all("/documents")}
    c.checkpoint("newly_available_rights_refund_later_overage")
    f.api.at("2028-02-02")
    correction(f, {}, dict(kind="source", source_id=u.source["id"], event=dict(event, key="less", revision=2, quantity="60")), date="2028-02-02")
    fields(read_grant(f, g), dict(face_remaining_minor=0, basis_recognized_minor=8000), "freed face consumed by later service")
    equal(sum(r["overage_minor"] for r in u.rows()), 0, "later overage displaced")
    document_totals([d for d in f.api.all("/documents") if d["id"] not in before], [("credit", 2000)])
    f.api.at("2028-03-01")
    f.recognition("2028-02-29", "2028-03-01")
    f.create("/grant-expirations", through="2028-03-01", posting_date="2028-03-01")
    equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "capacity_expiry"), 0, "already consumed freed rights expired again")


@case("interaction-carried-basis-fraction-and-expiry", 6, "B17", "M5-10 M5-11 M5-16 M5-17 M5-18",
      "X28: a nontrivial successor ratio releases 43.68 on consumption and 75.12 on expiry")
def carried_ratio(c):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    sold = f.product("capacity-sale")
    f.api.at("2028-01-01")
    g0 = grant(f, u.customers[0], u.consumers, u.product, 15000, 12000, end="2028-03-01", sale_product=sold)
    f.api.at("2028-02-01")
    u.event("old", "114")
    u.complete()
    u.finish()
    g1 = replace_rights(f, g0, u.consumers, u.product, sold, "next", "2028-02-01", "2028-04-01", 10000, 9000)
    fields(read_grant(f, g1), dict(face_minor=13600, basis_minor=11880), "derived successor")
    later = Usage(f, customers=u.customers, consumers=u.consumers, product=u.product, group_key="next-month",
                  window=dict(starts_on="2028-02-01", ends_before="2028-03-01"))
    late_first_fact(later, "later", "50", "2028-02-15", "2028-03-01")
    c.checkpoint("nontrivial_basis_ratio_then_new_not_old_expiry")
    f.recognition("2028-02-29", "2028-03-01")
    fields(read_grant(f, g1), dict(face_remaining_minor=8600, basis_recognized_minor=4368, basis_unearned_minor=7512), "partial successor consumption")
    f.create("/grant-expirations", through="2028-03-01", posting_date="2028-03-01")
    equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "capacity_expiry"), 0, "old grant expiry releases nothing")
    f.api.at("2028-04-01")
    f.recognition("2028-03-31", "2028-04-01")
    f.create("/grant-expirations", through="2028-04-01", posting_date="2028-04-01")
    equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "capacity_expiry"), 7512, "successor expiry releases remaining basis")
    fields(read_grant(f, g1), dict(status="expired", basis_recognized_minor=11880, basis_unearned_minor=0), "all successor basis accounted")


@case("interaction-lost-export-then-correction", 6, "I03", "M6-16 M6-18 M6-21 M6-22 M6-23",
      "X37: a later correction belongs in a new batch while an accepted old batch is recovered")
def export_correction(c):
    require(c.runtime is not None and c.receiver is not None, "requires real process and receiver")
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer)
    f.api.at("2028-02-01")
    f.bill()
    f.recognition("2028-01-31")
    original = copy.deepcopy(f.effects())
    export = f.create("/exports", currency="USD", posting_window=dict(starts_on="2028-01-01", ends_before="2028-03-01"))
    exported_entries_match(f, export["payload"], original)
    c.receiver.fault("after_accept")
    f.api.action(f"/exports/{identifier(export['id'])}/send")
    target = json.dumps([f.tenant["key"], export["key"]])
    deadline = time.monotonic()+30
    while target not in c.receiver.accepted() and time.monotonic() < deadline:
        time.sleep(.2)
    require(target in c.receiver.accepted(), "first export did not reach receiver")
    f.chart(effective="2028-02-01", prefix="new")
    correction(f, {}, dict(kind="recorded_term", resource=dict(kind="subscription", id=sub["id"]),
                           path=["charges", "base", "price"], replacement="80"), date="2028-02-02")
    effects = copy.deepcopy(f.effects())
    c.checkpoint("recover_old_payload_and_export_only_new_corrections")
    c.runtime.restart()
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        f.api.action(f"/exports/{identifier(export['id'])}/reconcile", complete=False, status=(200, 409))
        current = f.api.get(f"/exports/{identifier(export['id'])}")
        if current["status"] == "acknowledged":
            break
        time.sleep(.2)
    fields(current, dict(status="acknowledged", payload=export["payload"], digest=export["digest"], entry_ids=export["entry_ids"]), "old frozen export")
    second = f.create("/exports", currency="USD", posting_window=dict(starts_on="2028-01-01", ends_before="2028-03-01"))
    ids = {e["id"] for e in original}
    exported_entries_match(f, second["payload"], [e for e in effects if e["id"] not in ids])
    require(not set(export["entry_ids"]) & set(second["entry_ids"]), "batches duplicate source entries")
    equal(f.effects(), effects, "export changed economic history")


@case("interaction-held-correction-new-month", 6, "B26", "M6-01 M6-02 M6-19 M6-24",
      "R21: retry the same held correction in an open month with a fresh preview")
def held_correction(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer)
    f.api.at("2028-02-01")
    f.bill()
    f.recognition("2028-01-31")
    f.create("/period-closes", month="2028-01")
    before = (f.api.all("/documents"), f.effects(), f.report("2028-01"))
    body = dict(key="same-correction", reason="Recorded price", posting_date="2028-01-31",
                change=dict(kind="recorded_term", resource=dict(kind="subscription", id=sub["id"]),
                            path=["charges", "base", "price"], replacement="80"))
    preview = f.api.preview("/correction-previews", body)
    require(preview["issues"], "closed date accepted")
    held = f.api.request("POST", "/corrections", dict(body, basis_token=preview["basis_token"]), status=200)
    equal(held["operation"]["status"], "held", "closed correction must hold")
    equal((f.api.all("/documents"), f.effects(), f.report("2028-01")), before, "held correction partly posted")
    c.checkpoint("retry_same_change_with_open_posting_date")
    preview = f.api.preview("/correction-previews", dict(body, posting_date="2028-02-01"))
    equal(preview["issues"], [], "open-date correction is valid")
    f.api.action(f"/corrections/{identifier(held['data']['id'])}/retry", dict(basis_token=preview["basis_token"], posting_date="2028-02-01"))
    ids = {d["id"] for d in before[0]}
    document_totals([d for d in f.api.all("/documents") if d["id"] not in ids], [("credit", 2000)])
    equal(len(f.api.all("/corrections")), 1, "retry invented another correction")
    equal(f.statement(buyer)["ar_minor"], 8000, "corrected debt")
    closed_unchanged(before[2], f.report("2028-01"))


@case("interaction-defaults-do-not-hybridize-usage", 2, "B01", "M1-01 M1-02 M2-01 M2-10",
      "R17: flat defaults do not leak price or model into metered pricing")
def usage_defaults(c):
    f = c.f
    f.api.request("PUT", "/settings", dict(defaults=dict(model="flat", price="100", quantity="1"), grouping="payer"),
                  status=200, version=f.tenant["version"])
    f.chart()
    u = Usage(f, bands=[dict(up_to=None, unit_price="2")])
    u.event("three", "3")
    c.checkpoint("metered_options_replace_inapplicable_default_fields")
    _, docs = u.finish()
    document_totals(docs, [("invoice", 600)])
    equal(sum(r["net_minor"] for r in u.rows()), 600, "usage did not inherit flat price")
    options = dict(metric_id=u.metric["id"], pricing_group_id=u.group["id"], consumer_ids=[x["id"] for x in u.consumers],
                   period=dict(months=1, anchor="day", day=1), billing="arrears", minimum_minor=None,
                   maximum_minor=None, usage_proration="none", trigger=dict(kind="contract", date=None), price="100")
    f.api.error("POST", "/catalogs", dict(key="malformed", effective_from="2028-01-01", defaults={}, price_lookups=[],
                plans=[dict(key="bad", name="Bad", charges=[dict(key="bad", product_id=u.product["id"], kind="usage",
                  options=options, overridable=[], lookup_key=None)])]), 400, "invalid_request")


@case("interaction-scheduled-capacity-incomplete-boundary", 5, "B18", "M5-16 M5-17 M5-18 M5-20",
      "R06: scheduled replacement waits for old input without demanding nonexistent successor draws")
def delayed_rights(c, pre_recognize=True):
    f = c.f
    f.chart(capacity=True)
    u = Usage(f)
    sold = f.product("capacity-sale")
    f.api.at("2028-01-01")
    g0 = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000, end="2028-03-01", sale_product=sold)
    f.api.at("2028-01-10")
    terms = dict(key="successor", owner_customer_id=u.customers[0]["id"], currency="USD", priority=1,
                 window=dict(starts_on="2028-01-16", ends_before="2028-03-01"),
                 consumer_ids=[x["id"] for x in u.consumers], product_ids=[u.product["id"]])
    a = f.api.action(f"/deals/{identifier(g0['deal_id'])}/amendments", dict(key="scheduled", scope_key=g0["scope_key"],
                     effective_on="2028-01-16", kind="modify", commercial=dict(carry="all_remaining", price_delta_minor=1000,
                     new_face_minor=2000, replacement_promise=dict(key="new", product_id=sold["id"], ssp="1", attrs={}),
                     replacement_grant=terms), billing=dict(future_installments=None)), status=(200, 201), complete=False)["data"]
    f.api.action(f"/amendments/{identifier(a['id'])}/apply", dict(posting_date="2028-01-10"), complete=False, status=(200, 422))
    equal(len(f.api.all("/grants")), 1, "future agreement created early rights")
    f.api.at("2028-01-16")
    r = f.api.action(f"/amendments/{identifier(a['id'])}/apply", dict(posting_date="2028-01-16"), complete=False)
    equal(r["operation"]["status"], "held", "missing boundary funding must hold")
    equal(len(f.api.all("/grants")), 1, "held agreement partially replaced rights")
    f.api.at("2028-02-01")
    u.event("early", "30", date="2028-01-10")
    u.event("later", "20", date="2028-01-20")
    u.complete()
    if not pre_recognize:
        c.checkpoint("prior_recognition_is_a_required_prerequisite")
        before = (f.effects(), f.api.all("/grants"))
        response = f.api.action(f"/amendments/{identifier(a['id'])}/apply", dict(posting_date="2028-02-01"), complete=False)
        equal(response["operation"]["status"], "held", "apply skipped required prior recognition")
        require(response["operation"]["issues"], "missing recognition issue")
        equal((f.effects(), f.api.all("/grants")), before, "held agreement changed rights or journals")
        return
    if pre_recognize:
        c.checkpoint("recognize_completed_pre_boundary_inputs")
        f.recognition("2028-01-15", "2028-02-01")
    c.checkpoint("complete_input_then_apply_at_retained_boundary")
    apply(f, a, "2028-02-01")
    successor = next(g for g in f.api.all("/grants") if g["id"] != g0["id"])
    fields(successor, dict(face_minor=9000, basis_minor=6600), "70 carried face plus 20 new; 56 carried basis plus 10 new")
    f.recognition("2028-01-31", "2028-02-01")
    fields(read_grant(f, successor), dict(face_remaining_minor=7000, basis_recognized_minor=1467), "post-boundary draw at new ratio")
    equal(read_grant(f, g0)["basis_recognized_minor"], 2400, "old earnings preserved")
    before = f.effects()
    response = f.api.action(f"/amendments/{identifier(a['id'])}/apply", dict(posting_date="2028-02-01"), status=(200, 409), complete=False)
    if "error" in response:
        equal(response["error"]["code"], "already_final", "only an already-final rejection is valid")
    equal(f.effects(), before, "repeat apply duplicated transfer")


@case("interaction-scheduled-capacity-needs-prior-recognition", 5, "B18", "M5-16 M5-17 M5-18 M5-20",
      "R06 control: complete source input does not replace the required prior recognition")
def delayed_rights_direct(c):
    delayed_rights(c, pre_recognize=False)


@case("interaction-correction-other-tenant-isolation", 6, "B29", "C01 C12 M6-03 M6-24",
      "X38: same business keys in another tenant do not join a correction's dependencies")
def correction_isolation(c):
    from .fixtures import Fixture
    from .funding_interactions import pooled_fixture
    f = c.f
    other = Fixture(f.api.base_url, f.api.secret, "same-keys-other-tenant", f.api.trace)
    isolated = pooled_fixture(other, reduction=False, funding=False, unrelated=True)
    before = (other.api.all("/documents"), other.effects(), isolated["u"].rows())
    h = pooled_fixture(f, reduction=False, funding=False, unrelated=True)
    old = f.statement(h["other"])
    c.checkpoint("nonlocal_dependencies_stop_at_tenant_and_group")
    correction(f, {}, dict(kind="source", source_id=h["u"].source["id"],
                           event=dict(h["event"], key="revised", revision=2, quantity="10")), date="2028-02-01")
    equal((other.api.all("/documents"), other.effects(), isolated["u"].rows()), before, "other tenant changed")
    equal(f.statement(h["other"]), old, "unrelated customer changed")
    reader = f.api.actor("customer", h["a"]["id"])
    reader.get(f"/customers/{identifier(h['a']['id'])}/statement")
    reader.error("GET", f"/customers/{identifier(h['b']['id'])}/statement", None, 404, "not_found")


@case("interaction-split-posting-hold-recovery-close", 1, "B30", "M1-28 M1-29 M1-30 M1-32 M1-34",
      "X06: one unresolved distribution leg holds the whole effect until a valid configuration is available")
def split_hold(c):
    f = c.f
    original, addresses = f.chart()
    body = {k: copy.deepcopy(original[k]) for k in ("position_mode", "correction_routing", "accounts", "segments", "lookups", "rules")}
    body.update(key="split-missing", effective_from="2028-01-02")
    revenue = next(r for r in body["rules"] if r["function"] == "service_revenue")
    revenue["distribution"] = [dict(key="east", weight="60", account={"constant": addresses["service_revenue"]}, segments={}),
                               dict(key="west", weight="40", account={"field": "customer.attrs.west_account"}, segments={})]
    missing = f.api.create("/accounting-configurations", body)
    f.api.action(f"/accounting-configurations/{identifier(missing['id'])}/publish")
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price="1.01", starts="2028-01-02", kind="one_time", recognition="acceptance", activate=False)
    f.api.at("2028-01-31")
    f.evidence(sub, "base", "acceptance", "2028-01-31")
    f.bill()
    before = f.effects()
    held = f.api.request("POST", "/recognition-runs", dict(key="held", through="2028-01-31", posting_date="2028-01-31"), status=200)
    equal(held["operation"]["status"], "held", "one missing split leg")
    equal(f.effects(), before, "valid split leg posted alone")
    f.api.at("2028-02-01")
    closed = f.api.request("POST", "/period-closes", dict(key="blocked-close", month="2028-01"), status=200)
    equal(closed["operation"]["status"], "held", "unresolved recognition must block close")
    c.checkpoint("valid_distribution_recovers_whole_effect")
    f.api.at("2028-02-01")
    body = copy.deepcopy(body)
    body.update(key="split-fixed", effective_from="2028-02-01")
    west = copy.deepcopy(next(a for a in body["accounts"] if a["key"] == addresses["service_revenue"]))
    west["key"] = "west-revenue"
    body["accounts"].append(west)
    revenue = next(r for r in body["rules"] if r["function"] == "service_revenue")
    revenue["distribution"][1]["account"] = {"constant": "west-revenue"}
    fixed = f.api.create("/accounting-configurations", body)
    f.api.action(f"/accounting-configurations/{identifier(fixed['id'])}/publish")
    f.recognition("2028-01-31", "2028-02-01")
    legs = [l for e in f.effects() if e["kind"] == "recognition" for l in e["legs"]]
    distribution(legs, {(addresses["contract_position"], ()): 101,
                       (addresses["service_revenue"], ()): -61, ("west-revenue", ()): -40}, "complete rounded distribution")
    f.create("/period-closes", month="2028-01")
    retained = f.report("2028-01")
    f.chart(effective="2028-03-01", prefix="future")
    closed_unchanged(retained, f.report("2028-01"))
