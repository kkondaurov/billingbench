#!/usr/bin/env python3
"""Append two audited replicas; retain raw case errors and dated cost evidence."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from export_deepseek import MODEL, TOTALS, session_usage
from export_opus_replicate import hashes
from export_r3 import DISPUTED, sum_usage
from export_v1 import archive, code_metrics, compact_result, read, sha, write

VERSION = '1.5.0'
IMAGE = 'sha256:7478deb805b212cf752e3e93719ad7bdc188eda9f1e6f514c8fcdb1adfb009bf'
RATES = {2: [.08, .004, .40], 3: [.08, .08, .80]}
FIELDS = {'memo-compensation': 'source', 'interaction-paid-credit-compensation-0': 'source',
          'promotion-priority-overage': 'overage_minor', 'bundled-paid-capacity': 'overage_minor'}


def price(usage, rates):
    assert usage['cache_write_5m_tokens'] == usage['cache_write_1h_tokens'] == 0
    return ((usage['input_tokens'] - usage['cached_input_tokens']) * rates[0]
            + usage['cached_input_tokens'] * rates[1] + usage['output_tokens'] * rates[2]) / 1e6


def checked_rows(summary, receipt, expected, output, allow_errors=False):
    if isinstance(summary, dict):
        assert summary['status'] == 'completed'
        rows = summary['results']
    else:
        rows = summary
    assert len(rows) == len(expected) == len({r['key'] for r in rows})
    assert {r['key'] for r in rows} == set(expected)
    assert Counter(r['status'] for r in rows) == receipt['counts']
    assert all(r['status'] in ('passed', 'failed', 'error') for r in rows)
    errors = []
    for row in rows:
        raw_path = output / ('cases' if isinstance(summary, dict) else '') / (row['key'] + '.json')
        raw = read(raw_path)
        assert raw['result'] == row
        if row['status'] != 'error':
            continue
        assert allow_errors and row['key'] in FIELDS, 'Unexplained errors cannot be published as scores'
        field = FIELDS[row['key']]
        assert row['error'] == f"KeyError: '{field}'"
        collection = 'applications' if field == 'source' else 'rated-charges'
        request = next(r for r in reversed(raw['trace'])
                       if r['method'] == 'GET' and '/' + collection + '?' in r['path'])
        assert request['status'] == 200 and request['response']['data']
        assert any(field not in r for r in request['response']['data'])
        errors.append(dict(key=row['key'], error=row['error'], field=field, collection=collection,
                           case_sha256=sha(raw_path), classification='candidate_required_response_field_missing'))
    assert errors == receipt.get('error_evidence', [])
    return rows, errors


def append_run(data, public, evidence, source, archives, sample):
    audit = read(evidence / 'MONITOR_COMPLETION.json')
    ready = read(evidence / 'READY.json')
    state = read(evidence / 'run/status.json')
    screen = read(evidence / 'SCREEN.json')
    report = read(evidence / 'RUN_REPORT.json')
    assert audit['status'] == ('verified_completed' if sample == 2 else 'verified_complete_with_candidate_case_errors')
    assert state['status'] == report['status'] == 'completed'
    assert state['model'] == 'openrouter/' + MODEL and state['effort'] == 'high'
    assert not ready['reused_releases'] and ready['image'] == IMAGE
    assert report['private_feedback_to_candidate'] is False
    assert [s['milestone'] for s in state['completed']] == list(range(1, 6))
    assert len({s['session_id'] for s in state['completed']}) == 5
    assert len({s['runtime_container_id'] for s in state['completed']}) == 5
    assert set(screen['evaluations']) == {'api-m1', 'api-m2', 'api-m3', 'api-m4', 'api-m5', 'retained'}
    assert all(j['exit_code'] == 0 for j in screen['evaluations'].values())
    for name, digest in ready['adapter_sha256'].items():
        assert sha(evidence / name) == digest
    for item in audit['database_checkpoints']:
        path = evidence / 'run/databases' / ('milestone-' + str(item['milestone'])) / 'manifest.json'
        assert sha(path) == item['manifest_sha256']
        for row in read(path):
            assert sha(Path(row['path'])) == row['sha256']
    provisioning = [json.loads(line) for line in (evidence / 'run/provisioning.jsonl').read_text().splitlines()]
    assert len(provisioning) == 5
    assert {p['container_id'] for p in provisioning} == {s['runtime_container_id'] for s in state['completed']}
    for p in provisioning:
        assert p['model'] == 'openrouter/' + MODEL and p['effort'] == 'high'
        assert p['opencode_version'] == '1.18.31' and p['auth_providers'] == ['openrouter']
        model = p['config']['provider']['openrouter']['models'][MODEL]
        assert model['options']['provider'] == dict(only=['Reka'], allow_fallbacks=False, require_parameters=True)
    baseline = next(r for r in data['runs'] if r['id'] == 'deepseek41-high-01')
    row = {k: deepcopy(baseline[k]) for k in ('model', 'effort', 'harness', 'opencode_version', 'provider',
           'protocol', 'independent_fresh_m1', 'requested_output_cap', 'quantization', 'reasoning_equivalence', 'runtime')}
    row.update(id=f'deepseek41-high-{sample:02}', sample=sample, cohort='2026-10-23', releases=[],
               pricing_rates=RATES[sample], pricing_verified_on='2026-10-23 before run ' + str(sample),
               cost_limitation='Dated SDK estimate, not native billing. Provider pricing changed during run 2; exact billed cost needs receipts. Unarchived interrupted-request usage may be missing.')
    source_hashes = hashes(source / 'evaluation/0.5/billing_eval')

    def job(name, n, receipt):
        path = evidence / 'run/evaluation' / name / 'summary.json'
        assert sha(path) == receipt['summary_sha256']
        api = name.startswith('api-')
        expected = baseline['releases'][n-1]['cases'] if api else baseline['retained']
        rows, errors = checked_rows(read(path), receipt, [c['key'] for c in expected], path.parent,
                                   allow_errors=sample == 3 and api)
        if api:
            assert hashes(path.parent / 'evaluator-source/billing_eval') == source_hashes
            assert sha(path.parent / 'evaluator-source/evaluate.py') == sha(source / 'evaluate_v05.py')
        else:
            assert hashes(path.parent / 'evaluator-source') == source_hashes
            assert sha(path.parent / 'evaluate_retained.py') == sha(source / 'evaluate_retained_v05.py')
        wrapper_status = screen['evaluations'][name]['status']
        assert wrapper_status == ('execution_failure' if errors else 'completed')
        cases = [compact_result(r) for r in rows]
        for c in cases:
            if c['key'] in DISPUTED:
                c['interpretation'] = 'disputed-contract-expectation'
        repetitions = {r['key']: [a['status'] for a in r['repetitions']] for r in rows if 'repetitions' in r}
        result = dict(lane=row['id'], kind='api' if api else 'retained', milestone=n,
                      summary_sha256=sha(path), counts=dict(Counter(r['status'] for r in rows)), old_counts=None,
                      uncontested_counts=dict(Counter(r['status'] for r in rows if r['key'] not in DISPUTED)),
                      changes=[], repeatability=repetitions, exceptions=len(errors), exit_code=0,
                      evaluation_basis='First scoring with unchanged frozen R4',
                      supervisor_status=wrapper_status, complete_case_inventory=True,
                      candidate_contract_errors=errors)
        public['jobs'].append(result)
        return cases, result

    for stage, measured in zip(state['completed'], audit['releases'], strict=True):
        n = stage['milestone']
        snapshot = Path(stage['snapshot'])
        assert hashes(snapshot) == stage['sha256']
        for name, digest in stage['input_receipt']['sha256'].items():
            assert sha(snapshot / name) == digest
        session = evidence / 'run/sessions' / (stage['session_id'] + '.json')
        assert stage['session_id'] == measured['session_id'] and sha(session) == measured['session_sha256']
        assert all(m['info']['sessionID'] == stage['session_id'] for m in read(session)['messages'])
        runtime_path = evidence / ('run/runtime.json' if n == 5 else f'run/runtimes/milestone-{n}.json')
        runtime = read(runtime_path)
        assert sha(runtime_path) == measured['runtime_receipt_sha256']
        assert runtime['image_id'] == IMAGE and runtime['container_id'] == stage['runtime_container_id'] == measured['runtime_container_id']
        usage = session_usage(session, RATES[sample])
        assert abs(usage['api_equivalent_usd'] - measured['archived_sdk_cost']) < 1e-8
        cases, receipt = job('api-m' + str(n), n, measured)
        code = code_metrics(snapshot)
        assert (code['production'], code['test']) == (measured['production_loc'], measured['test_loc'])
        assert stage['seconds'] == measured['seconds']
        row['releases'].append(dict(release=n, seconds=stage['seconds'], reused=False, usage=usage, code=code,
            snapshot_files=stage['sha256'], session_sha256=hashlib.sha256(stage['session_id'].encode()).hexdigest(),
            cases=cases, passed=receipt['counts'].get('passed', 0), total=len(cases), summary_sha256=receipt['summary_sha256'],
            previous_counts=None, changes=[], repeatability=receipt['repeatability']))
    retained, history = job('retained', 5, audit['retained'])
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
        uncontested_total=121, families=groups, cases=final['cases'], retained=retained, repeatability=final['repeatability'],
        previous_counts=None, changes=[], retained_changes=[], retained_previous_counts=None,
        source_archive=dict(file=filename, sha256=sha(archives / filename)),
        evidence=dict(final_summary_sha256=final['summary_sha256'], retained_summary_sha256=history['summary_sha256'],
            snapshot_files=final['snapshot_files'], monitor_completion_sha256=sha(evidence / 'MONITOR_COMPLETION.json'),
            report_sha256=sha(evidence / 'RUN_REPORT.json'), ready_sha256=sha(evidence / 'READY.json'),
            screen_sha256=sha(evidence / 'SCREEN.json'), supervisor_status=screen['status'],
            completion_basis='All six jobs exited zero with complete unique case inventories; raw candidate-caused case errors remain errors.'))
    assert abs(row['usage']['api_equivalent_usd'] - report['api_equivalent_dollars']) < 1e-8
    data['runs'].append(row)


def export(base, evidence2, evidence3, r4, output, archives):
    data, public = read(base / 'results.json'), read(base / 'EVALUATION_R4.json')
    assert data['version'] == '1.4.0' and len(data['runs']) == 15 and len(public['jobs']) == 90
    old_runs, old_jobs = deepcopy(data['runs']), deepcopy(public['jobs'])
    frozen = read(r4 / 'MANIFEST.json')
    assert sha(r4 / 'MANIFEST.json') == 'ca1de4f5b677291d326501ffcdca642fe75e89b635ef5e8df620d07f840de5a7'
    assert hashes(r4 / 'harness') == frozen['harness_sha256']
    for sample, evidence in ((2, evidence2), (3, evidence3)):
        assert read(evidence / 'READY.json')['harness_sha256'] == frozen['harness_sha256']
        append_run(data, public, evidence, r4 / 'harness/benchmark/v1', archives, sample)
    assert data['runs'][:15] == old_runs and public['jobs'][:90] == old_jobs
    assert [r['passed'] for r in data['runs'][-2:]] == [12, 58]
    assert sum(j.get('exceptions', 0) for j in public['jobs']) == 13
    data.update(version=VERSION, date='2026-10-24')
    public['version'] = VERSION
    data['comparable_costs'] = {r['id']: dict(api_equivalent_usd=price(r['usage'], RATES[3]),
        reused_api_equivalent_usd=0, new_api_equivalent_usd=price(r['usage'], RATES[3]),
        releases=[price(s['usage'], RATES[3]) for s in r['releases']])
        for r in data['runs'] if r['model'] == MODEL}
    data['pricing']['deepseek_comparison'] = dict(rates=RATES[3], verified_at='2026-10-24T01:14:52.683246Z',
        provider='Reka', source='https://openrouter.ai/api/v1/models/' + MODEL + '/endpoints',
        scope='All three DeepSeek token mixes repriced at one dated quote; other models keep their archived verified rates.',
        dated_rates={'deepseek41-high-01': [.15, .003, .60], 'deepseek41-high-02': RATES[2], 'deepseek41-high-03': RATES[3]},
        limitation='SDK estimates are not billing receipts. Pricing changed during run 2; its exact billed cost is uncertain. Interrupted-request usage may be missing.')
    data['qualification'].update(jobs=102, snapshot_count=85, evaluator_exceptions=13,
        candidate_contract_error_occurrences=13, execution_failures=0, incremental_jobs=24, scenario_outcomes=6562)
    data['incremental_publication'] = dict(baseline_version='1.4.0', evaluator_changed=False,
        old_jobs_rerun=False, completed_work_verified_from_raw_evidence=True)
    write(output / 'results.json', data)
    (output / 'data.js').write_text('window.BILLING_RESULTS = ' + json.dumps(data) + ';\n')
    write(output / 'EVALUATION_R4.json', public)
    print('Verified 17 runs / 102 jobs / 6562 outcomes; 13 preserved candidate-contract error occurrences.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'evidence2', 'evidence3', 'r4', 'output', 'archives'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    export(a.base, a.evidence2, a.evidence3, a.r4, a.output, a.archives)
