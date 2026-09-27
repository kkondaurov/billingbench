"""Reviewed source-ownership and accounting-route challenges, promoted in 0.3."""
from collections import Counter
import copy
from .checks import equal, fields, require, document_totals, closed_unchanged, earned_minor
from .client import identifier
from .m1 import immutable_document
from .m4 import deal, promise, installment, amend, apply, lineage_units as units, amounts
from .m6 import correction
from .suite import case


def checked(fn):
    def run(c):
        fn(c)
        require(not [r for r in c.observations if r.get('matches') is False],
                str([r for r in c.observations if r.get('matches') is False]))
    return run

def observe(c, label, actual, expected):
    c.observations.append(dict(stage=c.stage, label=label, actual=actual, expected=expected,
                               matches=actual == expected, request_count=len(c.f.api.trace)))

def scope_map(c, value):
    require(isinstance(value, dict), 'scope keys must be the documented key-to-scope map')
    return value

def revenue_balances(f):
    balances = Counter()
    for e in f.effects():
        for leg in e['legs']:
            if leg['function'] == 'service_revenue':
                balances[leg['account_key']] += leg['debit_minor'] - leg['credit_minor']
    return {k: v for k, v in balances.items() if v}

def transfer_view(rows, edge):
    rows = [t for t in rows if t['predecessor_scope_key'] == edge]
    require(rows, 'retained transfer history exists')
    sources = Counter()
    for row in rows:
        for s in row['source_items']:
            sources[s['document_id'], s['item_key']] += s['assigned_minor']
    return dict(billed_transfer_minor=sum(t['billed_transfer_minor'] for t in rows),
                source_items=[dict(document_id=d, item_key=k, assigned_minor=n) for (d, k), n in sources.items() if n])

def transfer_checks(c, edges, totals, allowed):
    documents = {d['id']: d for d in c.f.api.all('/documents')}
    for edge, total in zip(edges, totals):
        t = transfer_view(c.f.api.all('/position-transfers'), edge)
        observe(c, 'edge assigned billing', t['billed_transfer_minor'], total)
        observe(c, 'source items conserve edge assigned billing', sum(s['assigned_minor'] for s in t['source_items']), total)
        observe(c, 'edge uses only eligible unreversed invoice sources',
                all(s['document_id'] in allowed for s in t['source_items'] if s['assigned_minor']), True)
        for source in t['source_items']:
            if not source['assigned_minor']:
                continue
            document = documents.get(source['document_id'])
            require(document is not None, 'transfer source document does not exist')
            matches = [i for i in document['items'] if i['key'] == source['item_key']]
            require(len(matches) == 1, 'transfer source item does not exist uniquely')
            require(matches[0]['amount_minor'] > 0, 'transfer source item has no positive consideration')
            require(0 < source['assigned_minor'] <= matches[0]['amount_minor'],
                    'transfer source assignment exceeds item consideration')

