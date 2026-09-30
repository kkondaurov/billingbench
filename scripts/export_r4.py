#!/usr/bin/env python3
"""Export the 13-run R4 comparison only after all 78 jobs have verified receipts."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from export_r3 import DISPUTED, RATES, claude_usage, codex_usage, sum_usage
from export_v1 import archive, code_metrics, compact_result, read, sha, write

VERSION = '1.2.0'
INVENTORY = {'gpt-6-astra': 3, 'gpt-6-sol': 3, 'gpt-6-luna': 3,
             'claude-opus-5-5': 1, 'gpt-6.1-sol': 3}
TOTALS = {1: 34, 2: 51, 3: 71, 4: 87, 5: 123}


def snapshot_hashes(path):
    return {str(p.relative_to(path)): sha(p) for p in path.rglob('*') if p.is_file()}


def measurements(rescore):
    manifest = read(rescore / 'MANIFEST.json')
    assert Counter(lane['model'] for lane in manifest['lanes']) == INVENTORY
    rows = []
    for lane in manifest['lanes']:
        directory = Path(lane['run'])
        state = read(directory / 'status.json')
        assert state['model'] == lane['model'] and state['effort'] == lane['effort']
        assert len(state['completed']) == 5
        stages = []
        for stage in sorted(state['completed'], key=lambda s: s['milestone']):
            n = stage['milestone']
            frozen = next(s for s in lane['stages'] if s['milestone'] == n)
            snapshot = Path(stage['snapshot'])
            assert snapshot_hashes(snapshot) == frozen['sha256']
            usage, seconds = (claude_usage if lane['model'].startswith('claude') else codex_usage)(directory, stage, lane['model'])
            stages.append(dict(release=n, seconds=seconds, reused=bool(stage.get('inherited_from')),
                               usage=usage, code=code_metrics(snapshot), snapshot_files=frozen['sha256'],
                               session_sha256=hashlib.sha256(stage['session_id'].encode()).hexdigest()))
        assert [s['release'] for s in stages] == list(range(1, 6))
        assert len({s['session_sha256'] for s in stages}) == 5
        reused = [s for s in stages if s['reused']]
        fresh = [s for s in stages if not s['reused']]
        sol61 = lane['model'] == 'gpt-6.1-sol'
        row = dict(id=lane['label'], model=lane['model'], effort=lane['effort'],
                   sample=int(lane['label'][-2:]),
                   harness='Claude Code' if lane['model'].startswith('claude') else 'Codex CLI',
                   cohort='2026-09-29/30' if sol61 else '2026-09-27/28',
                   codex_cli_version='0.159.0' if sol61 else (None if lane['model'].startswith('claude') else '0.155.1'),
                   protocol='fresh-session-per-release', seconds=sum(s['seconds'] for s in stages),
                   reused_seconds=sum(s['seconds'] for s in reused), new_seconds=sum(s['seconds'] for s in fresh),
                   usage=sum_usage(stages), reused_usage=sum_usage(reused), new_usage=sum_usage(fresh),
                   code=stages[-1]['code'], releases=stages)
        rows.append(row)
        print(row['id'], round(row['seconds'] / 3600, 3), round(row['usage']['api_equivalent_usd'], 2),
              row['code']['production'], row['code']['test'], flush=True)
    return dict(manifest_sha256=sha(rescore / 'MANIFEST.json'), rates=RATES, runs=rows)


def verified_results(rescore):
    manifest = read(rescore / 'MANIFEST.json')
    state = read(rescore / 'STATUS.json')
    assert state['status'] == 'completed' and state.get('hashes_verified'), 'Full rescore not complete'
    assert len(manifest['jobs']) == len(state['jobs']) == 78
    records = []
    identities = set()
    for job in manifest['jobs']:
        identity = (job['lane'], job['kind'], job['milestone'])
        assert identity not in identities
        identities.add(identity)
        key = f'{job["lane"]}/{job["kind"]}-m{job["milestone"]}'
        receipt = state['jobs'][key]
        assert receipt['status'] == 'completed' and receipt['exit_code'] == 0
        path = Path(job['output']) / 'summary.json'
        assert sha(path) == receipt['summary_sha256']
        summary = read(path)
        if job['kind'] == 'api':
            assert summary['status'] == 'completed'
        rows = summary['results'] if job['kind'] == 'api' else summary
        expected = TOTALS[job['milestone']] if job['kind'] == 'api' else 20
        assert len(rows) == len({r['key'] for r in rows}) == expected
        assert all(r['status'] in ('passed', 'failed') for r in rows), 'Execution failure is not a score'
        counts = dict(Counter(r['status'] for r in rows))
        assert counts == receipt['counts']
        original = read(Path(job['original']))
        old_rows = original['results'] if job['kind'] == 'api' else original
        assert {r['key'] for r in rows} == {r['key'] for r in old_rows}
        uncontested = Counter(r['status'] for r in rows if r['key'] not in DISPUTED)
        records.append(dict(lane=job['lane'], kind=job['kind'], milestone=job['milestone'],
                            revised=str(path), summary_sha256=sha(path), counts=counts,
                            old_counts=dict(Counter(r['status'] for r in old_rows)),
                            uncontested_counts=dict(uncontested), changes=receipt['changes'],
                            repeatability={r['key']: [a['status'] for a in r['repetitions']]
                                           for r in rows if 'repetitions' in r}))
    expected = {(lane['label'], 'api', n) for lane in manifest['lanes'] for n in range(1, 6)}
    expected |= {(lane['label'], 'retained', 5) for lane in manifest['lanes']}
    assert identities == expected
    return dict(complete=True, manifest_sha256=sha(rescore / 'MANIFEST.json'), jobs=records)


def export(rescore, measured, output, archives, timing=None):
    results = verified_results(rescore)
    assert measured['manifest_sha256'] == results['manifest_sha256']
    assert measured['rates'] == RATES
    assert Counter(r['model'] for r in measured['runs']) == INVENTORY
    manifest = read(rescore / 'MANIFEST.json')
    assert {r['id'] for r in measured['runs']} == {lane['label'] for lane in manifest['lanes']}
    indexed = {(j['lane'], j['kind'], j['milestone']): j for j in results['jobs']}
    for row in measured['runs']:
        if timing and row['harness'] == 'Codex CLI':
            matching = [r for r in timing['rows'] if r['lane'] == row['id']]
            excluded = [r for r in timing.get('excluded', []) if r['model'] == row['model']]
            assert len(matching) + len(excluded) == 1
            if matching:
                record = matching[0]
                assert abs(record['recorded_seconds'] - row['new_seconds']) < 0.001
                assert record['releases'] == [s['release'] for s in row['releases'] if not s['reused']]
                row['timing_audit'] = {k: record[k] for k in
                    ('releases', 'recorded_seconds', 'session_seconds', 'tool_wait_seconds',
                     'outside_tool_seconds', 'runner_clock_residual_seconds')}
            else:
                row['timing_audit_unavailable'] = excluded[0]['reason']
        for stage in row['releases']:
            job = indexed[row['id'], 'api', stage['release']]
            cases = [compact_result(r) for r in read(Path(job['revised']))['results']]
            for case in cases:
                if case['key'] in DISPUTED:
                    case['interpretation'] = 'disputed-contract-expectation'
            stage.update(cases=cases, passed=job['counts'].get('passed', 0), total=len(cases),
                         summary_sha256=job['summary_sha256'], previous_counts=job['old_counts'],
                         changes=job['changes'], repeatability=job['repeatability'])
        final = row['releases'][-1]
        job = indexed[row['id'], 'api', 5]
        history = indexed[row['id'], 'retained', 5]
        grouped = {}
        for case in final['cases']:
            grouped.setdefault(case['family'], Counter()).update([case['status']])
        lane = next(lane for lane in manifest['lanes'] if lane['label'] == row['id'])
        snapshot = Path(next(s['snapshot'] for s in lane['stages'] if s['milestone'] == 5))
        assert snapshot_hashes(snapshot) == final['snapshot_files']
        filename = row['id'] + '-m5-source.tar.gz'
        archive(snapshot, archives / filename)
        row.update(passed=final['passed'], total=123, uncontested_passed=job['uncontested_counts'].get('passed', 0),
                   uncontested_total=121, retained_passed=history['counts'].get('passed', 0), retained_total=20,
                   families=grouped, cases=final['cases'], retained=[compact_result(r) for r in read(Path(history['revised']))],
                   repeatability=job['repeatability'], previous_counts=job['old_counts'], changes=job['changes'],
                   retained_changes=history['changes'], retained_previous_counts=history['old_counts'],
                   source_archive=dict(file=filename, sha256=sha(archives / filename)),
                   evidence=dict(final_summary_sha256=job['summary_sha256'], retained_summary_sha256=history['summary_sha256'],
                                 snapshot_files=final['snapshot_files']))
    dataset = dict(version=VERSION, date='2026-09-30', evaluator='R4', protocol='fresh-session-per-release',
        pricing=dict(verified_on='2026-09-30', rates=RATES, long_threshold=272000,
                     long_input_multiplier=2, long_output_multiplier=1.5,
                     claude_cache_write_5m=5, claude_cache_write_1h=8,
                     sources=['https://developers.openai.com/api/docs/pricing',
                              'https://platform.claude.com/docs/en/models/opus-5-5/overview']),
        qualification=dict(regression_tests=73, jobs=78, evaluator_exceptions=0,
                           raw_manifest_sha256=results['manifest_sha256'],
                           replayed_final_cases=1599, snapshot_count=65),
        disputed_cases=sorted(DISPUTED), timing_methodology=timing['methodology'] if timing else [],
        scaffold=code_metrics(Path(__file__).resolve().parents[1] / 'benchmark/v1/scaffold'), runs=measured['runs'])
    write(output / 'results.json', dataset)
    (output / 'data.js').write_text('window.BILLING_RESULTS = ' + json.dumps(dataset) + ';\n')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rescore', required=True, type=Path)
    parser.add_argument('--metrics', required=True, type=Path)
    parser.add_argument('--metrics-only', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--archives', type=Path)
    parser.add_argument('--receipts', type=Path)
    parser.add_argument('--timing-audit', type=Path)
    args = parser.parse_args()
    if args.metrics_only:
        assert not args.metrics.exists(), 'Preserve previous measurements'
        write(args.metrics, measurements(args.rescore))
        return
    assert args.output and args.archives and args.receipts
    results = export(args.rescore, read(args.metrics), args.output, args.archives,
                     read(args.timing_audit) if args.timing_audit else None)
    write(args.receipts, results)


if __name__ == '__main__':
    main()
