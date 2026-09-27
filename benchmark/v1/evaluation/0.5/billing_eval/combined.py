"""Reviewed combined histories, strengthened and newly versioned for 0.4."""
from collections import Counter
import copy
from billing_eval.checks import equal, require, fields, document_totals, closed_unchanged
from billing_eval.client import identifier
from billing_eval.m1 import immutable_document, single
from billing_eval.m2 import Usage
from billing_eval.m4 import deal, promise, installment, amend, apply, lineage_units as units, amounts, scope_deal
from billing_eval.m6 import correction
from billing_eval.funding_interactions import meridian_case
from billing_eval.reviewed_challenges import transfer_checks, revenue_balances, checked
from billing_eval.suite import Case


def reclass(f, date):
    historical = copy.deepcopy(f.effects())
    config, accounts = f.chart(effective=date, prefix='new', routing='original')
    equal(f.effects(), historical, 'publishing chart did not reclassify history')
    ids = [e['id'] for e in historical if any(l['function'] == 'service_revenue' for l in e['legs'])]
    require(ids, 'positive revenue reclassification control')
    body = dict(key='reclass', scope=dict(currency='USD', scope_keys=None, effect_ids=ids,
                                        economic_window=None), configuration_id=config['id'], posting_date=date)
    p = f.api.preview('/reclassification-previews', body)
    f.api.create('/reclassifications', dict(body, basis_token=p['basis_token']))
    return accounts


def net_debt(f, buyer, expected):
    s = f.statement(buyer)
    equal(s['ar_minor'] - s['available_backed_minor'] - s['available_restricted_minor'], expected,
          'receivable less still available funds')


def public_allocations(application):
    names = ('document_id', 'item_key', 'original_minor', 'unapplied_minor',
             'backing_released_minor', 'currently_applied_minor', 'unappliable_minor')
    rows = application.get('allocations')
    require(isinstance(rows, list), 'application missing allocations')
    require(all(isinstance(row, dict) and all(k in row for k in names) for row in rows),
            'application missing public allocation counters')
    return sorted(({k: row[k] for k in names} for row in rows),
                  key=lambda row: (row['document_id'], row['item_key']))


def usage_correction_effects(effects, previous_ids, original_scopes):
    adjustments = [e for e in effects if e['id'] not in previous_ids and e['kind'] == 'unfunded_usage']
    require(adjustments, 'correction usage earnings exist')
    equal(sum(e['amount_minor'] for e in adjustments), -1000, 'correction usage earnings delta')
    require(all(e['economic_date'] == '2028-01-20' and e['posting_date'] == '2028-02-03'
                for e in adjustments), 'correction economic date retained')
    require(all(e['scope_key'] in original_scopes for e in adjustments), 'correction unit attribution')


