"""A formerly fixed convention, exercised through old and new commercial history."""
import copy
import json
from .checks import equal, fields, require, document_totals, closed_unchanged
from .client import identifier
from .m1 import immutable_document
from .m3 import order
from .m6 import correction
from .suite import case


def publish(f, method='daily_365', date='2028-03-01'):
    f.api.at(date)
    policy = f.create('/billing-policies', effective_from=date, proration=method)
    f.api.action(f"/billing-policies/{identifier(policy['id'])}/publish")
    return policy


def total(f, sub, start, column='net_minor'):
    rows = [r for r in f.units(sub, '2028-07-31') if isinstance(r.get('window'), dict)
            and r['window'].get('starts_on') == start]
    equal(len(rows), 1, 'one recurring charge in selected period')
    value = rows[0].get(column)
    require(type(value) is int, f'required integer period {column}')
    return value


def prepare(f):
    """Only M1 operations: no policy field, no future route, real old storage."""
    f.chart()
    buyer = f.customer('old-buyer')
    sub, _, _ = f.subscription(buyer, price='310', starts='2028-01-11', end='2028-07-01',
                              period=dict(months=1, anchor='day', day=1))
    f.api.at('2028-01-11')
    _, january = f.bill('2028-01-11', '2028-01-11', customers=[buyer['id']])
    document_totals(january, [('invoice', 21000)])
    f.api.at('2028-02-01')
    _, february = f.bill('2028-02-01', '2028-02-01', customers=[buyer['id']])
    document_totals(february, [('invoice', 31000)])
    f.recognition('2028-01-31', '2028-02-01')
    f.create('/period-closes', month='2028-01')
    return dict(buyer=buyer, sub=sub, january=copy.deepcopy(january[0]),
                closed=copy.deepcopy(f.report('2028-01')), original=copy.deepcopy(f.api.all('/documents')))


def bind_and_change(f, state):
    p = publish(f)
    _, march = f.bill('2028-03-01', '2028-03-01', customers=[state['buyer']['id']])
    document_totals(march, [('invoice', 31000)])
    f.api.at('2028-03-05')
    new = f.customer('new-buyer')
    fresh, _, _ = f.subscription(new, price='310', starts='2028-03-10', end='2028-07-01',
                                period=dict(months=1, anchor='day', day=1))
    _, first = f.bill('2028-03-10', '2028-03-10', customers=[new['id']])
    document_totals(first, [('invoice', 22422)])
    f.api.at('2028-04-01')
    _, april = f.bill('2028-04-01', '2028-04-01', customers=[state['buyer']['id']])
    document_totals(april, [('invoice', 31000)])
    price_order = order(f, state['sub'], '2028-04-11', [dict(kind='price', charge_key='base', price='400')])['data']
    equal(total(f, state['sub'], '2028-04-01'), 37000, 'old subscription still uses anchored month')
    order(f, state['sub'], '2028-05-16', [dict(kind='policy_migration', policy_id=p['id'])])
    equal(total(f, state['sub'], '2028-05-01'), 40396, 'mixed-policy month')
    return dict(state, policy=p, new_buyer=new, new_sub=fresh, april=copy.deepcopy(april[0]), price_order=price_order)


