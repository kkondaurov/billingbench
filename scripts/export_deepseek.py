#!/usr/bin/env python3
"""Append the verified DeepSeek trajectory without rewriting older evidence."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
from pathlib import Path

from export_opus_replicate import hashes
from export_r3 import DISPUTED, sum_usage
from export_v1 import archive, code_metrics, compact_result, read, sha, write

MODEL = 'deepseek/deepseek-v4.1-flash-1017'
RATES = [.15, .003, .60]
TOTALS = [34, 51, 71, 87, 123]


def checked_rows(summary, receipt, expected):
    if isinstance(summary, dict):
        assert summary['status'] == 'completed'
        rows = summary['results']
    else:
        rows = summary
    assert isinstance(rows, list) and len(rows) == expected
    assert len({r['key'] for r in rows}) == expected
    assert all(r['status'] in ('passed', 'failed') for r in rows), 'Execution failure is not a score'
    assert Counter(r['status'] for r in rows) == receipt['counts']
    return rows


def session_usage(path):
    session = read(path)
    messages = {m['info']['id']: m['info'] for m in session['messages'] if m['info']['role'] == 'assistant'}
    assert messages
    assert all((m['providerID'], m['modelID'], m.get('variant')) == ('openrouter', MODEL, 'high')
               and m.get('time', {}).get('completed') is not None for m in messages.values())
    u = Counter()
    for message in messages.values():
        t = message.get('tokens', {})
        u.update(input_tokens=t.get('input', 0) + t.get('cache', {}).get('read', 0),
                 cached_input_tokens=t.get('cache', {}).get('read', 0),
                 output_tokens=t.get('output', 0) + t.get('reasoning', 0),
                 reasoning_output_tokens=t.get('reasoning', 0),
                 cache_write_5m_tokens=0, cache_write_1h_tokens=0)
        assert t.get('cache', {}).get('write', 0) == 0
    cost = ((u['input_tokens'] - u['cached_input_tokens']) * RATES[0]
            + u['cached_input_tokens'] * RATES[1] + u['output_tokens'] * RATES[2]) / 1e6
    assert abs(cost - sum(m.get('cost', 0) for m in messages.values())) < 1e-8
    return dict(u, requests=len(messages), long_requests=0, api_equivalent_usd=cost,
                boundary_verified=True, source_sha256={'session_export': sha(path)},
                basis='Deduplicated completed OpenCode assistant messages through delivery; SDK estimate at run-start Reka rates, not native billing.')


def export(base, evidence, r4, output, archives):
    data = read(base / 'results.json')
    assert data['version'] == '1.3.0' and len(data['runs']) == 14
    original_runs = deepcopy(data['runs'])
    audit = read(evidence / 'MONITOR_COMPLETION.json')
    report = read(evidence / 'RUN_REPORT.json')
    ready = read(evidence / 'READY.json')
    state = read(evidence / 'run/status.json')
    assert audit['status'] == report['verification_status'] == 'verified_complete'
    assert state['status'] == 'completed' and state['model'] == 'openrouter/' + MODEL
    assert state['effort'] == 'high' and not ready['reused_releases']
    assert sha(evidence / 'finalize_readout.py') == audit['script_sha256']
    assert sha(evidence / 'SCREEN.json') == audit['original_screen_sha256']
    for name, digest in ready['adapter_sha256'].items():
        assert sha(evidence / name) == digest
    frozen = read(r4 / 'MANIFEST.json')
    assert hashes(r4 / 'harness') == frozen['harness_sha256'] == ready['harness_sha256']
    assert sha(r4 / 'MANIFEST.json') == 'ca1de4f5b677291d326501ffcdca642fe75e89b635ef5e8df620d07f840de5a7'
    assert len(set(audit['unique_release_sessions'])) == len(set(audit['unique_release_runtimes'])) == 5
    assert [s['milestone'] for s in state['completed']] == list(range(1, 6))
    for item in audit['development_database_archives']:
        assert sha(Path(item['path'])) == item['sha256']
    public = read(base / 'EVALUATION_R4.json')
    public['version'] = '1.4.0'
    evaluation = evidence / 'run/evaluation'
    source = r4 / 'harness/benchmark/v1'
    source_hashes = hashes(source / 'evaluation/0.5/billing_eval')
    row = dict(id='deepseek41-high-01', model=MODEL, effort='high', sample=1,
               harness='OpenCode / OpenRouter', opencode_version='1.18.31', provider='Reka',
               cohort='2026-10-23', protocol='fresh-session-per-release', independent_fresh_m1=True,
               requested_output_cap=262144, releases=[], pricing_rates=RATES,
               pricing_verified_on='2026-10-23', quantization='unknown',
               reasoning_equivalence='High requested; native budget equivalence not verified',
               runtime=dict(image=report['runtime_provenance']['image'], elixir='1.20.2', otp='29.0.4',
                            driver='VZ', arch='aarch64', cpus=2, memory_gib=4,
                            comparison_note=audit['runtime_comparison_note']),
               cost_limitation=audit['provider_billing_note'])

    def job(name, n):
        receipt = audit['scoring'][name]
        path = evaluation / name / 'summary.json'
        assert sha(path) == receipt['summary_sha256'] and receipt['evaluator_source_matches_frozen']
        api = name.startswith('api-')
        if api:
            assert receipt['exit_code'] == 0
        rows = checked_rows(read(path), receipt, TOTALS[n-1] if api else 20)
        expected = data['runs'][0]['releases'][n-1]['cases'] if api else data['runs'][0]['retained']
        assert {r['key'] for r in rows} == {r['key'] for r in expected}
        if api:
            assert hashes(path.parent / 'evaluator-source/billing_eval') == source_hashes
            assert sha(path.parent / 'evaluator-source/evaluate.py') == sha(source / 'evaluate_v05.py')
        else:
            assert hashes(path.parent / 'evaluator-source') == source_hashes
            assert sha(path.parent / 'evaluate_retained.py') == sha(source / 'evaluate_retained_v05.py')
            for result in rows:
                assert read(path.parent / (result['key'] + '.json'))['result'] == result
        cases = [compact_result(r) for r in rows]
        for case in cases:
            if case['key'] in DISPUTED:
                case['interpretation'] = 'disputed-contract-expectation'
        repetitions = {r['key']: [a['status'] for a in r['repetitions']] for r in rows if 'repetitions' in r}
        result = dict(lane=row['id'], kind='api' if api else 'retained', milestone=n,
                      summary_sha256=sha(path), counts=receipt['counts'], old_counts=None,
                      uncontested_counts=dict(Counter(r['status'] for r in rows if r['key'] not in DISPUTED)),
                      changes=[], repeatability=repetitions, exceptions=0,
                      evaluation_basis='First scoring with unchanged frozen R4',
                      exit_code=receipt['exit_code'])
        if not api:
            result['completion_basis'] = receipt['exit_code_note']
        public['jobs'].append(result)
        return cases, result

    for stage, measured in zip(state['completed'], report['per_release_usage_and_cost'], strict=True):
        n = stage['milestone']
        snapshot = Path(stage['snapshot'])
        assert hashes(snapshot) == stage['sha256']
        session = evidence / 'run/sessions' / (stage['session_id'] + '.json')
        assert sha(session) == measured['session_sha256']
        assert stage['session_id'] == measured['session_id'] == audit['unique_release_sessions'][n-1]
        assert stage['runtime_container_id'] == audit['unique_release_runtimes'][n-1]
        usage = session_usage(session)
        assert abs(usage['api_equivalent_usd'] - measured['api_equivalent_dollars']) < 1e-8
        cases, receipt = job('api-m' + str(n), n)
        row['releases'].append(dict(release=n, seconds=stage['seconds'], reused=False,
            usage=usage, code=code_metrics(snapshot), snapshot_files=stage['sha256'],
            session_sha256=hashlib.sha256(stage['session_id'].encode()).hexdigest(),
            cases=cases, passed=receipt['counts'].get('passed', 0), total=len(cases),
            summary_sha256=receipt['summary_sha256'], previous_counts=None, changes=[],
            repeatability=receipt['repeatability']))
    retained, history = job('retained', 5)
    final = row['releases'][-1]
    groups = {}
    for case in final['cases']:
        groups.setdefault(case['family'], Counter()).update([case['status']])
    filename = row['id'] + '-m5-source.tar.gz'
    archive(Path(state['completed'][-1]['snapshot']), archives / filename)
    row.update(seconds=sum(s['seconds'] for s in row['releases']), reused_seconds=0,
        new_seconds=sum(s['seconds'] for s in row['releases']), usage=sum_usage(row['releases']),
        reused_usage=sum_usage([]), new_usage=sum_usage(row['releases']), code=final['code'],
        passed=final['passed'], total=123, retained_passed=history['counts'].get('passed', 0), retained_total=20,
        uncontested_passed=sum(c['status']=='passed' and c['key'] not in DISPUTED for c in final['cases']),
        uncontested_total=121, families=groups, cases=final['cases'], retained=retained,
        repeatability=final['repeatability'], previous_counts=None, changes=[], retained_changes=[],
        retained_previous_counts=None, source_archive=dict(file=filename, sha256=sha(archives / filename)),
        evidence=dict(final_summary_sha256=final['summary_sha256'], retained_summary_sha256=history['summary_sha256'],
                      snapshot_files=final['snapshot_files'], monitor_completion_sha256=sha(evidence / 'MONITOR_COMPLETION.json'),
                      report_sha256=sha(evidence / 'RUN_REPORT.json'), ready_sha256=sha(evidence / 'READY.json')))
    assert [s['passed'] for s in row['releases']] == [21, 31, 39, 43, 50]
    assert row['retained_passed'] == 3 and abs(row['usage']['api_equivalent_usd'] - 1.40029566) < 1e-8
    data['runs'].append(row)
    assert data['runs'][:-1] == original_runs
    data.update(version='1.4.0', date='2026-10-23')
    data['pricing']['rates'][MODEL] = RATES
    data['pricing']['deepseek_verified_on'] = '2026-10-23 before run 1; not a current quote'
    data['pricing']['sources'].append('https://openrouter.ai/api/v1/models/' + MODEL + '/endpoints')
    data['qualification'].update(jobs=90, snapshot_count=75, evaluator_exceptions=0,
                                 incremental_jobs=12, scenario_outcomes=5790)
    data['incremental_publication'] = dict(baseline_version='1.3.0', evaluator_changed=False,
        old_jobs_rerun=False, completed_work_verified_from_raw_evidence=True,
        monitor_completion_sha256=sha(evidence / 'MONITOR_COMPLETION.json'))
    public['deepseek_evidence'] = dict(row['evidence'], bookkeeping_recovery=audit['bookkeeping_recovery'])
    write(output / 'results.json', data)
    import json
    (output / 'data.js').write_text('window.BILLING_RESULTS = ' + json.dumps(data) + ';\n')
    write(output / 'EVALUATION_R4.json', public)
    print('Verified DeepSeek #1: 50/123 API, 3/20 histories; 15 runs and 90 R4 jobs.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'evidence', 'r4', 'output', 'archives'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    export(a.base, a.evidence, a.r4, a.output, a.archives)