def paid_sources(c):
    f = c.f
    f.chart(separate=False)
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 100000, [promise('old', product, end='2028-01-11')],
             [installment('first', '2028-01-01', 60000, 'old'), installment('second', '2028-01-02', 40000, 'old')])
    original = []
    for day in ('2028-01-01', '2028-01-02'):
        f.api.at(day)
        _, docs = f.bill(day, day)
        original.extend(docs)
    document_totals(original, [('invoice', 60000), ('invoice', 40000)])
    source = single([d for d in original if d['total_minor'] == 40000], 'paid source')
    cash = f.receipt(buyer, 40000, post='2028-01-02')
    payment = f.application(cash, source, 40000, post='2028-01-02')
    f.api.at('2028-01-06')
    f.recognition('2028-01-06')
    equal(amounts(units(f, d), 'old', 'earned_minor'), 60000, 'six days earned')
    f.api.at('2028-01-07')
    accounts = reclass(f, '2028-01-07')
    equal(revenue_balances(f), {accounts['service_revenue']: -60000}, 'predecessor revenue moved once')
    scope = d['scope_keys']['groups']['group']
    edges = []
    for i in range(2):
        c.checkpoint('paid-source-replacement-'+str(i+1))
        change = dict(price_delta_minor=30000 if i == 0 else 0, new_services_only=False,
                      new_services_distinct=True, remaining_distinct=True, changes_ongoing_progress=False,
                      successor_promises=[promise('s'+str(i), product, start='2028-01-07', end='2028-02-01')], revised_group=None)
        before = {t['key'] for t in f.api.all('/position-transfers')}
        apply(f, amend(f, d, '2028-01-07', change, scope=scope), '2028-01-07')
        edge = single([t for t in f.api.all('/position-transfers') if t['key'] not in before], 'new transfer')
        edges.append(edge['predecessor_scope_key'])
        scope = edge['successor_scope_key']
        _, new = f.bill('2028-01-07', '2028-01-07')
        document_totals(new, [('invoice', 30000)] if i == 0 else [])
        if i == 0:
            sale = single(new, 'new sale')
    transfer_checks(c, edges, [40000, 70000], {x['id'] for x in original} | {sale['id']})
    agreements = copy.deepcopy(f.api.all('/amendments'))
    c.checkpoint('unapply-reverse-rebill-reapply-paid-source')
    f.api.action('/applications/'+identifier(payment['id'])+'/unapply',
                 dict(allocations=[dict(document_id=source['id'], item_key=source['items'][0]['key'], amount_minor=40000)],
                      posting_date='2028-01-07'))
    f.api.action('/billing-results/'+identifier(source['result_id'])+'/reverse', dict(key='reverse', posting_date='2028-01-07'))
    equal(amounts(units(f, d), 's1', 'billed_minor'), 30000, 'reversed source released through both transfers')
    transfer_checks(c, edges, [0, 30000], {original[0]['id'], sale['id']})
    f.api.at('2028-01-08')
    _, rebills = f.bill('2028-01-08', '2028-01-08')
    document_totals(rebills, [('invoice', 40000)])
    rebill = single(rebills, 'reissued paid source')
    f.application(cash, rebill, 40000, post='2028-01-08')
    transfer_checks(c, edges, [40000, 70000], {original[0]['id'], sale['id'], rebill['id']})
    equal(f.api.all('/amendments'), agreements, 'rebilling changed negotiated agreements')
    fields(f.statement(buyer), dict(ar_minor=90000, available_backed_minor=0, cash_received_minor=40000), 'cash reapplied once')
    f.api.at('2028-01-16')
    f.recognition('2028-01-16')
    equal(amounts(units(f, d), 's1', 'earned_minor'), 28000, 'successor ten of twenty-five days')
    f.api.at('2028-01-17')
    c.checkpoint('terminate-reclassified-successor-and-refund')
    owner = scope_deal(f, d, scope)
    r = f.api.action('/deals/'+identifier(owner['id'])+'/terminations', dict(key='end', scope_key=scope,
        effective_on='2028-01-17', retained_price_minor=20000, termination_fee=None), status=(200, 201))
    f.api.action('/terminations/'+identifier(r['data']['id'])+'/apply', dict(posting_date='2028-01-17'))
    _, credits = f.bill('2028-01-17', '2028-01-17')
    equal(sum(x['total_minor'] for x in credits if x['kind'] == 'credit'), 50000, 'termination credit')
    by_source = Counter()
    for doc in credits:
        equal(doc['kind'], 'credit', 'termination document kind')
        for item in doc['items']:
            by_source[item['origin_document_id']] += item['amount_minor']
    equal(dict(by_source), {sale['id']: 10000, rebill['id']: 40000}, 'latest-issued retained source ownership')
    credit = single([x for x in credits if x['available_backed_minor'] >= 5000], 'backed termination credit')
    f.create('/refunds', source=dict(kind='credit', id=credit['id']), amount_minor=5000, posting_date='2028-01-17')
    fields(f.statement(buyer), dict(cash_received_minor=40000, cash_refunded_minor=5000), 'real cash preserved')
    net_debt(f, buyer, 45000)
    equal(revenue_balances(f), {accounts['service_revenue']: -80000}, 'retained revenue on accepted accounts')
    equal(amounts(units(f, d), 'old', 'earned_minor'), 60000, 'untouched predecessor revenue')
    equal(amounts(units(f, d), 's1', 'earned_minor'), 20000, 'termination revenue belongs to successor')
    successor_effects = [e for e in f.effects() if e['scope_key'] == scope and e['kind'] == 'recognition']
    equal(sum(e['amount_minor'] for e in successor_effects), 20000, 'per-scope recognition, not only report')
    equal(f.api.get('/documents/'+identifier(original[0]['id']))['open_minor'], 60000, 'unrelated invoice not silently paid')
    for doc in original:
        immutable_document(doc, f.api.get('/documents/'+identifier(doc['id'])))