def rebill_and_cancel(f, state):
    # Reverse before issuing an April adjustment, so no dependent memo has to be
    # silently compensated. The May migration is already effective at this point.
    f.api.at('2028-05-20')
    f.api.action(f"/billing-results/{identifier(state['april']['result_id'])}/reverse",
                 dict(key=f.key('release-april'), posting_date='2028-05-20'))
    _, docs = f.bill('2028-05-20', '2028-05-20', customers=[state['buyer']['id']])
    document_totals(docs, [('invoice', 77396)])
    equal(total(f, state['sub'], '2028-04-01', 'billed_minor'), 37000, 'rebill retains old rule')
    equal(total(f, state['sub'], '2028-05-01', 'billed_minor'), 40396, 'migrated May billing')
    f.api.at('2028-06-01')
    _, june = f.bill('2028-06-01', '2028-06-01', customers=[state['buyer']['id']])
    document_totals(june, [('invoice', 40000)])
    order(f, state['sub'], '2028-06-21', [dict(kind='cancel')])
    equal(total(f, state['sub'], '2028-06-01'), 26301, 'cancelled service uses its accepted policy')
    f.api.at('2028-07-01')
    _, credits = f.bill('2028-07-01', '2028-07-01', customers=[state['buyer']['id']])
    document_totals(credits, [('credit', 13699)])
    f.recognition('2028-06-30', '2028-07-01')
    for start, amount in (('2028-04-01', 37000), ('2028-05-01', 40396), ('2028-06-01', 26301)):
        equal(total(f, state['sub'], start, 'earned_minor'), amount, 'completed service earns policy-priced consideration')
    closed_unchanged(state['closed'], f.report('2028-01'))
    for old in state['original']:
        immutable_document(old, f.api.get(f"/documents/{identifier(old['id'])}"))
    return state


def correct_across_policy(f, state):
    f.api.at('2028-07-01')
    old_documents = copy.deepcopy(f.api.all('/documents'))
    before = {d['id'] for d in old_documents}
    old_effects = copy.deepcopy(f.effects())
    correction(f, {}, dict(kind='recorded_term', resource=dict(kind='subscription_order', id=state['price_order']['id']),
                           path=['effective_on'], replacement='2028-05-21'), date='2028-07-01')
    equal(total(f, state['sub'], '2028-04-01'), 31000, 'corrected April remains old policy')
    equal(total(f, state['sub'], '2028-05-01'), 34562, 'corrected order crosses fixed policy migration')
    equal(total(f, state['sub'], '2028-06-01'), 26301, 'later cancellation remains accepted')
    for start, amount in (('2028-04-01', 31000), ('2028-05-01', 34562), ('2028-06-01', 26301)):
        equal(total(f, state['sub'], start, 'earned_minor'), amount, 'correction revises earned consideration')
    issued = [d for d in f.api.all('/documents') if d['id'] not in before]
    require(issued, 'correction must issue documents, not only preview new targets')
    equal(sum(d['total_minor'] if d['kind'] == 'credit' else -d['total_minor'] for d in issued),
          11834, 'separate April and May correction amounts')
    require(all(d['customer_id'] == state['buyer']['id'] for d in issued), 'correction debtor')
    equal(sum(i['amount_minor'] for d in issued for i in d['items']), 11834, 'correction item conservation')
    by_period = {}
    original_items = {(d['id'], i['key']): i for d in old_documents for i in d['items']}
    for doc in issued:
        equal(doc['kind'], 'credit', 'both affected periods reduce consideration')
        for item in doc['items']:
            equal(item['subscription_id'], state['sub']['id'], 'correction service owner')
            require(isinstance(item.get('service_window'), dict) and
                    all(isinstance(item['service_window'].get(k), str) for k in ('starts_on', 'ends_before')),
                    'correction item missing recurring service window')
            require(all(k in item for k in ('origin_document_id', 'origin_item_key')),
                    'correction item missing original service link')
            start = item['service_window']['starts_on']
            by_period[start] = by_period.get(start, 0) + item['amount_minor']
            source = original_items.get((item['origin_document_id'], item['origin_item_key']))
            require(source is not None, 'correction source link')
            equal((source['subscription_id'], source['scope_key'], source['service_window']),
                  (item['subscription_id'], item['scope_key'], item['service_window']), 'correction links its own original service')
    equal(by_period, {'2028-04-01': 6000, '2028-05-01': 5834}, 'correction attribution by service period')
    for old in old_documents:
        immutable_document(old, f.api.get(f"/documents/{identifier(old['id'])}"))
    effects = f.effects()
    old_by_id = {e['id']: e for e in old_effects}
    current_by_id = {e['id']: e for e in effects}
    for key, value in old_by_id.items():
        equal(current_by_id.get(key), value, 'correction must retain historical effects')
    revenue_by_month = {}
    for effect in effects:
        if effect['id'] in old_by_id:
            continue
        delta = sum(leg['debit_minor']-leg['credit_minor'] for leg in effect['legs'] if leg['function'] == 'service_revenue')
        if delta:
            equal(effect['posting_date'], '2028-07-01', 'correction journal posting date')
            month = effect['economic_date'][:7]
            revenue_by_month[month] = revenue_by_month.get(month, 0)+delta
    equal({k: v for k, v in revenue_by_month.items() if v}, {'2028-04': 6000, '2028-05': 5834},
          'earned correction reaches the journal under its service dates')
    closed_unchanged(state['closed'], f.report('2028-01'))


