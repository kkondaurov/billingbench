"""M6 executed-pair histories. Expected business checkpoints are independently literal."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import copy

from .checks import equal, require, fields, closed_unchanged, document_totals, retained_projection, retained_response
from .client import identifier
from .m1 import immutable_document, single
from .m4 import deal, promise, installment
from .m6 import correction
from .suite import case


def chart(f, effective='2028-01-01', prefix='fx', clearing=True):
    functions = dict(cash='asset', receivable='asset', customer_funds='liability',
                     contract_position='asset', service_revenue='revenue')
    if clearing:
        functions['settlement_clearing'] = 'asset'
    accounts = [dict(key=prefix+'-'+k, name=k, **{'class': v}, parent_key=None, posting=True,
                     starts_on='2020-01-01', ends_before=None, required_segments=[]) for k, v in functions.items()]
    rules = [dict(key='r-'+k, function=k, priority=1, when={'all': []}, distribution=[
        dict(key='one', weight='100', account={'constant': prefix+'-'+k}, segments={})]) for k in functions]
    return f.chart(effective=effective, prefix=prefix, accounts=accounts, rules=rules)[0]


def invoice(f, buyer, price='72', currency='USD'):
    sub, _, _ = f.subscription(buyer, price=price, currency=currency, kind='one_time',
                              recognition='acceptance', activate=False)
    f.evidence(sub, 'base', 'acceptance', '2028-01-01')
    _, docs = f.bill('2028-01-01', '2028-01-01', customers=[buyer['id']])
    doc = single([d for d in docs if any(i.get('subscription_id') == sub['id'] for i in d['items'])],
                 'new subscription invoice')
    return sub, doc


def receipt(f, buyer, amount=10000, currency='EUR', date='2028-01-02'):
    f.api.at(date)
    return f.create('/receipts', customer_id=buyer['id'], currency=currency, amount_minor=amount,
                    payment_method='bank', posting_date=date)


def allocation(doc, target, source=None):
    value = dict(document_id=doc['id'], item_key=doc['items'][0]['key'], amount_minor=target)
    if source is not None:
        value['source_amount_minor'] = source
    return value


def pay(f, cash, doc, source, target, date='2028-01-02', kind='receipt', key=None):
    f.api.at(date)
    previous = {e['id'] for e in f.effects()} if source is not None and kind == 'receipt' else None
    body = dict(key=key or f.key('pay'), source=dict(kind=kind, id=cash['id']),
                allocations=[allocation(doc, target, source)], posting_date=date)
    app = f.api.create('/applications', body)
    if previous is not None:
        root = expect_pair(f, app, cash, doc, source, target, date)
        if cash['currency'] != doc['currency']:
            movement(f, root, 'funds_application', source, target, date, previous)
    return app, body


def unapply(f, app, doc, target, date='2028-02-02'):
    f.api.at(date)
    return f.api.action('/applications/'+identifier(app['id'])+'/unapply',
                        dict(allocations=[allocation(doc, target)], posting_date=date))


def refund(f, source, cash, face=None, currency='EUR', date='2028-02-02', kind='credit'):
    f.api.at(date)
    body = dict(key=f.key('refund'), source=dict(kind=kind, id=source['id']), amount_minor=cash,
                currency=currency, posting_date=date)
    if face is not None:
        body['credit_amount_minor'] = face
    result = f.api.create('/refunds', body)
    if kind == 'credit':
        f.__dict__.setdefault('_fx_refunds', {})[result['id']] = dict(
            currency=currency, cash=cash, face=cash if face is None else face)
    return result


def price(f, sub, target, date='2028-02-02'):
    f.api.at(date)
    before = {d['id'] for d in f.api.all('/documents')}
    correction(f, {}, dict(kind='recorded_term', resource=dict(kind='subscription', id=sub['id']),
                          path=['charges', 'base', 'price'], replacement=target), date=date)
    return [d for d in f.api.all('/documents') if d['id'] not in before]


def memo(f, buyer, doc, amount, date='2028-02-02'):
    f.api.at(date)
    value = f.create('/memos', kind='credit', customer_id=buyer['id'], currency=doc['currency'],
                     invoice_date=date, posting_date=date, items=[dict(key='adjust', document_id=doc['id'],
                         item_key=doc['items'][0]['key'], amount_minor=amount, reason='Concession')])
    did = value.get('document_id', value['id'])
    f.api.action('/documents/'+identifier(did)+'/post', dict(posting_date=date))
    return f.api.get('/documents/'+identifier(did))


def book(f, expected):
    totals = defaultdict(int)
    effects = f.effects()
    for effect in effects:
        for leg in effect['legs']:
            equal(leg['account_key'], 'fx-'+leg['function'], 'configured native account address')
            totals[effect['currency'], leg['function']] += leg['debit_minor']-leg['credit_minor']
    for key, amount in expected.items():
        equal(totals[key], amount, 'native journal '+str(key))
    for currency in ('USD', 'EUR'):
        equal(sum(v for (cur, _), v in totals.items() if cur == currency), 0, currency+' book balances')
    return effects


def pairs(f):
    roots = f.api.all('/settlement-pairs')
    equal(len({r['id'] for r in roots}), len(roots), 'unique root pairs')
    retained = f.__dict__.setdefault('_fx_roots', {})
    require(set(retained) <= {r['id'] for r in roots}, 'executed root disappeared')
    metadata = ('id', 'key', 'customer_id', 'source_receipt_id', 'source_application_id',
                'document_id', 'item_key', 'source_currency', 'target_currency',
                'source_total_minor', 'target_total_minor', 'posting_date')
    for root in roots:
        require(all(k in root for k in metadata), 'root missing immutable public fields')
        content = {k: root[k] for k in metadata}
        equal(content, retained.setdefault(root['id'], copy.deepcopy(content)), 'immutable executed pair')
        S, T = root['source_total_minor'], root['target_total_minor']
        require(type(S) is int and type(T) is int and S > 0 and T > 0, 'positive integer root pair')
        cursor, cash = 0, 0
        for part in root['portions']:
            a, b = part['target_from_minor'], part['target_before_minor']
            equal(a, cursor, 'root partition gap or duplicate backing')
            require(type(b) is int and a < b <= T, 'root portion bounds')
            # Integer arithmetic here is an assertion of the public formula, not a billing oracle.
            rounded = lambda x: (2*S*x+T)//(2*T)
            equal(part['source_minor'], rounded(b)-rounded(a), 'retained root-coordinate cash')
            require(part['holder']['kind'] in ('application', 'credit', 'receipt', 'refund'), 'holder kind')
            require(isinstance(part['holder']['id'], str) and part['holder']['id'], 'holder identity')
            cash += part['source_minor']
            cursor = b
        equal((cursor, cash), (T, S), 'root conservation')
    for identity, expected in f.__dict__.get('_fx_refunds', {}).items():
        owned = [(r, p) for r in roots for p in r['portions']
                 if p['holder'] == dict(kind='refund', id=identity)]
        require(all(r['source_currency'] == expected['currency'] for r, _ in owned), 'refund cash currency')
        equal(sum(p['source_minor'] for _, p in owned), expected['cash'], 'named refund retains actual cash')
        equal(sum(p['target_before_minor']-p['target_from_minor'] for _, p in owned),
              expected['face'], 'named refund retains consumed credit face')
        require(all(p['document_id'] is None and p['item_key'] is None for _, p in owned), 'refund terminal links')
    return roots


def expect_pair(f, app, cash, doc, source, target, date):
    root = single([r for r in pairs(f) if r['source_application_id'] == app['id']], 'executed root')
    fields(root, dict(source_receipt_id=cash['id'], document_id=doc['id'], item_key=doc['items'][0]['key'],
                      customer_id=doc['customer_id'], source_currency=cash['currency'],
                      target_currency=doc['currency'], source_total_minor=source,
                      target_total_minor=target, posting_date=date), 'root matches actual accepted request')
    return root


def movement(f, root, kind, cash, face, date, previous=(), effects=None):
    rows = [e for e in (f.effects() if effects is None else effects)
            if e['id'] not in previous and e.get('settlement_pair_id') == root['id']
            and e['kind'] == kind]
    require(rows, 'missing linked '+kind)
    S, T = root['source_currency'], root['target_currency']
    require(S != T, 'cross movement requires distinct currencies')
    amounts, legs = defaultdict(int), defaultdict(int)
    for e in rows:
        equal((e['economic_date'], e['posting_date']), (date, date), 'cash movement dates')
        require(type(e['amount_minor']) is int and e['amount_minor'] >= 0, 'native movement amount')
        amounts[e['currency']] += e['amount_minor']
        for leg in e['legs']:
            legs[e['currency'], leg['function']] += leg['debit_minor']-leg['credit_minor']
    if cash == 0:
        amounts.setdefault(S, 0)
    equal(dict(amounts), {S: cash, T: face}, 'both native movement amounts')
    if kind in ('backing_release', 'backing_restore'):
        expected = {(S, 'settlement_clearing'): cash, (S, 'customer_funds'): -cash,
                    (T, 'customer_funds'): face, (T, 'settlement_clearing'): -face}
        sign = -1 if kind == 'backing_restore' else 1
    else:
        expected = {(S, 'customer_funds'): cash, (S, 'settlement_clearing'): -cash,
                    (T, 'settlement_clearing'): face, (T, 'receivable'): -face}
        sign = -1 if kind == 'funds_unapplication' else 1
    equal({k: v for k, v in legs.items() if v}, {k: sign*v for k, v in expected.items() if v},
          'native '+kind+' legs')


def held_cash(f, kind, identity, expected, currency='EUR'):
    values = [p for r in pairs(f) if r['source_currency'] == currency
              for p in r['portions'] if p['holder'] == dict(kind=kind, id=identity)]
    equal(sum(p['source_minor'] for p in values), expected, 'backing cash at named holder')
    for part in values:
        if kind == 'credit':
            equal((part['document_id'], part['item_key']), (identity, None), 'credit holder link')
        elif kind in ('refund', 'receipt'):
            equal((part['document_id'], part['item_key']), (None, None), 'terminal holder link')
        else:
            app = f.api.get('/applications/'+identifier(identity))
            require(any((a['document_id'], a['item_key']) == (part['document_id'], part['item_key'])
                        for a in app['allocations']), 'backing attached to wrong application item')
    return values


def snapshot(f):
    return copy.deepcopy(dict(documents=f.api.all('/documents'), receipts=f.api.all('/receipts'),
                              applications=f.api.all('/applications'), refunds=f.api.all('/refunds'),
                              effects=f.effects(), pairs=pairs(f)))


def prepare(f, currency='USD', legacy=False):
    chart(f, clearing=not legacy)
    buyer = f.customer()
    sub, first = invoice(f, buyer, '72', currency)
    _, second = invoice(f, buyer, '42', currency)
    return dict(buyer=buyer, sub=sub, first=first, second=second)


for debt_currency, cash_currency in (('USD', 'EUR'), ('EUR', 'USD')):
    @case('v04-fx-direct-'+debt_currency, 6, 'fx_pair_integrity', 'FX01 FX02 FX03',
          'Source cash and target debt differ; partial unapply restores the original pair')
    def direct(c, debt_currency=debt_currency, cash_currency=cash_currency):
        f = c.f
        h = prepare(f, debt_currency)
        cash = receipt(f, h['buyer'], currency=cash_currency)
        app, _ = pay(f, cash, h['first'], 5000, 6000)
        c.checkpoint('distinct-source-and-debt')
        fields(f.statement(h['buyer'], debt_currency), dict(ar_minor=5400), 'target debt')
        fields(f.statement(h['buyer'], cash_currency), dict(refundable_cash_minor=5000), 'source cash')
        held_cash(f, 'application', app['id'], 5000, cash_currency)
        # Another pair cannot change the first transaction's partial restoration.
        pay(f, cash, h['second'], 1000, 2000, date='2028-01-03')
        f.api.at('2028-01-04')
        chart(f, effective='2028-01-04', prefix='later')
        unapply(f, app, h['first'], 2400)
        c.checkpoint('retained-pair-unapplication')
        fields(f.statement(h['buyer'], debt_currency), dict(ar_minor=5800), 'restored target debt')
        fields(f.statement(h['buyer'], cash_currency), dict(refundable_cash_minor=6000), 'restored actual cash')
        held_cash(f, 'application', app['id'], 3000, cash_currency)
        effects = book(f, {(cash_currency, 'settlement_clearing'): -4000,
                           (debt_currency, 'settlement_clearing'): 5600})
        root = single([r for r in f.__dict__['_fx_roots'].values()
                       if r['source_application_id'] == app['id']], 'retained executed root')
        movement(f, root, 'funds_unapplication', 2000, 2400, '2028-02-02', effects=effects)


def anchor(c, reuse=False):
    f = c.f
    h = prepare(f)
    buyer, first, second = h['buyer'], h['first'], h['second']
    cash = receipt(f, buyer)
    app, _ = pay(f, cash, first, 5000, 6000)
    other, _ = pay(f, cash, second, 3500, 4200, date='2028-01-03')
    unapply(f, other, second, 4200, date='2028-01-04')
    f.api.at('2028-02-01')
    f.recognition('2028-01-31', '2028-02-01')
    f.create('/period-closes', month='2028-01')
    closed = {cur: f.report('2028-01', currency=cur) for cur in ('USD', 'EUR')}
    old_effects = {e['id']: e for e in f.effects()}
    c.checkpoint('credit-release-after-close')
    credits = price(f, h['sub'], '36')
    root = single([r for r in pairs(f) if r['source_application_id'] == app['id']], 'original root')
    movement(f, root, 'backing_release', 2000, 2400, '2028-02-02', old_effects)
    document_totals(credits, [('credit', 3600)])
    credit = single(credits, 'correction credit')
    fields(credit, dict(available_backed_minor=2400), 'credit face distinct from cash')
    held_cash(f, 'credit', credit['id'], 2000)
    held_cash(f, 'application', app['id'], 3000)
    fields(f.statement(buyer, 'EUR'), dict(refundable_cash_minor=7000), 'no duplicated cash backing')
    fields(f.statement(buyer), dict(ar_minor=4200, available_backed_minor=2400,
                                     refundable_cash_minor=0), 'native credit face')
    before = snapshot(f)
    f.api.error('POST', '/applications/'+identifier(app['id'])+'/unapply',
                dict(allocations=[allocation(first, 6000)], posting_date='2028-02-02'),
                422, 'prerequisite_failed', version=f.api.get('/applications/'+identifier(app['id']))['version'])
    equal(snapshot(f), before, 'locked backing rejection is atomic')
    if reuse:
        c.checkpoint('credit-reuse-is-not-a-new-exchange')
        use, _ = pay(f, credit, second, None, 2400, kind='credit', date='2028-02-02')
        fields(f.statement(buyer), dict(ar_minor=1800, available_backed_minor=0), 'face pays second invoice')
        held_cash(f, 'application', use['id'], 2000)
        unapply(f, use, second, 1200, date='2028-02-03')
        held_cash(f, 'credit', credit['id'], 1000)
        fields(f.statement(buyer), dict(ar_minor=3000, available_backed_minor=1200), 'credit restored, not receipt')
        refund(f, credit, 1000, 1200, date='2028-02-03')
        expected_ar, refunded, clearing_eur, clearing_usd = 6600, 1000, -4000, 4800
    else:
        c.checkpoint('refund-original-cash')
        refund(f, credit, 2000, 2400)
        expected_ar, refunded, clearing_eur, clearing_usd = 7800, 2000, -3000, 3600
    c.checkpoint('second-correction-preserves-spent-value')
    additions = price(f, h['sub'], '72', date='2028-02-04')
    document_totals(additions, [('debit', 3600)])
    fields(f.statement(buyer), dict(ar_minor=expected_ar), 'new debt after actual refund')
    fields(f.statement(buyer, 'EUR'), dict(cash_received_minor=10000, cash_refunded_minor=refunded,
                                            refundable_cash_minor=5000), 'cash after second correction')
    book(f, {('EUR', 'cash'): 10000-refunded, ('EUR', 'settlement_clearing'): clearing_eur,
             ('USD', 'settlement_clearing'): clearing_usd, ('USD', 'receivable'): expected_ar,
             ('USD', 'service_revenue'): -11400})
    for cur in closed:
        closed_unchanged(closed[cur], f.report('2028-01', currency=cur))
    for e in f.effects():
        if e['id'] in old_effects:
            equal(e, old_effects[e['id']], 'old effect immutable')
        elif e['currency'] == 'EUR':
            equal(e['economic_date'], e['posting_date'], 'all new foreign cash effects are current dated')
        elif e['kind'] == 'recognition':
            equal(e['economic_date'], '2028-01-01', 'one-time economic date')
            equal(e['scope_key'], first['items'][0]['scope_key'], 'per-unit correction')
        elif e['kind'] in ('backing_release', 'funds_application', 'funds_unapplication', 'refund'):
            equal(e['economic_date'], e['posting_date'], 'cash movement date')
    immutable_document(first, f.api.get('/documents/'+identifier(first['id'])))


case('v04-fx-correct-refund-restore', 6, 'fx_history', 'FX04 FX05 FX06 FX07',
     'Closed invoice correction refunds actual foreign cash; later debit preserves refund')(anchor)
case('v04-fx-credit-reuse-unapply', 6, 'fx_credit_provenance', 'FX04 FX05 FX06',
     'Foreign backing follows native-face credit reuse and partial unapplication')(lambda c: anchor(c, True))


@case('v04-fx-mixed-backing', 6, 'fx_credit_provenance', 'FX04 FX05',
      'One credit owns EUR and USD backing; refund selection cannot fabricate a conversion')
def mixed(c):
    f = c.f
    h = prepare(f)
    usd = receipt(f, h['buyer'], 2400, 'USD')
    pay(f, usd, h['first'], None, 2400)
    eur = receipt(f, h['buyer'], 4000)
    pay(f, eur, h['first'], 4000, 4800, date='2028-01-03')
    credit = memo(f, h['buyer'], h['first'], 7200)
    held_cash(f, 'credit', credit['id'], 4000)
    held_cash(f, 'credit', credit['id'], 2400, 'USD')
    c.checkpoint('currency-selected-credit-refunds')
    before = snapshot(f)
    f.api.error('POST', '/refunds', dict(key='wrong-cash', source=dict(kind='credit', id=credit['id']),
                currency='EUR', amount_minor=4800, credit_amount_minor=4800, posting_date='2028-02-02'),
                422, 'invalid_domain')
    equal(snapshot(f), before, 'wrong refund pair changed state')
    refund(f, credit, 4000, 4800)
    refund(f, credit, 2400, 2400, 'USD')
    fields(f.statement(h['buyer']), dict(ar_minor=4200, available_backed_minor=0,
                                         cash_refunded_minor=2400, refundable_cash_minor=0), 'USD face/cash')
    fields(f.statement(h['buyer'], 'EUR'), dict(cash_refunded_minor=4000, refundable_cash_minor=0), 'EUR cash')
    book(f, {('EUR', 'settlement_clearing'): 0, ('USD', 'settlement_clearing'): 0})


@case('v04-fx-nested-rounding', 6, 'fx_rounding', 'FX03 FX04 FX05',
      'Repeated releases and a split reused portion retain root coordinates and every cent')
def rounding(c):
    f = c.f
    chart(f)
    buyer = f.customer()
    _, first = invoice(f, buyer, '57.13')
    _, second = invoice(f, buyer, '30')
    cash = receipt(f, buyer, 5000)
    pay(f, cash, first, 5000, 5713)
    credits = []
    for face, cash_amount in ((1904, 1666), (1904, 1667), (1905, 1667)):
        credit = memo(f, buyer, first, face)
        held_cash(f, 'credit', credit['id'], cash_amount)
        credits.append(credit)
    c.checkpoint('split-child-with-original-coordinates')
    app, _ = pay(f, credits[-1], second, None, 948, kind='credit', date='2028-02-02')
    held_cash(f, 'application', app['id'], 829)
    held_cash(f, 'credit', credits[-1]['id'], 838)
    unapply(f, app, second, 948)
    held_cash(f, 'credit', credits[-1]['id'], 1667)
    before = snapshot(f)
    f.api.error('POST', '/refunds', dict(key='one-cent-short', source=dict(kind='credit', id=credits[1]['id']),
        currency='EUR', amount_minor=1666, credit_amount_minor=1904, posting_date='2028-02-02'), 422, 'invalid_domain')
    equal(snapshot(f), before, 'one-cent refund mismatch is atomic')
    for credit, face, amount in zip(credits, (1904, 1904, 1905), (1666, 1667, 1667)):
        refund(f, credit, amount, face)
    fields(f.statement(buyer, 'EUR'), dict(cash_refunded_minor=5000, refundable_cash_minor=0), 'all residual cents returned')
    fields(f.statement(buyer), dict(ar_minor=3000, available_backed_minor=0), 'credit not duplicated')
    pairs(f)


@case('v04-fx-release-then-unapply', 6, 'fx_rounding', 'FX03 FX04',
      'Latest settlement releases lowest coordinates; only the highest unlocked slice is unapplied')
def release_then_unapply(c):
    f = c.f
    chart(f)
    buyer = f.customer()
    _, doc = invoice(f, buyer, '77.13')
    native = receipt(f, buyer, 2000, 'USD')
    pay(f, native, doc, None, 2000)
    cash = receipt(f, buyer, 5000)
    app, _ = pay(f, cash, doc, 5000, 5713, date='2028-01-03')
    credit = memo(f, buyer, doc, 2400)
    held_cash(f, 'credit', credit['id'], 2100)
    held_cash(f, 'credit', credit['id'], 0, 'USD')
    c.checkpoint('unapply-only-highest-unlocked-coordinates')
    unapply(f, app, doc, 1200)
    held_cash(f, 'application', app['id'], 1850)
    held_cash(f, 'receipt', cash['id'], 1050)
    fields(f.statement(buyer, 'EUR'), dict(refundable_cash_minor=3150), 'exact released and restored cash')
    fields(f.statement(buyer), dict(ar_minor=1200, available_backed_minor=2400), 'face stays distinct')
    book(f, {('EUR', 'cash'): 5000, ('EUR', 'customer_funds'): -3150,
             ('EUR', 'settlement_clearing'): -1850, ('USD', 'cash'): 2000,
             ('USD', 'receivable'): 1200, ('USD', 'customer_funds'): 0,
             ('USD', 'contract_position'): -5313, ('USD', 'settlement_clearing'): 2113})


@case('v04-fx-atomic-validation', 6, 'fx_atomicity', 'FX01 FX08',
      'One invalid allocation cannot partially settle either book or leak another customer')
def atomic(c):
    f = c.f
    h = prepare(f)
    cash = receipt(f, h['buyer'])
    stranger = f.customer('other')
    _, foreign = invoice(f, stranger)
    f.api.at('2028-01-02')
    for target in (allocation(h['second'], 4201, 3000), allocation(foreign, 1200, 1000)):
        before = snapshot(f)
        body = dict(key=f.key('invalid'), source=dict(kind='receipt', id=cash['id']),
                    allocations=[allocation(h['first'], 6000, 5000), target], posting_date='2028-01-02')
        response = f.api.request('POST', '/applications', body, status=(404, 422))
        require(response.get('error', {}).get('code') in ('not_found', 'invalid_domain'), 'invalid allocation error')
        equal(snapshot(f), before, 'partial multi-allocation mutation')
    c.checkpoint('rejected-requests-did-not-consume-cash')
    app, _ = pay(f, cash, h['first'], 5000, 6000)
    held_cash(f, 'application', app['id'], 5000)
    _, euro_doc = invoice(f, h['buyer'], '72', 'EUR')
    credit = memo(f, h['buyer'], h['first'], 2400)
    # Each source/target has enough available value; only the requested shape is invalid.
    credit_source = dict(kind='credit', id=credit['id'])
    receipt_source = dict(kind='receipt', id=cash['id'])
    invalid = [
        ('/applications', dict(source=credit_source, allocations=[allocation(h['second'], 1000, 999)]), 422),
        ('/applications', dict(source=credit_source, allocations=[allocation(euro_doc, 1000)]), 422),
        ('/applications', dict(source=receipt_source, allocations=[allocation(euro_doc, 1000, 999)]), 422),
        ('/applications', dict(source=receipt_source, allocations=[allocation(h['second'], 100, 50)]*2), 400),
        ('/refunds', dict(source=receipt_source, amount_minor=100, currency='USD'), 422),
        ('/refunds', dict(source=receipt_source, amount_minor=100, currency='EUR', credit_amount_minor=100), 422),
    ]
    c.checkpoint('invalid-request-shapes-with-sufficient-balances')
    for path, body, status in invalid:
        before = snapshot(f)
        f.api.error('POST', path, dict(body, key=f.key('bad-shape'), posting_date='2028-02-02'),
                    status, 'invalid_request' if status == 400 else 'invalid_domain')
        equal(snapshot(f), before, 'invalid FX shape changed economics')
    hidden = f.api.actor(role='customer', customer=stranger['id'])
    response = hidden.request('GET', '/settlement-pairs?source_receipt_id='+identifier(cash['id']), status=(200, 403, 404))
    if 'data' in response:
        equal(response['data'], [], 'foreign backing leaked')


@case('v04-fx-held-replay-restart', 6, 'fx_atomicity', 'FX07 FX08 FX09',
      'Missing clearing holds both books; repair, replay and restart preserve one executed pair')
def held(c):
    if c.runtime is None:
        raise RuntimeError('restart case requires a process runtime')
    f = c.f
    h = prepare(f, legacy=True)
    cash = receipt(f, h['buyer'])
    before = snapshot(f)
    body = dict(key='held-pay', source=dict(kind='receipt', id=cash['id']),
                allocations=[allocation(h['first'], 6000, 5000)], posting_date='2028-01-03')
    f.api.at('2028-01-03')
    r = f.api.request('POST', '/applications', body, status=200, key='attempt-1')
    equal(r['operation']['status'], 'held', 'missing clearing hold')
    require(any(i['code'] == 'missing_configuration' for i in r['operation']['issues']), 'held reason')
    after = snapshot(f)
    for name in ('documents', 'receipts', 'effects', 'pairs', 'refunds'):
        equal(after[name], before[name], 'held '+name)
    chart(f, effective='2028-01-03', prefix='fixed')
    c.checkpoint('retry-whole-pair-after-configuration')
    accepted = f.api.request('POST', '/applications', body, status=201, key='attempt-2')
    f.api.completed(accepted, 'held retry')
    saved = snapshot(f)
    c.runtime.restart()
    f.api.at('2028-02-04')
    equal(f.api.request('POST', '/applications', body, status=201, key='attempt-2'), accepted, 'exact saved response replay')
    equal(snapshot(f), saved, 'restart/replay duplicated pair')
    changed = copy.deepcopy(body)
    changed['allocations'][0]['source_amount_minor'] = 4999
    f.api.error('POST', '/applications', changed, 409, 'idempotency_conflict', key='attempt-2')
    equal(snapshot(f), saved, 'changed-pair replay altered economics')


@case('v04-fx-competing-applications', 6, 'fx_atomicity', 'FX08',
      'Competing foreign allocations serialize in source cash units, not debt units')
def competing(c):
    f = c.f
    h = prepare(f)
    cash = receipt(f, h['buyer'], 1000)
    def attempt(key):
        return f.api.actor().request('POST', '/applications', dict(key=key,
            source=dict(kind='receipt', id=cash['id']), allocations=[allocation(h['first'], 720, 600)],
            posting_date='2028-01-02'), status=(200, 201, 409, 422))
    c.checkpoint('competing-source-cash')
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(attempt, ('race-a', 'race-b')))
    equal(sum(r.get('operation', {}).get('status') == 'completed' for r in responses), 1, 'one pair commits')
    equal(sum(r.get('error', {}).get('code') in ('invalid_domain', 'prerequisite_failed', 'stale_version')
              for r in responses), 1, 'one pair rejects')
    fields(f.statement(h['buyer']), dict(ar_minor=10680), 'one debt reduction')
    fields(f.statement(h['buyer'], 'EUR'), dict(refundable_cash_minor=400), 'source remainder')
    pay(f, cash, h['second'], 400, 480)
    fields(f.statement(h['buyer']), dict(ar_minor=10200), 'legitimate remainder usable')
    book(f, {('EUR', 'settlement_clearing'): -1000, ('USD', 'settlement_clearing'): 1200})
    pairs(f)


@case('v04-fx-termination', 6, 'fx_agreement_integration', 'FX04 FX05 FX07',
      'Termination releases foreign backing from original deal invoice and preserves earned service')
def termination(c):
    f = c.f
    chart(f)
    buyer, product = f.customer(), f.product()
    d = deal(f, buyer, 3100, [promise('service', product, end='2028-02-01')],
             [installment('bill', '2028-01-01', 3100, 'service')])
    _, docs = f.bill('2028-01-01', '2028-01-01')
    doc = single(docs, 'deal invoice')
    cash = receipt(f, buyer, 2480)
    app, _ = pay(f, cash, doc, 2480, 3100)
    f.api.at('2028-01-16')
    f.recognition('2028-01-15', '2028-01-16')
    body = dict(key='terminate', scope_key=d['scope_keys']['promises']['service'],
                effective_on='2028-01-16', retained_price_minor=1500, termination_fee=None)
    term = f.api.action('/deals/'+identifier(d['id'])+'/terminations', body)['data']
    c.checkpoint('termination-cross-backed-credit')
    f.api.action('/terminations/'+identifier(term['id'])+'/apply', dict(posting_date='2028-01-16'))
    # Billing the derived delta is the ordinary M4 workflow.
    f.bill('2028-01-16', '2028-01-16')
    credit = single([x for x in f.api.all('/documents') if x['kind'] == 'credit'], 'termination credit')
    equal(credit['total_minor'], 1600, 'unperformed service credit')
    held_cash(f, 'credit', credit['id'], 1280)
    held_cash(f, 'application', app['id'], 1200)
    refund(f, credit, 1280, 1600, date='2028-01-16')
    book(f, {('USD', 'service_revenue'): -1500, ('USD', 'settlement_clearing'): 1500,
             ('EUR', 'settlement_clearing'): -1200, ('EUR', 'cash'): 1200})


def prepare_legacy(f, currency):
    h = prepare(f, currency, legacy=True)
    cash = receipt(f, h['buyer'], 2400, currency)
    app, _ = pay(f, cash, h['first'], None, 2400)
    saved_operation = copy.deepcopy(f.api.trace[-1])
    archive_buyer = f.customer('historical-customer')
    archive_sub, archive_doc = invoice(f, archive_buyer, '120', currency)
    archive_cash = receipt(f, archive_buyer, 12000, currency, date='2028-01-03')
    archive_app, _ = pay(f, archive_cash, archive_doc, None, 12000, date='2028-01-03')
    archive_credit = memo(f, archive_buyer, archive_doc, 3000, date='2028-01-04')
    f.api.at('2028-01-05')
    archive_refund = f.create('/refunds', source=dict(kind='credit', id=archive_credit['id']),
                              amount_minor=1000, posting_date='2028-01-05')
    unapply(f, archive_app, archive_doc, 2000, date='2028-01-06')
    price(f, archive_sub, '100', date='2028-01-07')
    f.api.at('2028-02-01')
    f.recognition('2028-01-31', '2028-02-01')
    f.create('/period-closes', month='2028-01')
    h.update(currency=currency, cash=cash, app=app, old_documents=copy.deepcopy(f.api.all('/documents')),
             old_effects=f.effects(), closed=f.report('2028-01', currency=currency),
             old_statement=f.statement(h['buyer'], currency),
             old_application=f.api.get('/applications/'+identifier(app['id'])),
             saved_operation=saved_operation, archive_buyer=archive_buyer,
             archive_statement=f.statement(archive_buyer, currency), archive_cash=archive_cash,
             archive_credit=archive_credit, archive_app=archive_app, archive_refund=archive_refund)
    return h


def resume_legacy(c, h):
    f = c.f
    c.checkpoint('old-state-survives-upgrade')
    for doc in h['old_documents']:
        immutable_document(doc, f.api.get('/documents/'+identifier(doc['id'])))
    actual = {e['id']: e for e in f.effects()}
    old = {e['id']: e for e in h['old_effects']}
    equal(set(actual), set(old), 'upgrade changed effect population')
    retained_projection(actual, old, 'upgrade rewrote posted effects')
    retained_projection(f.statement(h['buyer'], h['currency']), h['old_statement'], 'legacy statement values')
    retained_projection(f.api.get('/applications/'+identifier(h['app']['id'])), h['old_application'], 'old application counters')
    request = h['saved_operation']
    f.api.at('2028-02-02')
    replay = f.api.request('POST', '/applications', request['body'], key=request['idempotency_key'], status=201)
    retained_response(replay, request['response'], 'pre-upgrade saved application response')
    retained_projection(f.statement(h['archive_buyer'], h['currency']), h['archive_statement'], 'M5 corrected/refunded state')
    for kind, resource, amount in (('application', h['archive_app'], 7000), ('credit', h['archive_credit'], 2000),
                                    ('receipt', h['archive_cash'], 2000), ('refund', h['archive_refund'], 1000)):
        held_cash(f, kind, resource['id'], amount, h['currency'])
    closed_unchanged(h['closed'], f.report('2028-01', currency=h['currency']))
    chart(f, effective='2028-02-02')
    other = 'EUR' if h['currency'] == 'USD' else 'USD'
    cash = receipt(f, h['buyer'], 4000, other, date='2028-02-02')
    app, _ = pay(f, cash, h['first'], 4000, 4800, date='2028-02-02')
    c.checkpoint('old-invoice-new-pair-correction')
    credit = single(price(f, h['sub'], '36', date='2028-02-03'), 'upgrade credit')
    held_cash(f, 'credit', credit['id'], 3000, other)
    held_cash(f, 'application', app['id'], 1000, other)
    refund(f, credit, 3000, 3600, other, date='2028-02-03')
    fields(f.statement(h['buyer'], h['currency']), dict(ar_minor=4200, available_backed_minor=0), 'old native debt')
    fields(f.statement(h['buyer'], other), dict(cash_refunded_minor=3000), 'new foreign refund')
    closed_unchanged(h['closed'], f.report('2028-01', currency=h['currency']))
    identity = single([r for r in pairs(f) if r['source_application_id'] == h['app']['id']], 'legacy identity pair')
    equal((identity['source_total_minor'], identity['target_total_minor']), (2400, 2400), 'old pair default')


@case('v04-fx-credit-compensation', 6, 'fx_credit_provenance', 'FX04 FX05 FX07',
      'Compensation restores original backing ownership and unlocks the original receipt application')
def compensate(c):
    f = c.f
    h = prepare(f)
    cash = receipt(f, h['buyer'], 6000)
    app, _ = pay(f, cash, h['first'], 6000, 7200)
    credit = memo(f, h['buyer'], h['first'], 3600)
    held_cash(f, 'credit', credit['id'], 3000)
    root = single([r for r in pairs(f) if r['source_application_id'] == app['id']], 'compensation root')
    before = {e['id'] for e in f.effects()}
    f.api.at('2028-02-03')
    c.checkpoint('restore-backing-not-another-exchange')
    f.api.action('/documents/'+identifier(credit['id'])+'/compensate',
                 dict(key='neutralize', posting_date='2028-02-03'))
    movement(f, root, 'backing_restore', 3000, 3600, '2028-02-03', before)
    held_cash(f, 'application', app['id'], 6000)
    held_cash(f, 'credit', credit['id'], 0)
    fields(f.statement(h['buyer']), dict(ar_minor=4200, available_backed_minor=0), 'compensating debit cleared once')
    book(f, {('EUR', 'settlement_clearing'): -6000, ('USD', 'settlement_clearing'): 7200})
    unapply(f, app, h['first'], 7200, date='2028-02-04')
    fields(f.statement(h['buyer'], 'EUR'), dict(refundable_cash_minor=6000), 'original application unlocked')