def spent_correction(c, fixed):
    f = c.f
    f.chart()
    u = Usage(f)
    event, _ = u.event('work', '100')
    _, docs = u.finish()
    document_totals(docs, [('invoice', 10000)])
    original = single(docs, 'original usage')
    buyer = u.customers[0]
    cash = f.receipt(buyer, 10000, post='2028-02-01')
    f.application(cash, original, 10000, post='2028-02-01')
    if fixed:
        concession = f.memo(buyer, original, fixed, post='2028-02-01')
    f.create('/period-closes', month='2028-01')
    closed = copy.deepcopy(f.report('2028-01'))
    f.api.at('2028-02-02')
    accounts = reclass(f, '2028-02-02')
    equal(revenue_balances(f), {accounts['service_revenue']: -(10000-fixed)}, 'initial reclassified net revenue')
    # The later chart must differ from the retained explicit reclassification.
    f.api.at('2028-02-03')
    f.chart(effective='2028-02-03', prefix='later', routing='original')
    old_effects = {e['id'] for e in f.effects()}
    c.checkpoint('first-revision-with-retained-routing-and-concession')
    before = {x['id'] for x in f.api.all('/documents')}
    correction(f, {}, dict(kind='source', source_id=u.source['id'],
                          event=dict(event, key='revision-2', revision=2, quantity='80')), date='2028-02-03')
    credits = [x for x in f.api.all('/documents') if x['id'] not in before]
    document_totals(credits, [('credit', 2000)])
    credit = single(credits, 'usage correcting credit')
    f.create('/refunds', source=dict(kind='credit', id=credit['id']), amount_minor=500, posting_date='2028-02-03')
    f.subscription(buyer, price='50', kind='one_time', recognition='acceptance', starts='2028-02-03', end='2028-03-01')
    _, extra = f.bill('2028-02-03', '2028-02-03')
    document_totals(extra, [('invoice', 5000)])
    extra = single(extra, 'separate debt')
    payment = f.application(credit, extra, 1000, kind='credit', post='2028-02-03')
    c.checkpoint('second-revision-after-refund-and-cross-invoice-application')
    before = {x['id'] for x in f.api.all('/documents')}
    correction(f, {}, dict(kind='source', source_id=u.source['id'],
                          event=dict(event, key='revision-3', revision=3, quantity='90')), date='2028-02-03')
    document_totals([x for x in f.api.all('/documents') if x['id'] not in before], [('debit', 1000)])
    net_debt(f, buyer, 4500-fixed)
    fields(f.statement(buyer), dict(cash_received_minor=10000, cash_refunded_minor=500), 'cash independent of rerating')
    equal(f.api.get('/documents/'+identifier(extra['id']))['open_minor'], 4000, 'prior application to separate invoice preserved')
    equal(public_allocations(f.api.get('/applications/'+identifier(payment['id']))),
          public_allocations(payment), 'recorded application history retained')
    equal(revenue_balances(f), {accounts['service_revenue']: -(9000-fixed)}, 'latest economics on explicitly reclassified accounts')
    original_scopes = {i['scope_key'] for i in original['items']}
    usage_correction_effects(f.effects(), old_effects, original_scopes)
    closed_unchanged(closed, f.report('2028-01'))
    immutable_document(original, f.api.get('/documents/'+identifier(original['id'])))
    if fixed:
        immutable_document(concession, f.api.get('/documents/'+identifier(concession['id'])))


CASES = [
    Case('mixed-retained-rights-paid-reclassified', 5, 'exploratory', (),
         'Retained rights correction with both settlement and selective reclassification', meridian_case(True, True)),
    Case('mixed-paid-source-chain-reclassified-termination', 5, 'exploratory', (),
         'Paid invoice ownership through replacements, reversal, reclassification and termination', checked(paid_sources)),
    *[Case('mixed-spent-credit-reclassified-fixed-'+str(fixed), 5, 'exploratory', (),
           'Correct revised usage after refund and cross-invoice credit consumption',
           lambda c, n=fixed: spent_correction(c, n)) for fixed in (0, 2000)],
]
