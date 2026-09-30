"""Public impact schema plus independent economics for the simple closed sale."""
from collections import defaultdict

from .checks import equal, require


def text(value):
    return isinstance(value, str) and bool(value)


def references(rows, label):
    require(isinstance(rows, list), label + ': expected list')
    for row in rows:
        require(isinstance(row, dict) and text(row.get('kind')) and text(row.get('id')),
                label + ': expected kind and ID')


def validate_impacts(result):
    require(isinstance(result, dict), 'impact result: expected object')
    references(result.get('affected'), 'affected references')
    rows = result.get('effects')
    require(isinstance(rows, list), 'impact effects: expected list')
    required = {'key', 'kind', 'scope_key', 'customer_id', 'obligation_key', 'old_minor',
                'target_minor', 'delta_minor', 'old_addresses', 'target_addresses',
                'source_refs', 'unchanged_reason'}
    for row in rows:
        require(isinstance(row, dict), 'impact row: expected object')
        require(required <= row.keys(), 'impact row: missing required fields ' +
                ', '.join(sorted(required - row.keys())))
        for key in ('key', 'kind', 'scope_key'):
            require(text(row[key]), 'impact ' + key + ': expected nonempty string')
        for key in ('customer_id', 'obligation_key', 'unchanged_reason'):
            require(row[key] is None or isinstance(row[key], str), 'impact ' + key + ': expected string or null')
        for key in ('old_minor', 'target_minor', 'delta_minor'):
            require(type(row[key]) is int, 'impact ' + key + ': expected integer')
        equal(row['target_minor'] - row['old_minor'], row['delta_minor'], 'impact arithmetic')
        references(row['source_refs'], 'impact source references')
        for key in ('old_addresses', 'target_addresses'):
            require(isinstance(row[key], list), 'impact addresses: expected list')
            for address in row[key]:
                require(isinstance(address, dict) and text(address.get('account_key')),
                        'impact address: expected account key')
                segments = address.get('segments')
                require(isinstance(segments, dict) and all(isinstance(k, str) and isinstance(v, str)
                        for k, v in segments.items()), 'impact address: expected string segments')
                for money in ('debit_minor', 'credit_minor'):
                    require(type(address.get(money)) is int and address[money] >= 0,
                            'impact address ' + money + ': expected nonnegative integer')
    return rows


def closed_sale_impact(preview, customer, accounts, old=10000, target=8000):
    """Accept daily or aggregate effects and separate or combined account projections."""
    rows = validate_impacts(preview['result'])
    # Account-wide projections may have a null customer. Debtor-specific economic
    # rows still identify the actual customer; a different nonnull debtor is never valid.
    require(all(r['customer_id'] in (None, customer) for r in rows), 'preview impact has wrong debtor')
    for kind in ('billing', 'recognition'):
        economic = [r for r in rows if r['kind'] == kind]
        if economic:
            if kind == 'billing':
                require(all(r['customer_id'] == customer for r in economic),
                        'billing impact omits debtor')
            equal(sum(r['old_minor'] for r in economic), old, kind + ' impact old amount')
            equal(sum(r['target_minor'] for r in economic), target, kind + ' impact target amount')
    projections = [[r for r in rows if r['kind'] in ('billing', 'recognition')],
                   [r for r in rows if r['kind'] == 'account_distribution']]
    populated = [group for group in projections if any(
        r['old_addresses'] or r['target_addresses'] for r in group)]
    require(populated, 'preview omits required billing/recognition accounting impact')
    # Some implementations put amounts on economic rows and addresses on a separate
    # projection. If both projections carry addresses, both must be correct.
    for chosen in populated:
        for field, amount in (('old_addresses', old), ('target_addresses', target)):
            totals = defaultdict(int)
            for row in chosen:
                for address in row[field]:
                    require(address['segments'] == {}, 'preview introduces unexpected accounting segments')
                    totals[address['account_key']] += address['debit_minor'] - address['credit_minor']
            # A corrective credit may remain in customer funds or be applied to AR.
            totals[accounts['receivable']] += totals.pop(accounts['customer_funds'], 0)
            actual = {k: v for k, v in totals.items() if v}
            equal(actual, {accounts['receivable']: amount, accounts['service_revenue']: -amount},
                  'preview ' + field + ' independently expected accounting target')
