"""Small histories built exclusively through candidate-owned public operations."""

import copy
import uuid

from .checks import equal, require, effect_integrity
from .client import API, identifier


class Fixture:
    def __init__(self, base_url, secret, label, trace):
        self.api = API(base_url, secret, role="platform_admin", trace=trace)
        name = label + "-" + uuid.uuid4().hex[:10]
        tenant = self.api.create("/api/tenants", dict(key=name, name=name, defaults={}, grouping="payer"))
        self.api = self.api.actor(tenant=tenant["id"])
        self.tenant = tenant
        self.prefix = name
        self.counter = 0

    def key(self, stem):
        self.counter += 1
        return f"{stem}-{self.counter}"

    def create(self, collection, **body):
        body.setdefault("key", self.key(collection.strip("/").replace("/", "-")))
        return self.api.create(collection, body)

    def customer(self, key="buyer", parent=None, attrs=None):
        return self.create("/customers", key=key, name=key, parent_id=parent, attrs=attrs or {})

    def product(self, key="service", attrs=None):
        return self.create("/products", key=key, name=key, attrs=attrs or {})

    def chart(self, effective="2028-01-01", separate=False, prefix="book", rules=None,
              segments=None, accounts=None, routing="original", capacity=False, **extra):
        functions = {"cash": "asset", "receivable": "asset", "customer_funds": "liability",
                     "service_revenue": "revenue"}
        if capacity:
            functions["capacity_expiry_revenue"] = "revenue"
        functions.update({"contract_asset": "asset", "deferred": "liability"} if separate
                         else {"contract_position": "asset"})
        addresses = {function: prefix + "-" + function for function in functions}
        default_accounts = [dict(key=addresses[k], name=k, **{"class": v}, parent_key=None,
                                 posting=True, starts_on="2020-01-01", ends_before=None,
                                 required_segments=[]) for k, v in functions.items()]
        default_rules = [dict(key="route-" + k, function=k, priority=10, when={"all": []},
                             distribution=[dict(key="whole", weight="100", account={"constant": addresses[k]},
                                                segments={})]) for k in functions]
        body = dict(key=self.key("chart"), effective_from=effective,
                    position_mode="separate" if separate else "clearing", correction_routing=routing,
                    accounts=accounts or default_accounts, segments=segments or [], lookups=[],
                    rules=rules if rules is not None else default_rules, **extra)
        chart = self.api.create("/accounting-configurations", body)
        self.api.action(f"/accounting-configurations/{identifier(chart['id'])}/publish")
        return self.api.get(f"/accounting-configurations/{identifier(chart['id'])}"), addresses

    def subscription(self, customer, product=None, price="100", quantity="1", included="0",
                     starts="2028-01-01", end="2028-02-01", model="flat", kind="recurring",
                     billing="advance", recognition="stand_ready", trigger=None, period=None,
                     options=None, overridable=None, overrides=None, defaults=None, charges=None,
                     activate=True, currency="USD", accept=True):
        product = product or self.product(self.key("service"))
        opt = dict(model=model, price=price, quantity=quantity, included=included,
                   minimum_minor=None, maximum_minor=None,
                   period=period or {"months": 1, "anchor": "service_start", "day": None},
                   billing=billing, trigger=trigger or {"kind": "contract", "date": None}, recognition=recognition)
        if kind == "one_time":
            opt["period"] = None
        opt.update(options or {})
        charges = charges or [dict(key="base", product_id=product["id"], kind=kind, options=opt,
                                   overridable=overridable or [], lookup_key=None)]
        catalog = self.create("/catalogs", effective_from="2028-01-01", defaults=defaults or {},
                              plans=[dict(key="standard", name="Standard", charges=charges)], price_lookups=[])
        self.api.action(f"/catalogs/{identifier(catalog['id'])}/publish")
        body = dict(customer_id=customer["id"], currency=currency, starts_on=starts, ends_before=end,
                    renewal_months=None,
                    plans=[dict(catalog_id=catalog["id"], plan_key="standard", overrides=overrides or {})], attrs={})
        sub = self.create("/subscriptions", **body)
        if accept:
            self.api.action(f"/subscriptions/{identifier(sub['id'])}/accept")
        if activate and accept:
            for c in charges:
                if c["options"].get("recognition") == "stand_ready":
                    self.evidence(sub, c["key"], "activation", starts)
        return sub, catalog, product

    def evidence(self, sub, charge, kind, date, period_start=None):
        if self.api.clock[:10] < date:
            self.api.at(date)
        body = dict(key=self.key("evidence"), charge_key=charge, kind=kind, effective_on=date)
        if period_start:
            body["period_starts_on"] = period_start
        return self.api.create(f"/subscriptions/{identifier(sub['id'])}/evidence", body)

    def forecast(self, sub, through):
        value = self.api.get(f"/subscriptions/{identifier(sub['id'])}/forecast?through={through}")
        # The public contract defines rows, but does not prescribe their outer wrapper.
        if isinstance(value, dict):
            for name in ("rows", "units", "charges", "breakdown"):
                if isinstance(value.get(name), list):
                    return value[name]
        require(isinstance(value, list), "forecast must expose its breakdown rows")
        return value

    def units(self, sub=None, through=None):
        # The contract leaves the default read horizon unspecified.
        query = {"through": through if through is not None else self.api.clock[:10]}
        if sub:
            query["subscription_id"] = sub["id"]
        return self.api.all("/revenue-units", **query)

    def bill_scopes(self, run):
        # The contract puts scopes on billing results; a run may link those results.
        require(isinstance(run, dict), "bill run must expose its result records")
        if "scopes" in run:
            results = [run]
        else:
            result_ids = run.get("result_ids")
            if result_ids is None and isinstance(run.get("result_id"), str):
                result_ids = [run["result_id"]]
            if result_ids is None and isinstance(run.get("results"), list):
                result_ids = run["results"]
            require(isinstance(result_ids, list), "bill run missing scopes or result links")
            require(all(isinstance(value, str) and value for value in result_ids),
                    "bill run result links must be nonempty strings")
            results = [self.api.get(f"/billing-results/{identifier(result_id)}")
                       for result_id in result_ids]
        scopes = []
        for result in results:
            require(isinstance(result, dict) and isinstance(result.get("scopes"), list),
                    "billing result missing scope records")
            for scope in result["scopes"]:
                require(isinstance(scope, dict) and isinstance(scope.get("document_ids"), list),
                        "billing scope missing document links")
                scopes.append(scope)
        return scopes

    def bill(self, target="2028-01-31", post="2028-01-31", customers=None, posted=True):
        body = dict(key=self.key("bill"), customer_ids=customers, target_date=target,
                    invoice_date=target, posting_date=post)
        previous = {d["id"] for d in self.api.all("/documents")}
        run = self.api.create("/bill-runs", body)
        generated = self.api.all("/documents")
        require(all(d["status"] == "draft" for d in generated
                    if d["id"] not in previous and d["total_minor"] != 0),
                "generation posted a nonzero document before posting")
        if posted:
            self.post_bill(run)
        docs = self.api.all("/documents")
        result = self.api.get(f"/bill-runs/{identifier(run['id'])}")
        result = {**result, "scopes": self.bill_scopes(result)}
        ids = {d for s in result["scopes"] for d in s["document_ids"]}
        return result, [d for d in docs if d["id"] in ids]

    def post_bill(self, run):
        response = self.api.action(f"/bill-runs/{identifier(run['id'])}/post",
                                   {"result_keys": None}, complete=False, status=(200, 409))
        if "error" in response:
            equal(response["error"]["code"], "already_final", "bill post rejection")
            current = self.api.get(f"/bill-runs/{identifier(run['id'])}")
            equal(current.get("status"), "posted", "already-final run is not posted")
            scopes = self.bill_scopes(current)
            require(all(s.get("status") in ("posted", "covered", "not_due") for s in scopes),
                    "already-final run contains unfinished work")
            for scope in scopes:
                for doc_id in scope["document_ids"]:
                    document = self.api.get(f"/documents/{identifier(doc_id)}")
                    equal(document["status"], "posted", "already-final run retains a draft")
        else:
            self.api.completed(response, "bill post")
        return response

    def recognition(self, through, posting=None, allow_missing_evidence=False):
        body = dict(key=self.key("recognition-runs"), through=through, posting_date=posting or through)
        response = self.api.request("POST", "/recognition-runs", body, status=201)
        if allow_missing_evidence and response.get("operation", {}).get("status") in ("held", "partial"):
            issues = response["operation"].get("issues")
            require(isinstance(issues, list) and issues and all(i.get("code") == "missing_evidence" for i in issues),
                    "recognition held for an unexpected reason")
        else:
            self.api.completed(response, "recognition")
        return self.api.resource(response, "recognition")

    def statement(self, customer, currency="USD"):
        data = self.api.get(f"/customers/{identifier(customer['id'])}/statement")
        return currency_statement(data, currency)

    def receipt(self, customer, amount, post="2028-01-31"):
        return self.create("/receipts", customer_id=customer["id"], currency="USD",
                           amount_minor=amount, payment_method="bank", posting_date=post)

    def application(self, source, doc, amount, kind="receipt", post="2028-01-31", item=None):
        allocations = []
        if item is not None or amount <= doc['items'][0]['amount_minor']:
            allocations = [dict(document_id=doc['id'], item_key=item or doc['items'][0]['key'],
                                amount_minor=amount)]
        else:
            # Whole-document settlement must not overapply its first display item.
            remaining = amount
            for row in doc['items']:
                take = min(remaining, row['amount_minor'])
                if take:
                    allocations.append(dict(document_id=doc['id'], item_key=row['key'], amount_minor=take))
                    remaining -= take
            require(remaining == 0, 'fixture payment exceeds document consideration')
        return self.create("/applications", source=dict(kind=kind, id=source["id"]),
                           allocations=allocations, posting_date=post)

    def memo(self, customer, doc, amount, kind="credit", post="2028-01-31", item=None):
        memo = self.create("/memos", kind=kind, customer_id=customer["id"], currency="USD",
                           invoice_date=post, posting_date=post,
                           items=[dict(key="adjustment", document_id=doc["id"],
                                       item_key=item or doc["items"][0]["key"], amount_minor=amount,
                                       reason="Commercial price correction")])
        doc_id = memo.get("document_id", memo["id"])
        require(isinstance(doc_id, str) and doc_id, "memo missing valid document identity")
        self.api.action(f"/documents/{identifier(doc_id)}/post", dict(posting_date=post))
        return self.api.get(f"/documents/{identifier(doc_id)}")

    def unapply_source(self, source, kind="credit", post="2028-01-31"):
        applications = [a for a in self.api.all("/applications")
                        if a["source"].get("kind") == kind and a["source"].get("id") == source["id"]]
        for application in applications:
            allocations = [dict(document_id=a["document_id"], item_key=a["item_key"], amount_minor=a["unappliable_minor"])
                           for a in application["allocations"] if a["unappliable_minor"] > 0]
            if allocations:
                self.api.action(f"/applications/{identifier(application['id'])}/unapply",
                                 dict(allocations=allocations, posting_date=post))

    def report(self, month, view="as_posted", currency="USD"):
        data = self.api.get(f"/accounting-reports?month={month}&view={view}")
        return report_content(currency_report(data, currency))

    def effects(self):
        rows = self.api.all("/effects")
        effect_integrity(rows)
        return rows