def source_history(c, split, chains):
    f = c.f
    f.chart(separate=True)
    buyer, product = f.customer(), f.product()
    bills = [installment('first', '2028-01-01', 60000 if split else 100000, 'old')]
    if split:
        bills.append(installment('second', '2028-01-02', 40000, 'old'))
    d = deal(f, buyer, 100000, [promise('old', product, end='2028-01-11')], bills)
    original = []
    for day in (['2028-01-01', '2028-01-02'] if split else ['2028-01-01']):
        f.api.at(day)
        _, docs = f.bill(day, day)
        original.extend(docs)
    document_totals(original, [('invoice', 60000), ('invoice', 40000)] if split else [('invoice', 100000)])
    f.api.at('2028-01-06')
    f.recognition('2028-01-06')
    equal(amounts(units(f, d), 'old', 'earned_minor'), 60000, 'predecessor earned six days')
    f.api.at('2028-01-07')
    scope = scope_map(c, d['scope_keys']['groups'])['group']
    predecessors = {scope, scope_map(c, d['scope_keys']['promises'])['old']}
    edges = []
    for i in range(chains):
        key = 'successor-' + str(i + 1)
        c.checkpoint('replacement-' + str(i + 1))
        commercial = dict(price_delta_minor=30000 if i == 0 else 0, new_services_only=False,
                          new_services_distinct=True, remaining_distinct=True, changes_ongoing_progress=False,
                          successor_promises=[promise(key, product, start='2028-01-07', end='2028-02-01')], revised_group=None)
        apply(f, amend(f, d, '2028-01-07', commercial, scope=scope), '2028-01-07')
        ts = [t for t in f.api.all('/position-transfers') if t['predecessor_scope_key'] in predecessors]
        equal(len({t['successor_scope_key'] for t in ts}), 1, 'one successor for selected predecessor')
        edges.append(ts[0]['predecessor_scope_key'])
        scope = ts[0]['successor_scope_key']
        predecessors = {scope}
        _, new = f.bill('2028-01-07', '2028-01-07')
        document_totals(new, [('invoice', 30000)] if i == 0 else [])
        if i == 0:
            sale = new[0]
        observe(c, 'successor allocation', amounts(units(f, d), key, 'allocation_minor'), 70000)
        observe(c, 'successor assigned billing after new sale', amounts(units(f, d), key, 'billed_minor'), 70000)
        transfer_checks(c, edges, [40000] + [70000] * i, {d['id'] for d in original} | {sale['id']})
        first_edge = transfer_view(f.api.all('/position-transfers'), edges[0])
        observe(c, 'new sale is not old transferred billing',
                sum(s['assigned_minor'] for s in first_edge['source_items'] if s['document_id'] == sale['id']), 0)
    frozen = copy.deepcopy(f.api.all('/documents'))
    selected = original[-1]
    c.checkpoint('reverse-only-selected-source')
    f.api.action(f"/billing-results/{identifier(selected['result_id'])}/reverse", dict(key='reverse-source', posting_date='2028-01-07'))
    observe(c, 'only new sale remains assigned to successor', amounts(units(f, d), key, 'billed_minor'), 30000)
    transfer_checks(c, edges, [0] + [30000] * (chains - 1),
                    ({d['id'] for d in original} - {selected['id']}) | {sale['id']})
    transfer_rows = f.api.all('/position-transfers')
    for edge in edges:
        t = transfer_view(transfer_rows, edge)
        observe(c, 'reversed source has no active transfer coverage',
                sum(r['assigned_minor'] for r in t['source_items'] if r['document_id'] == selected['id']), 0)
    observe(c, 'unrelated new sale outstanding unchanged',
            f.api.get(f"/documents/{identifier(sale['id'])}")['open_minor'], 30000)
    if split:
        observe(c, 'other original invoice outstanding unchanged',
                f.api.get(f"/documents/{identifier(original[0]['id'])}")['open_minor'], 60000)
    c.checkpoint('rebill-selected-source')
    _, rebill = f.bill('2028-01-07', '2028-01-07')
    document_totals(rebill, [('invoice', selected['total_minor'])])
    transfer_checks(c, edges, [40000] + [70000] * (chains - 1),
                    ({d['id'] for d in original} - {selected['id']}) | {sale['id'], rebill[0]['id']})
    observe(c, 'successor assigned billing restored', amounts(units(f, d), key, 'billed_minor'), 70000)
    observe(c, 'allocation did not repeat accepted amendment', amounts(units(f, d), key, 'allocation_minor'), 70000)
    observe(c, 'retained original earnings', amounts(units(f, d), 'old', 'earned_minor'), 60000)
    observe(c, 'net customer debt', f.statement(buyer)['ar_minor'], 130000)
    for old in frozen:
        immutable_document(old, f.api.get(f"/documents/{identifier(old['id'])}"))

def routes(c, route, reclass=False, routing='current'):
    f = c.f
    _, old = f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, price='0.31')
    f.api.at('2028-01-31')
    _, docs = f.bill()
    document_totals(docs, [('invoice', 31)])
    f.recognition('2028-01-31')
    equal(sum(earned_minor(u) for u in f.units(sub)), 31, 'initial fully earned service')
    f.api.at('2028-02-01')
    f.create('/period-closes', month='2028-01')
    closed = copy.deepcopy(f.report('2028-01'))
    historical = copy.deepcopy(f.effects())
    chart, new = f.chart(effective='2028-02-01', prefix='new', routing=routing)
    equal(f.effects(), historical, 'configuration publication must not move balances')
    if reclass:
        c.checkpoint('explicit-reclassification')
        body = dict(key='reclass', scope=dict(currency='USD', scope_keys=None,
                    effect_ids=[e['id'] for e in historical if e['kind'] == 'recognition'], economic_window=None),
                    configuration_id=chart['id'], posting_date='2028-02-01')
        preview = f.api.preview('/reclassification-previews', body)
        f.api.create('/reclassifications', dict(body, basis_token=preview['basis_token']))
        observe(c, 'reclassified earned revenue', revenue_balances(f), {new['service_revenue']: -31})
    c.checkpoint(route + '-after-' + ('reclassification' if reclass else 'chart-change'))
    if route == 'memo':
        f.memo(buyer, docs[0], 2, post='2028-02-01')
    else:
        correction(f, {}, dict(kind='recorded_term', resource=dict(kind='subscription', id=sub['id']),
                   path=['charges', 'base', 'price'], replacement='0.29'), date='2028-02-01')
    target = new if reclass or routing == 'current' else old
    observe(c, 'entire accepted revenue distribution', revenue_balances(f), {target['service_revenue']: -29})
    observe(c, 'corrected earned total', sum(earned_minor(u) for u in f.units(sub)), 29)
    observe(c, 'corrected debt', f.statement(buyer)['ar_minor'], 29)
    document_totals([d for d in f.api.all('/documents') if d['id'] != docs[0]['id']], [('credit', 2)])
    closed_unchanged(closed, f.report('2028-01'))
    now = {e['id']: e for e in f.effects()}
    for e in historical:
        equal(now[e['id']], e, 'original journal effect immutable')
