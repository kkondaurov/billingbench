#!/usr/bin/env python3
"""Verify packaged sources and published results without running candidates."""
import ast
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
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
assert (data['version'], data['evaluator'], data['protocol']) == ('1.6.0', 'R4', 'fresh-session-per-release')
assert data['qualification']['jobs'] == 162 and data['qualification']['evaluator_exceptions'] == 13
assert data['qualification']['execution_failures'] == 0
expected = {'astra-low-01': 110, 'astra-low-02': 117, 'astra-low-03': 105,
            'sol6-xhigh-01': 88, 'sol6-xhigh-02': 78, 'sol6-xhigh-03': 71,
            'luna6-xhigh-01': 43, 'luna6-xhigh-02': 30, 'luna6-xhigh-03': 47,
            'opus55-xhigh-01': 107, 'sol61-xhigh-01': 109, 'sol61-xhigh-02': 111, 'sol61-xhigh-03': 110, 'opus55-xhigh-02': 105,
            'deepseek41-high-01': 50, 'deepseek41-high-02': 12, 'deepseek41-high-03': 58}
for n, score in enumerate((102, 112, 109), 1):
    expected[f'terra61-strict-xhigh-{n:02}'] = 1
    expected[f'terra61-assisted-xhigh-{n:02}'] = score
assert set(r['id'] for r in data['runs']) == set(expected)
all_runs = data['runs'] + data['supplementary_runs']
for n, score in enumerate((37,43,35),1): expected[f'terra61-m1-assisted-xhigh-{n:02}'] = score
receipts = json.loads((ROOT / 'site/EVALUATION_R4.json').read_text())
assert (receipts['version'], receipts['evaluator']) == ('1.6.0', 'R4')
assert receipts['source_manifest_sha256'] == hashlib.sha256((package / 'SOURCE_MANIFEST.json').read_bytes()).hexdigest()
jobs = {(j['lane'], j['kind'], j['milestone']): j for j in receipts['jobs']}
assert len(jobs) == len(receipts['jobs']) == 162
assert set(jobs) == ({(r['id'], 'api', n) for r in data['runs'] for n in range(1,6)} |
    {(r['id'], 'retained', 5) for r in all_runs} |
    {(r['id'], 'api', n) for r in data['supplementary_runs'] for n in range(2,6)} |
    {(f'terra61-before-r{n}-{i:02}', 'api', n) for i in range(1,4) for n in (3,4,5)})
checksums = json.loads((ROOT / 'site/RELEASE_SHA256.json').read_text())
for name in ('results.json', 'EVALUATION_R4.json'):
    assert checksums[name] == hashlib.sha256((ROOT / 'site' / name).read_bytes()).hexdigest()
prior = json.loads((ROOT / 'site/archive/v1.5.0/results.json').read_text())
for original in prior['runs']:
    current = dict(next(r for r in data['runs'] if r['id'] == original['id']))
    assert current == original, 'Previously published evidence changed'
