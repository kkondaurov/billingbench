#!/usr/bin/env python3
"""Public shape/default smoke checks. Creates one disposable tenant; no economic oracle."""
import argparse
import base64
import hashlib
import hmac
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import quote
import uuid


def bearer(secret, tenant=None, role='admin'):
    raw = json.dumps(dict(tenant_id=tenant, role=role, customer_id=None), separators=(',', ':')).encode()
    payload = base64.urlsafe_b64encode(raw).rstrip(b'=')
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()).rstrip(b'=')
    return (payload + b'.' + signature).decode()


def mutation(body):
    assert isinstance(body, dict) and isinstance(body.get('data'), dict), 'missing resource'
    resource = body['data']
    assert isinstance(resource.get('id'), str) and resource['id'], 'opaque resource id'
    assert isinstance(resource.get('key'), str), 'resource key'
    assert type(resource.get('version')) is int and resource['version'] > 0, 'resource version'
    operation = body.get('operation', {})
    assert isinstance(operation.get('id'), str), 'operation id'
    assert operation.get('status') == 'completed', 'operation did not complete'
    assert isinstance(operation.get('issues'), list) and isinstance(operation.get('effects'), list), 'operation lists'
    return resource


def run(base, secret):
    tenant = None

    def request(method, path, body=None, key=None, version=None, business_time='2028-01-01T12:00:00Z'):
        absolute = path.startswith('/api/') or path == '/health'
        route = path if absolute else '/api/tenants/' + quote(tenant, safe='') + path
        headers = {'Authorization': 'Bearer ' + bearer(secret, tenant, 'platform_admin' if tenant is None else 'admin')}
        if body is not None:
            headers.update({'Content-Type': 'application/json', 'Idempotency-Key': key or uuid.uuid4().hex,
                            'X-Business-Time': business_time})
        if version is not None:
            headers['If-Match'] = str(version)
        req = Request(base.rstrip('/') + route, headers=headers, method=method,
                      data=json.dumps(body).encode() if body is not None else None)
        try:
            response = urlopen(req, timeout=30)
        except HTTPError as exc:
            response = exc
        result = json.loads(response.read())
        assert response.status in (200, 201), (method, path, response.status, result)
        return result

    assert request('GET', '/health').get('status') == 'ok', 'health response'
    name = 'public-smoke-' + uuid.uuid4().hex[:12]
    tenant = mutation(request('POST', '/api/tenants', dict(key=name, name=name, defaults={}, grouping='payer')))['id']
    payload = dict(key='customer', name='Customer', parent_id=None, attrs={})
    customer = mutation(request('POST', '/customers', payload, key='customer-create'))
    again = mutation(request('POST', '/customers', payload, key='customer-create'))
    assert customer['id'] == again['id'], 'replay changed resource identity'
    listed = request('GET', '/customers?limit=1')
    assert isinstance(listed.get('data'), list) and 'next_cursor' in listed, 'collection shape'
    assert listed['next_cursor'] is None or isinstance(listed['next_cursor'], str), 'cursor shape'
    functions = dict(cash='asset', receivable='asset', customer_funds='liability',
                     contract_position='asset', service_revenue='revenue')
    chart = dict(key='accounts', effective_from='2028-01-01', position_mode='clearing',
                 correction_routing='original', segments=[], lookups=[],
                 accounts=[dict(key=k, name=k, **{'class': v}, parent_key=None, posting=True,
                                starts_on='2020-01-01', ends_before=None, required_segments=[]) for k, v in functions.items()],
                 rules=[dict(key=k, function=k, priority=1, when={'all': []}, distribution=[
                     dict(key='whole', weight='100', account={'constant': k}, segments={})]) for k in functions])
    config = mutation(request('POST', '/accounting-configurations', chart))
    config_path = '/accounting-configurations/'+quote(config['id'], safe='')
    mutation(request('POST', config_path+'/publish', {}, version=config['version']))
    product = mutation(request('POST', '/products', dict(key='product', name='Service', attrs={})))
    options = dict(model='flat', price='1', quantity='1', included='0', minimum_minor=None,
                   maximum_minor=None, period=dict(months=1, anchor='day', day=1), billing='advance',
                   trigger=dict(kind='contract', date=None), recognition='stand_ready')
    catalog = mutation(request('POST', '/catalogs', dict(key='catalog', effective_from='2028-01-01', defaults={},
        price_lookups=[], plans=[dict(key='plan', name='Plan', charges=[dict(key='charge', product_id=product['id'],
        kind='recurring', options=options, overridable=[], lookup_key=None)])])))
    mutation(request('POST', '/catalogs/'+quote(catalog['id'], safe='')+'/publish', {}, version=catalog['version']))
    sub = mutation(request('POST', '/subscriptions', dict(key='sub', customer_id=customer['id'], currency='USD',
        starts_on='2028-01-01', ends_before='2028-02-01', renewal_months=None,
        plans=[dict(catalog_id=catalog['id'], plan_key='plan', overrides={})], attrs={})))
    sub_path = '/subscriptions/'+quote(sub['id'], safe='')
    mutation(request('POST', sub_path+'/accept', {}, version=sub['version']))
    # Evidence creates a nested record, rather than updating the subscription.
    mutation(request('POST', sub_path+'/evidence', dict(key='activation', charge_key='charge',
                                                       kind='activation', effective_on='2028-01-01')))
    deal = mutation(request('POST', '/deals', dict(key='deal', customer_id=customer['id'], currency='USD', attrs={},
        groups=[dict(key='group', price_minor=100, promises=[dict(key='promise', product_id=product['id'],
            kind='stand_ready', ssp='1', window=dict(starts_on='2028-01-01', ends_before='2028-02-01'),
            activation_on='2028-01-01', approved_total=None, attrs={})])], installments=[dict(key='first',
            billable_on='2028-01-01', items=[dict(key='item', group_key='group', promise_key='promise', amount_minor=100)])])))
    deal_path = '/deals/'+quote(deal['id'], safe='')
    mutation(request('POST', deal_path+'/accept', {}, version=deal['version']))
    scopes = request('GET', deal_path)['data']['scope_keys']
    assert isinstance(scopes.get('groups'), dict) and isinstance(scopes.get('promises'), dict), 'deal scope maps'
    assert isinstance(scopes['groups'].get('group'), str) and isinstance(scopes['promises'].get('promise'), str), 'deal scope identifiers'
    run = mutation(request('POST', '/bill-runs', dict(key='run', customer_ids=[customer['id']],
        target_date='2028-01-01', invoice_date='2028-01-01', posting_date='2028-01-01')))
    run_path = '/bill-runs/'+quote(run['id'], safe='')
    mutation(request('POST', run_path+'/post', dict(result_keys=None), version=run['version']))
    current = request('GET', run_path)['data']
    results = [current] if 'scopes' in current else [request('GET', '/billing-results/'+quote(i, safe=''))['data']
                                                   for i in current['result_ids']]
    ids = {i for result in results for scope in result['scopes'] for i in scope['document_ids']}
    assert ids, 'bill-run scope document links'
    documents = [request('GET', '/documents/'+quote(i, safe=''))['data'] for i in sorted(ids)]
    doc, item = next((d, i) for d in documents for i in d['items'] if i.get('subscription_id') == sub['id'])
    memo = mutation(request('POST', '/memos', dict(key='memo', kind='credit', customer_id=customer['id'],
        currency='USD', invoice_date='2028-01-01', posting_date='2028-01-01', items=[dict(key='line',
            document_id=doc['id'], item_key=item['key'], amount_minor=1, reason='Smoke')])) )
    memo_id = memo.get('document_id', memo['id'])
    draft = request('GET', '/documents/'+quote(memo_id, safe=''))['data']
    assert draft['kind'] == 'credit' and draft['status'] == 'draft', 'memo document link'
    print('Public protocol/default smoke checks passed. Financial behavior has not been evaluated.')
    return dict(request=request, customer=customer, deal=request('GET', deal_path)['data'],
                subscription=sub, documents=documents, chart=chart,
                published_configuration=request('GET', config_path)['data'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--secret', required=True)
    args = parser.parse_args()
    run(args.base_url, args.secret)
