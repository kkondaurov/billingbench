"""Real process and transport boundaries, observed independently of candidate status."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import time

from .checks import document_totals, equal, fields, require
from .client import identifier
from .m1 import base
from .suite import case


@case("cold-first-retry", 1, "I01", "C05", "The first business request after a fresh VM returns the saved result")
def cold_retry(c):
    require(c.runtime is not None, "cold-retry check requires the process runtime")
    f, buyer, sub, _ = base(c)
    body = dict(key="cash", customer_id=buyer["id"], currency="USD", amount_minor=1700, payment_method="bank", posting_date="2028-01-31")
    original = f.api.request("POST", "/receipts", body, status=201, key="cold-retry")
    c.checkpoint("fresh_server_first_business_request")
    c.runtime.restart()
    replay = f.api.request("POST", "/receipts", body, status=201, key="cold-retry")
    equal(replay, original, "fresh-server saved result")
    equal(len(f.api.all("/receipts")), 1, "cold replay created a second receipt")
    equal(f.statement(buyer)["cash_received_minor"], 1700, "cash effect happened once")


@case("competing-cash-applications", 1, "I02", "C06 M1-19", "Concurrent positive applications cannot spend the same available balance twice")
def competing(c):
    f, buyer, sub, _ = base(c, price="200")
    _, docs = f.bill()
    document_totals(docs, [("invoice", 20000)])
    receipt = f.receipt(buyer, 10000)
    invoice = docs[0]
    def attempt(key):
        api = f.api.actor()
        return api.request("POST", "/applications", dict(key=key, source=dict(kind="receipt", id=receipt["id"]),
                           allocations=[dict(document_id=invoice["id"], item_key=invoice["items"][0]["key"], amount_minor=6000)],
                           posting_date="2028-01-31"), status=(200, 201, 409, 422))
    c.checkpoint("concurrent_applications")
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ["application-a", "application-b"]))
    successes = [r for r in results if "error" not in r and r.get("operation", {}).get("status") == "completed"]
    failures = [r for r in results if "operation" not in r and
                r.get("error", {}).get("code") in ("invalid_domain", "prerequisite_failed", "stale_version")]
    equal((len(successes), len(failures)), (1, 1), "one application commits and one rejects")
    fields(f.statement(buyer), dict(ar_minor=14000, available_backed_minor=4000, cash_received_minor=10000), "concurrent conserved balances")
    f.application(receipt, invoice, 4000)
    fields(f.statement(buyer), dict(ar_minor=10000, available_backed_minor=0), "legitimate remainder remains applicable")


def exported_entries_match(f, payload, source_effects):
    data = json.loads(payload)
    equal(data["tenant_key"], f.tenant["key"], "receiver tenant key")
    expected, actual = {}, {}
    configs = {x["id"]: x["key"] for x in f.api.all("/accounting-configurations")}
    for e in source_effects:
        for leg in e["legs"]:
            address = (e["key"], e["scope_key"], e["economic_date"], e["posting_date"],
                       configs[leg["configuration_id"]], leg["account_key"], tuple(sorted(leg["segments"].items())))
            debit, credit = expected.get(address, (0, 0))
            expected[address] = (debit + leg["debit_minor"], credit + leg["credit_minor"])
    for e in data["entries"]:
        for leg in e["lines"]:
            address = (e["effect_key"], e["scope_key"], e["economic_date"], e["posting_date"],
                       leg["configuration_key"], leg["account_key"], tuple(sorted(leg["segments"].items())))
            debit, credit = actual.get(address, (0, 0))
            actual[address] = (debit + leg["debit_minor"], credit + leg["credit_minor"])
    require(expected, "export positive control has no posted effects")
    equal(actual, expected, "export retained constituent effects and actual addresses")


def export_case(key, fault, restart):
    @case(key, 6, "I03" if restart else "I04", "M6-21 M6-22 M6-23", "Receiver acceptance, not queued status, proves delivery; retry preserves payload")
    def run(c):
        require(c.receiver is not None and c.runtime is not None, "export requires real receiver/process runtime")
        f, buyer, sub, _ = base(c)
        f.bill()
        f.recognition("2028-01-31")
        before = (f.api.all("/documents"), f.effects(), f.statement(buyer))
        c.checkpoint("freeze_posted_export")
        export = f.create("/exports", currency="USD", posting_window=dict(starts_on="2028-01-01", ends_before="2028-02-01"))
        equal(hashlib.sha256(export["payload"].encode()).hexdigest(), export["digest"], "payload digest")
        exported_entries_match(f, export["payload"], before[1])
        c.receiver.fault(fault)
        send_key = f.key("send-export")
        sent = f.api.action(f"/exports/{identifier(export['id'])}/send", key=send_key)
        target = json.dumps([f.tenant["key"], export["key"]])
        if fault == "after_accept":
            deadline = time.monotonic() + 30
            while target not in c.receiver.accepted() and time.monotonic() < deadline:
                time.sleep(0.2)
            require(target in c.receiver.accepted(), "worker never reached receiver acceptance")
        if restart:
            c.runtime.restart()
        c.checkpoint("reconcile_actual_receiver")
        deadline = time.monotonic() + 30
        current = None
        while time.monotonic() < deadline:
            response = f.api.action(f"/exports/{identifier(export['id'])}/reconcile", complete=False, status=(200, 409))
            if "error" in response:
                equal(response["error"]["code"], "stale_version", "worker race may only invalidate the version guard")
            current = f.api.get(f"/exports/{identifier(export['id'])}")
            if current["status"] == "acknowledged":
                break
            time.sleep(0.2)
        equal(current["status"], "acknowledged", "export acknowledgement")
        record = c.receiver.accepted().get(target)
        require(record, "candidate acknowledgement without receiver acceptance")
        fields(current, dict(payload=export["payload"], digest=export["digest"], entry_ids=export["entry_ids"],
                             acknowledgement_id=record["acknowledgement_id"]), "immutable export identity")
        replay = f.api.action(f"/exports/{identifier(export['id'])}/send", key=send_key)
        equal(replay, sent, "export send replay changed its saved response")
        equal((f.api.all("/documents"), f.effects(), f.statement(buyer)), before, "export changed economic state")
        empty = f.api.request("POST", "/exports", dict(key="nothing-unbatched", currency="USD",
                               posting_window=dict(starts_on="2028-01-01", ends_before="2028-02-01")), status=200)
        equal(empty["data"], None, "already batched entries exported again")
    return run


export_case("export-lost-response-restart", "after_accept", True)
export_case("export-preaccept-recovery", "before_accept", False)
