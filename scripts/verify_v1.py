#!/usr/bin/env python3
"""Verify packaged sources and published results without running candidates."""
import ast
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import statistics
import sys
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class AssetReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and 'src' in attrs:
            self.assets.append(attrs['src'])
        elif tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.assets.append(attrs['href'])


references = AssetReferences()
references.feed((ROOT / 'site/index.html').read_text())
assert {urlsplit(url).path for url in references.assets} == {'data.js', 'report.js', 'style.css'}
for url in references.assets:
    asset = urlsplit(url)
    digest = hashlib.sha256((ROOT / 'site' / asset.path).read_bytes()).hexdigest()[:12]
    assert parse_qs(asset.query).get('v') == [digest], f'Update index.html asset URL to {asset.path}?v={digest}'

package = ROOT / 'benchmark/v1'
manifest = json.loads((package / 'SOURCE_MANIFEST.json').read_text())
for relative, expected in manifest['sha256'].items():
    assert hashlib.sha256((package / relative).read_bytes()).hexdigest() == expected, relative
for path in package.rglob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
sys.path.insert(0, str(package / 'evaluation/0.5'))
from billing_eval.selection import SELECTED
assert len(SELECTED) == 123
assert set(c.milestone for c in SELECTED.values()) == {1, 2, 3, 4, 5}
data = json.loads((ROOT / 'site/results.json').read_text())
script = (ROOT / 'site/data.js').read_text()
assert json.loads(script.removeprefix('window.BILLING_RESULTS = ').rstrip(';\n')) == data
expected = {'astra-low-01': (108,18), 'astra-low-02': (103,18), 'astra-low-03': (115,20),
            'astra-xhigh-01': (114,20), 'sol6-xhigh-01': (99,14), 'sol6-xhigh-02': (73,14),
            'sol6-xhigh-03': (89,20), 'sol6-low-01': (76,11)}
assert set(r['id'] for r in data['runs']) == set(expected)
for run in data['runs']:
    assert (run['passed'], run['retained_passed']) == expected[run['id']]
    assert {c['key'] for c in run['cases']} == set(SELECTED)
    assert sum(c['status']=='passed' for c in run['cases']) == run['passed']
    assert len(run['retained']) == 20
    assert sum(c['status']=='passed' for c in run['retained']) == run['retained_passed']
    assert abs(sum(r['seconds'] for r in run['releases']) - run['seconds']) < .001
    for category in ('production', 'test'):
        assert sum(f['lines'] for f in run['code']['files'] if f['category']==category) == run['code'][category]
    assert run['usage']['boundary_verified']
    assert run['usage']['cached_input_tokens'] <= run['usage']['input_tokens']
    assert run['usage']['long_requests'] == 0
    price_in, price_cache, price_out = data['pricing']['rates'][run['model']]
    usage = run['usage']
    usd = ((usage['input_tokens'] - usage['cached_input_tokens'])*price_in +
           usage['cached_input_tokens']*price_cache + usage['output_tokens']*price_out)/1e6
    assert abs(usd-usage['api_equivalent_usd']) < 1e-7
    assert not any('/Users/' in str(v) for v in run.values())
for path in (ROOT / 'site').rglob('*'):
    if path.is_file() and path.suffix in ('.js', '.json', '.html', '.css'):
        text = path.read_text()
        assert '/Users/' not in text and 'Bearer eyJ' not in text, path
print(f'Verified {len(manifest["sha256"])} original source hashes, 123 cases, eight runs, totals, code metrics and prices.')
