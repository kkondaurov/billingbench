"""Shared assertions used by live observations and targeted altered-output controls."""
from collections import defaultdict


class Mismatch(AssertionError):
    pass


def equal(actual, expected, label):
    if actual != expected:
        raise Mismatch(f"{label}: expected {expected!r}, observed {actual!r}")


def require(condition, label):
    if not condition:
        raise Mismatch(label)


def fields(actual, expected, label):
    require(isinstance(actual, dict), f"{label}: expected object")
    for key, value in expected.items():
        require(key in actual, f"{label}: missing {key}")
        equal(actual[key], value, f"{label}.{key}")


def integer_fields(actual, names, label):
    require(isinstance(actual, dict), f"{label}: expected object")
    for name in names:
        require(name in actual, f"{label}: missing required field {name}")
        require(type(actual[name]) is int, f"{label}.{name}: expected integer, observed {actual[name]!r}")


def report_journal_movements(accounts, entries, month, currency='USD'):
    reported = {}
    for row in accounts:
        integer_fields(row, ('debit_minor', 'credit_minor', 'net_debit_minor',
                            'opening_net_debit_minor', 'closing_net_debit_minor'), 'report account')
        require(row['debit_minor'] >= 0 and row['credit_minor'] >= 0, 'negative report movement')
        equal(row['debit_minor'] - row['credit_minor'], row['net_debit_minor'], 'report movement net')
        equal(row['opening_net_debit_minor'] + row['net_debit_minor'],
              row['closing_net_debit_minor'], 'report opening plus movement')
        key = (row['account_key'], tuple(sorted(row['segments'].items())))
        require(key not in reported, 'duplicate report posting address')
        reported[key] = (row['debit_minor'], row['credit_minor'])
    posted = defaultdict(lambda: [0, 0])
    for entry in entries:
        # Journal layout is not fixed by the packet. Do not invent a layout failure.
        date, cur = entry.get('posting_date'), entry.get('currency')
        legs = entry.get('legs', entry.get('lines'))
        if not isinstance(date, str) or not isinstance(cur, str) or not isinstance(legs, list):
            return False
        if cur != currency or not date.startswith(month + '-'):
            continue
        for leg in legs:
            if not isinstance(leg, dict) or 'account_key' not in leg or not isinstance(leg.get('segments'), dict):
                return False
            integer_fields(leg, ('debit_minor', 'credit_minor'), 'journal leg')
            require(leg['debit_minor'] >= 0 and leg['credit_minor'] >= 0, 'negative journal movement')
            key = (leg['account_key'], tuple(sorted(leg['segments'].items())))
            posted[key][0] += leg['debit_minor']
            posted[key][1] += leg['credit_minor']
    equal({k: v for k, v in reported.items() if any(v)},
          {k: tuple(v) for k, v in posted.items() if any(v)}, 'report gross matches posted journal')
    return True


def earned_minor(row):
    integer_fields(row, ("earned_minor",), "revenue unit")
    return row["earned_minor"]


def document_totals(documents, expected, label="documents"):
    # Complete zero-price work may have a zero document or no document.
    observed = sorted((d["kind"], d["total_minor"]) for d in documents if d["total_minor"] != 0)
    equal(observed, sorted(expected), label)
    for d in documents:
        equal(sum(i["amount_minor"] for i in d["items"]), d["total_minor"], f"{label} item sum")
        if d["total_minor"] == 0:
            require(all(i["amount_minor"] == 0 for i in d["items"]), f"{label}: zero total hides opposing items")


def distribution(legs, expected, label="account distribution"):
    observed = {}
    for leg in legs:
        key = (leg["account_key"], tuple(sorted(leg["segments"].items())))
        observed[key] = observed.get(key, 0) + leg["debit_minor"] - leg["credit_minor"]
    equal({k: v for k, v in observed.items() if v}, {k: v for k, v in expected.items() if v}, label)


def retained_projection(actual, before, label):
    """Preserve old observable values, allowing new response fields after upgrade."""
    if isinstance(before, dict):
        require(isinstance(actual, dict), label + ': expected object')
        for key, value in before.items():
            require(key in actual, label + ': missing ' + key)
            retained_projection(actual[key], value, label + '.' + key)
    elif isinstance(before, list):
        require(isinstance(actual, list) and len(actual) == len(before), label + ': list population changed')
        for old, new in zip(before, actual):
            retained_projection(new, old, label)
    else:
        equal(actual, before, label)