old_receipts = json.loads((ROOT / 'site/archive/v1.5.0/EVALUATION_R4.json').read_text())
assert receipts['jobs'][:102] == old_receipts['jobs'], 'Previously published scoring receipts changed'
outcomes = Counter()
for run in all_runs:
    assert checksums[run['source_archive']['file']] == run['source_archive']['sha256']
    assert run['passed'] == expected[run['id']]
    assert {c['key'] for c in run['cases']} == set(SELECTED)
    assert sum(c['status']=='passed' for c in run['cases']) == run['passed']
    assert len(run['retained']) == 20
    assert sum(c['status']=='passed' for c in run['retained']) == run['retained_passed']
    history_job = jobs[run['id'], 'retained', 5]
    assert history_job['counts'] == Counter(c['status'] for c in run['retained'])
    assert history_job['summary_sha256'] == run['evidence']['retained_summary_sha256']
    assert abs(sum(r['seconds'] for r in run['releases']) - run['seconds']) < .001
    assert abs(run['reused_seconds'] + run['new_seconds'] - run['seconds']) < .001
    assert len({s['session_sha256'] for s in run['releases']}) == 5
    assert [s['release'] for s in run['releases']] == [1, 2, 3, 4, 5]
    reused_m1 = run['model'] in ('gpt-6-astra', 'gpt-6-sol', 'claude-opus-5-5') and run['id'] != 'opus55-xhigh-02'
    assert [s['reused'] for s in run['releases']] == [reused_m1, False, False, False, False]
    assert run['uncontested_total'] == 121
    assert sum(c['status'] == 'passed' and c['key'] not in data['disputed_cases'] for c in run['cases']) == run['uncontested_passed']
    for key, attempts in run['repeatability'].items():
        assert len(attempts) == 8
        result = next(c for c in run['cases'] if c['key'] == key)
        assert (result['status'] == 'passed') == all(s == 'passed' for s in attempts)
    outcomes.update(c['status'] for c in run['retained'])
    for category in ('production', 'test'):
        assert sum(f['lines'] for f in run['code']['files'] if f['category']==category) == run['code'][category]
    assert run['usage']['boundary_verified']
    assert run['usage']['cached_input_tokens'] <= run['usage']['input_tokens']
    price_in, price_cache, price_out = run.get('pricing_rates', data['pricing']['rates'][run['model']])
    for stage in run['releases']:
        job = jobs[stage.get('evaluation_lane',run['id']), 'api', stage['release']]
        assert job['summary_sha256'] == stage['summary_sha256']
        assert job['counts'] == Counter(c['status'] for c in stage['cases'])
        errors = [c for c in stage['cases'] if c['status'] == 'error']
        if errors:
            assert run['id'] == 'deepseek41-high-03'
            assert job['exit_code'] == 0 and job['complete_case_inventory']
            assert job['supervisor_status'] == 'execution_failure'
            assert len(errors) == job['exceptions'] == len(job['candidate_contract_errors'])
            assert {c['key'] for c in errors} == {c['key'] for c in job['candidate_contract_errors']}
            assert all(c['classification'] == 'candidate_required_response_field_missing'
                       and len(c['case_sha256']) == 64 for c in job['candidate_contract_errors'])
        assert job['changes'] == stage['changes']
        outcomes.update(c['status'] for c in stage['cases'])
        assert stage['total'] == [34, 51, 71, 87, 123][stage['release'] - 1]
        assert stage['passed'] == sum(c['status'] == 'passed' for c in stage['cases'])
        assert set(c['key'] for c in stage['cases']) == {k for k,c in SELECTED.items() if c.milestone <= stage['release']}
        for f in stage['code']['files']:
            assert stage['snapshot_files'][f['path']] == f['sha256']
        u = stage['usage']
        assert u['boundary_verified'] and u['source_sha256']
        if run['model'].startswith('gpt-'):
            usd = 0
            for kind, b in u['pricing_buckets'].items():
                usd += ((b.get('input_tokens', 0) - b.get('cached_input_tokens', 0)) * price_in +
                        b.get('cached_input_tokens', 0) * price_cache) * (2 if kind == 'long' else 1) / 1e6
                usd += b.get('output_tokens', 0) * price_out * (1.5 if kind == 'long' else 1) / 1e6
            for field in ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens'):
                assert sum(b.get(field, 0) for b in u['pricing_buckets'].values()) == u[field]
        elif run['model'].startswith('deepseek/'):
            usd = ((u['input_tokens'] - u['cached_input_tokens']) * price_in +
                   u['cached_input_tokens'] * price_cache + u['output_tokens'] * price_out) / 1e6
            assert u['cache_write_5m_tokens'] == u['cache_write_1h_tokens'] == 0
            assert u['reasoning_output_tokens'] <= u['output_tokens']
            assert run['provider'] == 'Reka' and run['independent_fresh_m1']
        else:
            usd = ((u['input_tokens'] - u['cached_input_tokens'] - u['cache_write_5m_tokens'] - u['cache_write_1h_tokens']) * price_in +
                   u['cached_input_tokens'] * price_cache + u['output_tokens'] * price_out +
                   u['cache_write_5m_tokens'] * 5 + u['cache_write_1h_tokens'] * 8) / 1e6
            assert abs(usd-u['cli_cost_usd']-u.get('archive_minus_cli_cost_usd', 0)) < 1e-7
            if run['id'] == 'opus55-xhigh-02':
                assert abs(u['archive_minus_cli_cost_usd'] - (0.1230792 if stage['release'] == 5 else 0)) < 1e-7
                assert u['requests'] > 0
                assert run['independent_fresh_m1'] and run['claude_cli_version'] == '2.1.285'
            assert abs(sum(a['seconds'] for a in u['attempts']) - stage['seconds']) < .001
        assert abs(usd-u['api_equivalent_usd']) < 1e-7
    for field in ('input_tokens', 'cached_input_tokens', 'cache_write_5m_tokens', 'cache_write_1h_tokens',
                  'output_tokens', 'reasoning_output_tokens', 'api_equivalent_usd'):
        assert abs(sum(s['usage'][field] for s in run['releases']) - run['usage'][field]) < 1e-7
        assert abs(run['reused_usage'][field] + run['new_usage'][field] - run['usage'][field]) < 1e-7
    assert not any('/Users/' in str(v) for v in run.values())