def currency_statement(data, currency="USD"):
    fields = ("ar_minor", "available_backed_minor", "available_restricted_minor",
              "cash_received_minor", "cash_refunded_minor")
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict) and r.get("currency") == currency]
        equal(len(rows), 1, "statement currency rows")
        row = rows[0]
    elif isinstance(data, dict):
        # No posted documents or funds means no populated currency balance yet.
        empty_funds = data.get("funds") == [] or (data.get("receipts") == [] and data.get("refunds") == [])
        if (data.get("documents") == [] and empty_funds
                and any(data.get(name) == [] or data.get(name) == {} for name in ("balances", "currencies"))):
            return {k: 0 for k in (*fields, 'refundable_cash_minor')}
        if data.get("currency") == currency:
            row = data
        elif isinstance(data.get(currency), dict):
            row = data[currency]
        elif isinstance(data.get("currencies"), (dict, list)):
            return currency_statement(data["currencies"], currency)
        elif isinstance(data.get("balances"), (dict, list)):
            return currency_statement(data["balances"], currency)
        else:
            require(all(isinstance(data.get(k), dict) and currency in data[k] for k in fields),
                    "statement must expose per-currency amounts")
            row = {k: data[k][currency] for k in fields}
            if 'refundable_cash_minor' in data:
                require(isinstance(data['refundable_cash_minor'], dict) and currency in data['refundable_cash_minor'],
                        'statement missing refundable cash currency')
                row['refundable_cash_minor'] = data['refundable_cash_minor'][currency]
    else:
        require(False, "statement must expose per-currency amounts")
    require(all(type(row.get(k)) is int for k in fields), "statement missing integer currency amounts")
    if 'refundable_cash_minor' in row:
        require(type(row['refundable_cash_minor']) is int, 'refundable cash must be integer')
    return row


