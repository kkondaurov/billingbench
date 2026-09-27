"""Metering added to an already sold and billed fixed subscription."""
import copy
from .checks import equal, document_totals, closed_unchanged
from .client import identifier
from .m1 import immutable_document
from .m2 import Usage
from .m3 import order
from .policies import publish
from .suite import case


def prepare(f):
    f.chart()
    buyer = f.customer('retained-customer')
    sub, _, _ = f.subscription(buyer, end='2028-04-01', period=dict(months=1, anchor='day', day=1))
    f.api.at('2028-01-31')
    _, documents = f.bill(customers=[buyer['id']])
    document_totals(documents, [('invoice', 10000)])
    f.recognition('2028-01-31')
    f.api.at('2028-02-01')
    f.create('/period-closes', month='2028-01')
    return dict(buyer=buyer, sub=sub, original=copy.deepcopy(documents), closed=f.report('2028-01'))


def change_policy(f, state):
    p = publish(f, date='2028-02-01')
    order(f, state['sub'], '2028-02-01', [dict(kind='policy_migration', policy_id=p['id'])])


def fixed_rows(f, state):
    return sorted((r['window']['starts_on'], r['window']['ends_before'], r['net_minor'])
                  for r in f.units(state['sub'], '2028-06-30') if r['charge_key'] == 'base')


def introduce_metering(f, state):
    f.api.at('2028-03-10')
    state['fixed'] = fixed_rows(f, state)
    u = Usage(f, customers=[state['buyer']], existing=state['sub'], start='2028-03-10',
              window=dict(starts_on='2028-03-10', ends_before='2028-04-01'))
    u.event('measured', '17', date='2028-03-20')
    u.complete()
    if u.addition['operation']['status'] == 'held':
        f.api.action('/orders/'+identifier(u.addition['data']['id'])+'/retry')
    _, docs = f.bill('2028-04-01', '2028-04-01', customers=[state['buyer']['id']])
    usage_items = [i for d in docs for i in d['items'] if i['charge_key'] == 'usage']
    equal(sum(i['amount_minor'] for i in usage_items), 1700, 'new metering is not licensed-charge proration')
    equal({i['subscription_id'] for i in usage_items}, {state['sub']['id']}, 'metering belongs to the existing subscription')
    f.recognition('2028-03-31', '2028-04-01')
    verify(f, state)


def verify(f, state):
    equal(fixed_rows(f, state), state['fixed'], 'adding a charge changed existing fixed consideration')
    usage = [r for r in f.units(state['sub'], '2028-03-31') if r['charge_key'] == 'usage'
             and r['window']['starts_on'].startswith('2028-03')]
    equal(sum(r['net_minor'] for r in usage), 1700, 'retained metered consideration')
    equal(sum(r['earned_minor'] for r in usage), 1700, 'retained metered earnings')
    equal(len(f.api.all('/subscriptions')), 1, 'adding a plan must not replace the subscription')
    for original in state['original']:
        immutable_document(original, f.api.get('/documents/'+identifier(original['id'])))
    closed_unchanged(state['closed'], f.report('2028-01'))
    before = f.api.all('/documents')
    f.bill('2028-04-01', '2028-04-01', customers=[state['buyer']['id']])
    equal(f.api.all('/documents'), before, 'repeated metering sweep duplicated documents')


@case('v03-metering-existing-subscription', 3, 'P02', 'metering-evolution',
      'A new charge kind joins an earlier sale without repricing or replacing its fixed service')
def fresh(c):
    state = prepare(c.f)
    change_policy(c.f, state)
    c.checkpoint('add_metering_to_existing_policy_bound_sale')
    introduce_metering(c.f, state)
