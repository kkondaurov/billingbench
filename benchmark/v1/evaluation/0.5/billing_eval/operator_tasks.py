"""Layout-independent operator tasks with evaluator-owned state assertions.

Navigation selectors are recorded after inspecting the candidate UI. They do not
decide business correctness; final HTTP observations below do.
"""

from .checks import earned_minor, document_totals, equal, fields
from .fixtures import Fixture
from .client import token
from .m1 import immutable_document
from .m2 import Usage
from .m4 import deal, promise, installment
from .m5 import grant, enterprise_history, read_grant


def prepare(base_url, secret, milestone, trace):
    f = Fixture(base_url, secret, f"operator-{milestone}", trace)
    f.chart(capacity=milestone >= 5)
    if milestone == 1:
        buyer = f.customer()
        sub, _, _ = f.subscription(buyer, price="110")
        f.api.at("2028-01-31")
        task = dict(instructions="Find this customer's accepted subscription, generate its January bill run, review the draft invoice and post it. Do not record a payment.",
                    customer=buyer, subscription=sub, target_date="2028-01-31", posting_date="2028-01-31", expected_invoice_minor=11000)
    elif milestone == 2:
        u = Usage(f)
        u.event("usage", "12")
        u.complete()
        _, docs = f.bill("2028-02-01", "2028-02-01")
        task = dict(instructions="Inspect the customer's rated usage, preview and reverse its posted invoice, then generate, review and post the replacement bill run.",
                    customer=u.customers[0], original=docs[0], target_date="2028-02-01", posting_date="2028-02-01", expected_invoice_minor=1200)
    elif milestone == 3:
        buyer = f.customer()
        sub, _, _ = f.subscription(buyer, price="310")
        f.api.at("2028-01-01")
        _, docs = f.bill("2028-01-01", "2028-01-01")
        task = dict(instructions="Cancel this subscription effective January 16. Generate, inspect and post the resulting credit. Leave the original invoice in its historical record.",
                    customer=buyer, subscription=sub, original=docs[0], effective_on="2028-01-16", posting_date="2028-01-16", expected_credit_minor=16000)
    elif milestone == 4:
        buyer, product = f.customer(), f.product()
        d = deal(f, buyer, 115000, [promise("service", product, ssp="920"), promise("delivery", product, "acceptance", "230")],
                 [installment("deposit", "2028-01-01", 50000, "service"), installment("later", "2028-03-01", 65000, "service")])
        task = dict(instructions="Inspect the allocation and billing schedule. Record acceptance of the delivery on January 15 and recognize performance through January 31. Do not change the quoted prices or invoice display amounts.",
                    customer=buyer, deal=d, effective_on="2028-01-15", through="2028-01-31", posting_date="2028-01-31", expected_earned_minor=54000)
    elif milestone == 5:
        u = Usage(f)
        f.api.at("2028-01-01")
        g = grant(f, u.customers[0], u.consumers, u.product, 10000, 8000)
        f.api.at("2028-02-01")
        u.event("work", "80")
        u.complete()
        task = dict(instructions="Inspect the capacity purchase and rated usage. Run recognition through January 31, then process expiry through February 1. Inspect the resulting consumed and expired consideration.",
                    customer=u.customers[0], grant=g, through="2028-01-31", expires_on="2028-02-01", posting_date="2028-02-01")
    else:
        # enterprise_history provisions its own chart, so use a fresh fixture here.
        f = Fixture(base_url, secret, "operator-correction", trace)
        h = enterprise_history(f)
        task = dict(instructions="Inspect the source event for B. Preview and accept a correction changing its quantity from 40 to 10, using the next revision. Review the resulting customer documents and the corrected successor grant. Do not enter accounting amounts yourself.",
                    source=h["pooled"].source, event=h["original_event"], successor=h["g1"],
                    posting_date="2028-03-01", quantity="10", revision=2)
    task.update(milestone=milestone, tenant=f.tenant, base_url=base_url,
                token=token(secret, f.api.tenant, "admin"), business_time=max(f.api.clock, task["posting_date"] + "T12:00:00Z"),
                before_documents=f.api.all("/documents"), before_effects=f.effects())
    return f, task


def verify(f, task):
    stage = task["milestone"]
    original_ids = {d["id"] for d in task["before_documents"]}
    documents = [d for d in f.api.all("/documents") if d["id"] not in original_ids]
    if stage == 1:
        document_totals(documents, [("invoice", 11000)])
        equal(documents[0]["status"], "posted", "operator posted invoice")
        fields(f.statement(task["customer"]), dict(ar_minor=11000, cash_received_minor=0),
               "operator invoice receivable without a payment")
    elif stage == 2:
        document_totals(documents, [("credit", 1200), ("invoice", 1200)])
        equal([d["status"] for d in documents], ["posted"] * len(documents), "operator posted replacement and reversal")
        equal(f.statement(task["customer"])["ar_minor"], 1200, "reversed and rebilled receivable")
        equal(f.api.get(f"/documents/{task['original']['id']}")["reversed"], True, "operator reversal")
    elif stage == 3:
        document_totals(documents, [("credit", 16000)])
        equal(documents[0]["status"], "posted", "operator posted cancellation credit")
        original = f.api.get(f"/documents/{task['original']['id']}")
        immutable_document(task["original"], original)
        equal(original["status"], "posted", "cancellation removed original posted invoice")
        equal(original.get("reversed", False), False, "cancellation reversed original billing")
        equal(f.statement(task["customer"])["ar_minor"], 15000, "remaining receivable for performed service")
    elif stage == 4:
        rows = [r for r in f.units() if r.get("deal_id") == task["deal"]["id"]]
        equal(sum(earned_minor(r) for r in rows), 54000, "operator allocation/performance result")
        equal(sum(e["amount_minor"] for e in f.effects() if e["kind"] == "recognition"), 54000, "actual posted recognition")
    elif stage == 5:
        fields(read_grant(f, task["grant"]), dict(status="expired", basis_recognized_minor=8000), "operator expiry")
        effects = f.effects()
        equal(sum(e["amount_minor"] for e in effects if e["kind"] == "capacity_consumption"), 6400, "operator consumed basis")
        equal(sum(e["amount_minor"] for e in effects if e["kind"] == "capacity_expiry"), 1600, "operator expired basis")
    else:
        fields(read_grant(f, task["successor"]), dict(face_minor=12000, basis_minor=10600), "operator accepted nonlocal correction")
        document_totals(documents, [("credit", 2200), ("debit", 1600)])
