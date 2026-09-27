"""Public M4 route and published-scope interoperability check; no private oracle."""
import argparse
from urllib.parse import quote
from smoke import run, mutation


def check(base, secret):
    state = run(base, secret)
    request, deal = state['request'], state['deal']
    body = dict(key='termination-smoke', scope_key=deal['scope_keys']['promises']['promise'],
                effective_on='2028-01-01', retained_price_minor=0, termination_fee=None)
    path = '/deals/'+quote(deal['id'], safe='')
    preview = request('POST', path+'/termination-preview', body)
    assert isinstance(preview['data']['issues'], list), 'agreement preview issues'
    agreement = mutation(request('POST', path+'/terminations', body, version=deal['version']))
    saved = request('GET', '/terminations/'+quote(agreement['id'], safe=''))['data']
    assert saved['id'] == agreement['id'], 'agreement route identity'
    print('Public agreement route/scope checks passed; no economic result asserted.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url', required=True)
    p.add_argument('--secret', required=True)
    a = p.parse_args()
    check(a.base_url, a.secret)