@case('v03-policy-accepted-binding', 2, 'P01', 'policy-binding', 'New default changes new sales, not old accepted subscriptions')
def binding(c):
    state = prepare(c.f)
    c.checkpoint('new_policy_on_old_sale')
    bind_and_change(c.f, state)


@case('v03-policy-rebill-and-cancel', 2, 'P01', 'policy-routes', 'Rebilling historical service and cancellation follow service-date bindings')
def rebill(c):
    state = bind_and_change(c.f, prepare(c.f))
    c.checkpoint('rebill_after_migration')
    rebill_and_cancel(c.f, state)


@case('v03-policy-correct-order-across-migration', 5, 'P01', 'policy-correction', 'Moving one commercial fact does not move a separate accepted policy boundary')
def corrected(c):
    state = rebill_and_cancel(c.f, bind_and_change(c.f, prepare(c.f)))
    c.checkpoint('correct_date_across_retained_policy')
    correct_across_policy(c.f, state)


@case('v03-policy-draft-acceptance-and-inert-order', 2, 'P01', 'policy-acceptance', 'Draft creation does not bind a policy; an inert action does not create proration')
def draft(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    f.api.at('2028-02-01')
    sub, _, _ = f.subscription(buyer, price='310', starts='2028-03-10', end='2028-05-01',
                              period=dict(months=1, anchor='day', day=1), accept=False)
    publish(f)
    c.checkpoint('accept_existing_draft_under_new_default')
    f.api.action(f"/subscriptions/{identifier(sub['id'])}/accept")
    f.evidence(sub, 'base', 'activation', '2028-03-10')
    order(f, sub, '2028-04-10', [dict(kind='price', charge_key='base', price='310')])
    equal(total(f, sub, '2028-03-10'), 22422, 'binding occurs at acceptance')
    equal(total(f, sub, '2028-04-01'), 31000, 'inert price order keeps full period')


@case('v03-policy-rejected-migration-is-inert', 2, 'P01', 'policy-atomicity', 'An invalid migration cannot partly accept an accompanying price change')
def rejected(c):
    f = c.f
    f.chart()
    buyer = f.customer()
    sub, _, _ = f.subscription(buyer, end='2028-04-01')
    publish(f, date='2028-03-01')
    def economic_rows():
        columns = ('scope_key', 'window', 'quantity', 'gross_minor', 'net_minor', 'billed_minor', 'earned_minor')
        return sorted(json.dumps({key: row.get(key) for key in columns}, sort_keys=True)
                      for row in f.units(sub, '2028-04-01'))
    before = economic_rows()
    f.api.at('2028-03-01')
    # Future policy is ineligible for the requested service boundary.
    future = f.create('/billing-policies', effective_from='2028-04-01', proration='anchored_month')
    f.api.action(f"/billing-policies/{identifier(future['id'])}/publish")
    version = f.api.get(f"/subscriptions/{identifier(sub['id'])}")['version']
    c.checkpoint('invalid_migration_does_not_accept_price')
    f.api.error('POST', f"/subscriptions/{identifier(sub['id'])}/orders",
                dict(key='bad-migration', effective_on='2028-03-10', posting_date='2028-03-01', actions=[
                    dict(kind='price', charge_key='base', price='999'),
                    dict(kind='policy_migration', policy_id=future['id'])]), 422, 'invalid_domain', version=version)
    equal(economic_rows(), before, 'failed atomic order changed economics')
    equal(f.api.get(f"/subscriptions/{identifier(sub['id'])}")['version'], version, 'rejected order changed subscription version')