for path in (ROOT / 'site').rglob('*'):
    if path.is_file() and path.suffix in ('.js', '.json', '.html', '.css'):
        text = path.read_text()
        assert '/Users/' not in text and 'Bearer eyJ' not in text, path
outcomes = Counter()
for job in receipts['jobs']: outcomes.update(job['counts'])
assert set(outcomes) == {'passed', 'failed', 'error'} and sum(outcomes.values()) == 10777, outcomes
assert outcomes['error'] == 13
replicate = next(r for r in data['runs'] if r['id'] == 'opus55-xhigh-02')
assert [s['passed'] for s in replicate['releases']] == [30, 47, 64, 79, 105]
assert replicate['retained_passed'] == 20 and replicate['usage']['requests'] == 457
assert sum(len(s['usage']['attempts']) for s in replicate['releases']) == 9
assert len(replicate['repeatability']) == 4
assert abs(replicate['quota_idle_seconds'] - 153914.0994091034) < .001
assert abs(replicate['usage']['api_equivalent_usd'] - 82.2077218) < 1e-7
deepseek = next(r for r in data['runs'] if r['id'] == 'deepseek41-high-01')
assert [s['passed'] for s in deepseek['releases']] == [21, 31, 39, 43, 50]
assert (deepseek['retained_passed'], deepseek['usage']['requests']) == (3, 1028)
assert (deepseek['code']['production'], deepseek['code']['test']) == (20478, 4745)
assert deepseek['usage']['input_tokens'] == 227443334
assert deepseek['usage']['output_tokens'] == 1021431
assert abs(deepseek['usage']['api_equivalent_usd'] - 1.40029566) < 1e-8
assert jobs['deepseek41-high-01', 'retained', 5]['exit_code'] is None
for identifier, scores, histories, production, tests, dated, common in (
        ('deepseek41-high-02', [7, 8, 9, 12, 12], 2, 21033, 4743, 1.209844448, 15.73209384),
        ('deepseek41-high-03', [21, 33, 47, 47, 58], 18, 25013, 5553, 17.82166208, 17.82166208)):
    run = next(r for r in data['runs'] if r['id'] == identifier)
    assert [s['passed'] for s in run['releases']] == scores
    assert (run['retained_passed'], run['code']['production'], run['code']['test']) == (histories, production, tests)
    assert abs(run['usage']['api_equivalent_usd'] - dated) < 1e-8
    assert abs(data['comparable_costs'][identifier]['api_equivalent_usd'] - common) < 1e-8
assert set(data['comparable_costs']) == {f'deepseek41-high-0{n}' for n in (1, 2, 3)}
for run in data['runs']:
    if run['id'] not in data['comparable_costs']:
        continue
    expected_cost = (run['usage']['input_tokens'] * .08 + run['usage']['output_tokens'] * .80) / 1e6
    comparison = data['comparable_costs'][run['id']]
    assert abs(comparison['api_equivalent_usd'] - expected_cost) < 1e-8
    assert abs(sum(comparison['releases']) - expected_cost) < 1e-8
assert len(checksums) == 28
for n, final, history in ((1,102,15),(2,112,20),(3,109,20)):
    strict=next(r for r in data['runs'] if r['id']==f'terra61-strict-xhigh-{n:02}')
    assisted=next(r for r in data['runs'] if r['id']==f'terra61-assisted-xhigh-{n:02}')
    assert (strict['passed'],strict['retained_passed'])==(1,0)
    assert (assisted['passed'],assisted['retained_passed'])==(final,history)
    assert strict['independent_fresh_m1'] and not assisted['independent_fresh_m1']
    assert assisted['protocol']=='completion-assisted-handoff' and assisted['paired_strict_run']==strict['id']
    assert assisted['completion_nudges']==5 and assisted['initial_seconds']+assisted['additional_seconds']==assisted['seconds']
    for s in assisted['releases']:
        assert s['completion_nudges']==1 and len(s['usage_phases'])==2
        assert abs(s['initial_seconds']+s['additional_seconds']-s['seconds'])<1e-6
        assert jobs[s['initial_evaluation_lane'],'api',s['release']]['summary_sha256']==s['initial_summary_sha256']
        for key in ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens','requests','api_equivalent_usd'):
            assert abs(s['initial_usage'][key]+s['additional_usage'][key]-s['usage'][key])<1e-7
print(f'Verified {len(manifest["sha256"])} source hashes, 23 headline runs, 3 supplementary paired branches, 10777 outcomes, 162 unique scoring receipts, preserved errors, provenance, code, timing and prices.')