def currency_report(data, currency="USD", shared=None):
    shared = dict(shared or {})
    if isinstance(data, dict):
        # Report-wide metadata may be outside the currency rows. Never invent it.
        for field in ("closed", "unresolved"):
            if field in data:
                shared[field] = data[field]
    if isinstance(data, dict) and "accounts" in data:
        report = data
    elif isinstance(data, dict) and isinstance(data.get(currency), dict):
        return currency_report(data[currency], currency, shared)
    elif isinstance(data, dict) and "currencies" in data:
        return currency_report(data["currencies"], currency, shared)
    elif data == {} and type(shared.get('closed')) is bool and isinstance(shared.get('unresolved'), list):
        return dict(shared, accounts=[], rollups=[], units=[])
    elif isinstance(data, list):
        require(all(isinstance(r, dict) for r in data), "accounting report currency rows must be objects")
        matches = [r for r in data if r.get("currency") == currency]
        if not data and type(shared.get('closed')) is bool and isinstance(shared.get('unresolved'), list):
            return dict(shared, accounts=[], rollups=[], units=[])
        equal(len(matches), 1, "accounting report currency")
        report = matches[0]
    else:
        require(False, "accounting report missing currency data")
    report = {**shared, **report}
    for field in ("accounts", "rollups", "units", "unresolved"):
        require(isinstance(report.get(field), list), f"accounting report missing {field}")
    require(type(report.get("closed")) is bool, "accounting report missing closed status")
    for row in report["accounts"] + report["rollups"]:
        equal(row["debit_minor"] - row["credit_minor"], row["net_debit_minor"], "report movements")
        equal(row["opening_net_debit_minor"] + row["net_debit_minor"], row["closing_net_debit_minor"], "report closing balance")
    for row in report["units"]:
        position = row["billed_minor"] - row["earned_minor"]
        equal(row["position_minor"], position, "reported scope position")
        equal((row["asset_minor"], row["deferred_minor"]), (max(-position, 0), max(position, 0)), "reported asset/deferred")
    return report


def report_content(report):
    account_fields = ("account_key", "segments", "debit_minor", "credit_minor", "net_debit_minor",
                      "opening_net_debit_minor", "closing_net_debit_minor")
    unit_fields = ("scope_key", "billed_minor", "earned_minor", "position_minor", "asset_minor", "deferred_minor")
    result = dict(closed=report["closed"], unresolved=copy.deepcopy(report["unresolved"]))
    for name in ("accounts", "rollups"):
        rows = [{key: copy.deepcopy(row[key]) for key in account_fields} for row in report[name]]
        result[name] = sorted(rows, key=lambda row: (row["account_key"], sorted(row["segments"].items())))
    result["units"] = sorted(({key: row[key] for key in unit_fields} for row in report["units"]), key=lambda row: row["scope_key"])
    return result
