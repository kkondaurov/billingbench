#!/usr/bin/env python3
"""Append verified Opus replicate 2 to the immutable v1.2.0 R4 dataset.

Reads completed evidence only; never launches candidates or evaluations.
Private transcript paths and identities are replaced by hashes.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from export_r3 import DISPUTED, FIELDS, sum_usage
from export_v1 import archive, code_metrics, compact_result, read, sha, write


def hashes(root):
    assert not any(p.is_symlink() for p in root.rglob('*'))
    return {str(p.relative_to(root)): sha(p) for p in root.rglob('*') if p.is_file()}


def export(base, evidence, candidate, r4, output, archives):
    data = read(base / 'results.json')
    assert data['version'] == '1.2.0' and len(data['runs']) == 13
    complete, metrics, scoring = [read(evidence / n) for n in ('COMPLETE.json', 'METRICS.json', 'SCORING.json')]
    assert complete['status'] == metrics['status'] == 'verified_complete'
    assert complete['metrics_sha256'] == sha(evidence / 'METRICS.json')
    assert complete['token_requests_sha256'] == sha(evidence / 'TOKEN_REQUESTS.json')
    assert metrics['independent_fresh_m1'] and metrics['model'] == 'claude-opus-5-5' and metrics['effort'] == 'xhigh'
    assert scoring['status'] == 'completed' and scoring['hashes_verified'] and len(scoring['jobs']) == 6
    manifest = read(r4 / 'MANIFEST.json')
    assert manifest['status'] == 'qualified'
    assert hashes(r4 / 'harness') == manifest['harness_sha256']
    assert sha(r4 / 'rescore.py') == manifest['worker_sha256']
    assert sha(r4 / 'MANIFEST.json') == complete['r4_manifest_sha256'] == metrics['r4_manifest_sha256']
    state = read(candidate / 'status.json')
    assert state['status'] == 'completed' and len(state['completed']) == 5
    assert len({s['runtime_container_id'] for s in state['completed']}) == 5
    for receipt in metrics['archive_receipts']:
        assert sha(Path(receipt['archive'])) == receipt['sha256']
    row = dict(id='opus55-xhigh-02', model=metrics['model'], effort=metrics['effort'], sample=2,
               harness='Claude Code', cohort='2026-09-30/10-02', claude_cli_version='2.1.285',
               protocol='fresh-session-per-release', independent_fresh_m1=True, releases=[])
    public = read(base / 'EVALUATION_R4.json')
    public['version'] = '1.3.0'
    public['incremental_evidence'] = dict(metrics_sha256=sha(evidence / 'METRICS.json'),
        complete_sha256=sha(evidence / 'COMPLETE.json'), scoring_sha256=sha(evidence / 'SCORING.json'))

    def job(kind, n):
        receipt = scoring['jobs'][f'{kind}-m{n}']
        assert receipt['status'] == 'completed' and receipt['exit_code'] == receipt['exceptions'] == 0
        assert receipt['r4_manifest_sha256'] == complete['r4_manifest_sha256']
        assert receipt['scoring_worker_sha256'] == sha(evidence / 'score.py')
        path = evidence / 'evaluation' / f'{kind}-m{n}' / 'summary.json'
        assert sha(path) == receipt['summary_sha256']
        summary = read(path)
        if kind == 'api':
            assert summary['status'] == 'completed'
        raw = summary['results'] if kind == 'api' else summary
        assert len(raw) == len({r['key'] for r in raw}) == ([34, 51, 71, 87, 123][n-1] if kind == 'api' else 20)
        assert all(r['status'] in ('passed', 'failed') for r in raw)
        assert Counter(r['status'] for r in raw) == receipt['counts']
        cases = [compact_result(r) for r in raw]
        for case in cases:
            if case['key'] in DISPUTED:
                case['interpretation'] = 'disputed-contract-expectation'
        repetitions = {r['key']: [a['status'] for a in r['repetitions']] for r in raw if 'repetitions' in r}
        result = dict(lane=row['id'], kind=kind, milestone=n, summary_sha256=sha(path),
                      counts=dict(Counter(r['status'] for r in raw)), old_counts=None,
                      uncontested_counts=dict(Counter(r['status'] for r in raw if r['key'] not in DISPUTED)),
                      changes=[], repeatability=repetitions, evaluation_basis='first scoring with frozen R4', exceptions=0)
        public['jobs'].append(result)
        return cases, result

    for release in metrics['releases']:
        n = release['milestone']
        submitted = next(s for s in state['completed'] if s['milestone'] == n)
        snapshot = Path(submitted['snapshot'])
        frozen = hashes(snapshot)
        assert frozen == submitted['sha256']
        assert len(frozen) == release['snapshot_files']
        assert release['cli_versions'] == ['2.1.285']
        assert release['session_id'] == submitted['session_id']
        sources = {}
        attempts = []
        for a in release['attempts']:
            p = Path(a['log'])
            sources[p.name] = sha(p)
            attempts.append(dict(seconds=a['seconds'], outcome=a['result_subtype'], exit_code=a['exit_code']))
        assert abs(sum(a['seconds'] for a in attempts) - release['implementation_seconds']) < .001
        sources.update({Path(a['archive']).name: a['sha256'] for a in metrics['archive_receipts'] if a['milestone'] == n})
        u = release['archived_usage']
        usage = dict(input_tokens=u['input_tokens']+u['cache_creation_input_tokens']+u['cache_read_input_tokens'],
            cached_input_tokens=u['cache_read_input_tokens'], cache_write_5m_tokens=u['cache_write_5m_tokens'],
            cache_write_1h_tokens=u['cache_write_1h_tokens'], output_tokens=u['output_tokens'],
            reasoning_output_tokens=u['thinking_tokens'], requests=release['unique_model_messages'], long_requests=0,
            api_equivalent_usd=release['archived_api_equivalent_usd'],
            cli_cost_usd=release['cli_cumulative_api_equivalent_usd'],
            archive_minus_cli_cost_usd=release['archived_api_equivalent_usd']-release['cli_cumulative_api_equivalent_usd'],
            boundary_verified=True, source_sha256=sources, attempts=attempts,
            basis='Deduplicated archived model-message receipts through delivery, including quota-interrupted attempts; final output of one interrupted M5 request is unknown.')
        cases, receipt = job('api', n)
        row['releases'].append(dict(release=n, seconds=release['implementation_seconds'], reused=False,
            quota_idle_seconds=release['quota_idle_seconds'], usage=usage, code=code_metrics(snapshot),
            snapshot_files=frozen, session_sha256=hashlib.sha256(release['session_id'].encode()).hexdigest(),
            cases=cases, passed=receipt['counts']['passed'], total=len(cases), summary_sha256=receipt['summary_sha256'],
            previous_counts=None, changes=[], repeatability=receipt['repeatability']))
    retained, history = job('retained', 5)
    assert len({s['session_sha256'] for s in row['releases']}) == 5
    final = row['releases'][-1]
    grouped = {}
    for case in final['cases']:
        grouped.setdefault(case['family'], Counter()).update([case['status']])
    filename = row['id'] + '-m5-source.tar.gz'
    archive(Path(state['completed'][-1]['snapshot']), archives / filename)
    row.update(seconds=metrics['timing']['implementation_seconds_all_attempts'], reused_seconds=0,
        new_seconds=metrics['timing']['implementation_seconds_all_attempts'],
        quota_idle_seconds=metrics['timing']['quota_idle_seconds'], trajectory_wall_seconds=metrics['timing']['trajectory_wall_seconds'],
        usage=sum_usage(row['releases']), reused_usage=sum_usage([]), new_usage=sum_usage(row['releases']),
        code=final['code'], passed=final['passed'], total=123,
        uncontested_passed=sum(c['status']=='passed' and c['key'] not in DISPUTED for c in final['cases']), uncontested_total=121,
        retained_passed=history['counts']['passed'], retained_total=20, families=grouped, cases=final['cases'], retained=retained,
        repeatability=final['repeatability'], previous_counts=None, changes=[], retained_changes=[], retained_previous_counts=None,
        cost_limitation=metrics['cost_limitation'], cli_cumulative_api_equivalent_usd=metrics['cli_cumulative_api_equivalent_usd'],
        source_archive=dict(file=filename, sha256=sha(archives / filename)),
        evidence=dict(final_summary_sha256=final['summary_sha256'], retained_summary_sha256=history['summary_sha256'], snapshot_files=final['snapshot_files']))
    assert abs(row['usage']['api_equivalent_usd'] - metrics['archived_api_equivalent_usd']) < 1e-7
    assert row['passed'] == 105 and row['retained_passed'] == 20
    data['runs'].append(row)
    # Verified init-event version; v1.2.0's archived report remains unchanged.
    next(r for r in data['runs'] if r['id']=='opus55-xhigh-01')['claude_cli_version'] = '2.1.283'
    data.update(version='1.3.0', date='2026-10-02')
    data['qualification'].update(jobs=84, snapshot_count=70, evaluator_exceptions=0,
                                 incremental_jobs=6, prior_rescore_jobs=78, scenario_outcomes=5404)
    data['pricing']['claude_verified_on'] = '2026-10-02'
    data['incremental_publication'] = dict(baseline_version='1.2.0', evaluator_changed=False, old_jobs_rerun=False,
                                          metrics_sha256=sha(evidence / 'METRICS.json'))
    write(output / 'results.json', data)
    (output / 'data.js').write_text('window.BILLING_RESULTS = ' + json.dumps(data) + ';\n')
    write(output / 'EVALUATION_R4.json', public)
    print('Verified and appended Opus #2: 105/123 API, 20/20 histories; 84 completed R4 jobs total.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'evidence', 'candidate', 'r4', 'output', 'archives'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    export(a.base, a.evidence, a.candidate, a.r4, a.output, a.archives)