def retained_response(actual, before, label):
    """Old operation results stay fixed; additive resource fields are compatible."""
    require(isinstance(actual, dict) and 'data' in actual, label + ': missing data')
    equal({k: v for k, v in actual.items() if k != 'data'},
          {k: v for k, v in before.items() if k != 'data'}, label + '.envelope')
    retained_projection(actual['data'], before['data'], label + '.data')


def closed_unchanged(before, after):
    def financial(report):
        result = dict(report)
        for name in ("accounts", "rollups", "units"):
            rows = []
            for row in report.get(name, []):
                amounts = [v for k, v in row.items() if k.endswith("_minor")]
                require(amounts and all(type(v) is int for v in amounts),
                        "closed report has invalid monetary fields")
                if any(amounts):
                    rows.append(row)
            result[name] = rows
        return result
    equal(financial(after), financial(before), "closed report changed")


def customer_documents(documents, expected, label="documents by debtor"):
    equal(sorted((d["customer_id"], d["kind"], d["total_minor"]) for d in documents),
          sorted(expected), label)
    for doc in documents:
        equal(sum(i["amount_minor"] for i in doc["items"]), doc["total_minor"], label + " item sum")


def effect_integrity(rows):
    ids = []
    for row in rows:
        require(isinstance(row, dict), "effect must be an object")
        for field in ("id", "key", "kind", "currency", "economic_date", "posting_date", "configuration_id"):
            require(isinstance(row.get(field), str) and row[field], f"effect missing {field}")
        require("scope_key" in row and (row["scope_key"] is None or
                isinstance(row["scope_key"], str) and row["scope_key"]), "effect missing or invalid scope_key")
        ids.append(row["id"])
        integer_fields(row, ("amount_minor",), "effect")
        require(isinstance(row.get("legs"), list), "effect missing legs")
        for leg in row["legs"]:
            integer_fields(leg, ("debit_minor", "credit_minor"), "effect leg")
            require(leg["debit_minor"] >= 0 and leg["credit_minor"] >= 0,
                    "negative journal side")
            require(not (leg["debit_minor"] and leg["credit_minor"]), "journal leg has two positive sides")
        equal(sum(l["debit_minor"] for l in row["legs"]),
              sum(l["credit_minor"] for l in row["legs"]), "individual effect balances")
    equal(len(ids), len(set(ids)), "duplicate logical effects")
    paired_journals = set()
    for row in rows:
        if row["legs"] or row["amount_minor"] == 0:
            continue
        # A transfer may publish both scopes' balanced journal on one member.
        # Its legless counterpart must be reconstructible, not an orphan amount.
        require(row["kind"] == "position_transfer" and isinstance(row.get("source"), dict)
                and row.get("scope_key") and isinstance(row.get("corrects_ids"), list),
                "nonzero effect has no reconstructible transfer legs")
        peers = [p for p in rows if p["kind"] == "position_transfer" and p['legs']
                 and p['id'] not in paired_journals and p['scope_key'] != row['scope_key']
                 and p['amount_minor'] == -row['amount_minor']
                 and all(p.get(k) == row.get(k) for k in
                         ("source", "economic_date", "posting_date", "currency", "corrects_ids"))]
        peers = [p for p in peers
                 if all(l.get('scope_key') in (row['scope_key'], p['scope_key'])
                        and l.get('function') in ('contract_position', 'contract_asset', 'deferred')
                        for l in p['legs'])
                 and all(sum(l['debit_minor'] - l['credit_minor'] for l in p['legs']
                             if l.get('scope_key') == member['scope_key']) == -member['amount_minor']
                         for member in (row, p))]
        require(peers, 'legless transfer needs an unused opposite scoped journal')
        paired_journals.add(sorted(peers, key=lambda p: p['id'])[0]['id'])
    for row in rows:
        if (row['kind'] == 'position_transfer' and row['amount_minor'] != 0 and
                any(l.get('scope_key') and l['scope_key'] != row['scope_key'] for l in row['legs'])):
            require(row['id'] in paired_journals, 'joint transfer journal missing opposite logical effect')
