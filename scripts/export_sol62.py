#!/usr/bin/env python3
"""Audit and append three fresh Sol 6.2 trajectories to the frozen R4 comparison."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from export_r3 import DISPUTED, sum_usage
from export_terra import TOTALS, hashes, usage_records
from export_terra_max import checked_job
from export_v1 import archive, code_metrics, compact_result, read, sha, write

MODEL, EFFORT, CLI = 'gpt-6.2-sol', 'xhigh', '0.169.0'
VERSION, DATE = '1.8.0', '2026-11-17'
RATES = [2, .1, 10]
IMAGE = 'sha256:6e52d0a6adda59e6d73dc2ae161d47fab2991e1aba91c61a96e54c46c0baaa86'
FREEZE_HASH = 'ca1de4f5b677291d326501ffcdca642fe75e89b635ef5e8df620d07f840de5a7'
LABELS = [f'sol62-xhigh-{n:02}' for n in (1, 2, 3)]


def session_usage(root, stage):
    session = stage['session_id']
    files = list((root/'sessions').rglob(f'rollout-*{session}.jsonl'))
    assert len(files) == 1
    rows = [json.loads(line) for line in files[0].read_text().splitlines() if line.strip()]
    metadata = [r['payload'] for r in rows if r['type'] == 'session_meta']
    assert len(metadata) == 1 and metadata[0]['id'] == session and metadata[0]['cli_version'] == CLI
    contexts = [r['payload'] for r in rows if r['type'] == 'turn_context']
    assert [(c['model'], c['effort'], c.get('service_tier')) for c in contexts] == [(MODEL, EFFORT, None)]
    ends = [i for i, r in enumerate(rows)
            if r.get('type') == 'event_msg' and r['payload'].get('type') == 'task_complete']
    assert len(ends) == 1
    assert not any(r['type'] == 'token_usage_record' for r in rows[ends[0]+1:])
    records = [r['payload'] for r in rows if r['type'] == 'token_usage_record']
    assert all(r['session_id'] == session for r in records)
    log = [json.loads(line) for line in Path(stage['log']).read_text().splitlines() if line.strip()]
    assert [r['thread_id'] for r in log if r['type'] == 'thread.started'] == [session]
    assert [r['usage'] for r in log if r['type'] == 'turn.completed'] == [stage['usage']]
    deliveries = [r['item']['text'] for r in log
                  if r.get('type') == 'item.completed' and r.get('item', {}).get('type') == 'agent_message']
    assert deliveries and rows[ends[0]]['payload']['last_agent_message'] == deliveries[-1]
    usage = usage_records(rows[:ends[0]+1], RATES)
    usage['source_sha256'] = {'request_records': sha(files[0])}
    usage['cli_cumulative_receipt'] = stage['usage']
    usage['receipt_delta'] = {k: usage[k] - stage['usage'][k] for k in
        ('input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens')}
    return usage


def export(base, evidence, freeze, output, archives):
    data, public = read(base/'results.json'), read(base/'EVALUATION_R4.json')
    assert data['version'] == public['version'] == '1.7.0'
    assert len(data['runs']) == 26 and len(public['jobs']) == 180
    assert sha(freeze/'MANIFEST.json') == FREEZE_HASH
    assert hashes(freeze/'harness') == read(freeze/'MANIFEST.json')['harness_sha256']
    ready, screen = (read(evidence/name) for name in ('READY.json', 'SCREEN.json'))
    assert (ready['model'], ready['effort'], ready['cli_version'], ready['image']) == (MODEL, EFFORT, CLI, IMAGE)
    assert ready['fresh_m1'] and ready['protocol'] == 'handoff' and ready['completion_nudges'] == 0
    assert ready['labels'] == LABELS and ready['scheduled_evaluations'] == 18
    assert all(sha(evidence/name) == digest for name, digest in ready['adapter_sha256'].items())
    assert sha(evidence/'preflight-cli169/PREFLIGHT.json') == ready['preflight_sha256']
    assert sha(evidence/'Dockerfile.cli169') == ready['dockerfile_sha256']
    assert screen['status'] == 'completed_pending_outcome_audit' and len(screen['evaluations']) == 18
    assert set(screen['candidates']) == set(LABELS)
    launch = read(evidence/'LAUNCH_VERIFIED.json')
    assert screen['pid'] == launch['supervisor_pid'] == read(evidence/'LAUNCH.json')['pid']
    source = freeze/'harness/benchmark/v1'
    baseline = data['runs'][0]
    evaluator = hashes(source/'evaluation/0.5/billing_eval')
    packet = hashes(source/'candidate/0.5')
    all_sessions, all_runtimes = set(), set()

    def job(lane, path, name, n):
        retained = name == 'retained'
        expected = baseline['retained'] if retained else baseline['releases'][n-1]['cases']
        rows = checked_job(path, expected, retained)
        copied = path/'evaluator-source' if retained else path/'evaluator-source/billing_eval'
        assert hashes(copied) == evaluator
        assert sha(path/('evaluate_retained.py' if retained else 'evaluator-source/evaluate.py')) == sha(
            source/('evaluate_retained_v05.py' if retained else 'evaluate_v05.py'))
        counts = dict(Counter(r['status'] for r in rows))
        state = screen['evaluations'][f'{lane}/{name}']
        assert state['status'] == 'completed' and state['exit_code'] == 0 and state['case_counts'] == counts
        receipt = dict(lane=lane, kind='retained' if retained else 'api', milestone=n,
            summary_sha256=sha(path/'summary.json'), counts=counts, old_counts=None, changes=[],
            uncontested_counts=dict(Counter(r['status'] for r in rows if r['key'] not in DISPUTED)),
            repeatability={r['key']:[p['status'] for p in r['repetitions']] for r in rows if 'repetitions' in r},
            exceptions=0, complete_case_inventory=True, evaluation_basis='Unchanged frozen R4', exit_code=0)
        public['jobs'].append(receipt)
        cases = [compact_result(r) for r in rows]
        for case in cases:
            if case['key'] in DISPUTED:
                case['interpretation'] = 'disputed-contract-expectation'
        return cases, receipt

    for i, lane in enumerate(LABELS, 1):
        root = evidence/'runs'/lane
        state = read(root/'status.json')
        assert screen['candidates'][lane]['exit_code'] == 0
        assert state['status'] == 'completed' and len(state['completed']) == 5
        assert (state['model'], state['effort'], state['harness'], state['protocol']) == (MODEL, EFFORT, 'codex', 'handoff')
        assert not state['delegation'] and not state.get('prefix_provenance')
        assert state['runtime_image'] == IMAGE and hashes(root/'inputs') == packet
        row = dict(id=lane, model=MODEL, effort=EFFORT, sample=i, group_id='sol62-xhigh',
            protocol=data['protocol'], harness='Codex CLI', codex_cli_version=CLI, cohort=DATE,
            independent_fresh_m1=True, completion_nudges=0, pricing_rates=RATES, pricing_verified_on=DATE,
            runtime=dict(image=IMAGE, virtualization='VZ/aarch64', elixir='1.20.2', otp='29.0.4', postgres='17.11'),
            releases=[])
        for n, stage in enumerate(state['completed'], 1):
            snapshot = root/'snapshots'/f'milestone-{n}'
            assert stage['milestone'] == n and snapshot == Path(stage['snapshot'])
            assert hashes(snapshot) == stage['sha256'] and stage['seconds'] > 0
            files = {name for section in read(root/'inputs/manifest.json')['milestones']
                     if section['milestone'] <= n for name in section['files']}
            assert {p.name for p in (snapshot/'requests').iterdir()} == files
            assert all(sha(snapshot/'requests'/name) == packet[name] for name in files)
            assert all(sha(snapshot/name) == digest for name, digest in stage['input_receipt']['sha256'].items())
            assert len(stage['attempts']) == 1 and stage['attempts'][0]['completed'] and stage['attempts'][0]['exit_code'] == 0
            assert stage['session_id'] not in all_sessions
            all_sessions.add(stage['session_id'])
            runtime = read(root/('runtime.json' if n==5 else f'runtimes/milestone-{n}.json'))
            assert runtime['image_id'] == IMAGE and runtime['container_id'] == stage['runtime_container_id']
            assert runtime['container_id'] not in all_runtimes
            all_runtimes.add(runtime['container_id'])
            if n == 1:
                assert launch['runs'][lane]['session_id'] == stage['session_id']
                assert launch['runs'][lane]['container_id'] == runtime['container_id']
            db_dir = root/'databases'/f'milestone-{n}'
            databases = read(db_dir/'manifest.json')
            assert {d['database'] for d in databases} == {'field_desk', 'field_desk_test'}
            for db in databases:
                assert Path(db['path']) == db_dir/(db['database']+'.dump') and sha(Path(db['path'])) == db['sha256']
            if n == 5:
                end = read(root/'FINAL_RUNTIME.json')
                assert end['stopped'] and end['runtime_container_id'] == runtime['container_id']
                assert end['image'] == IMAGE and end['database_checkpoint'] == databases
            cases, receipt = job(lane, root/'evaluation'/f'api-m{n}', f'api-m{n}', n)
            row['releases'].append(dict(release=n, seconds=stage['seconds'], reused=False,
                usage=session_usage(root, stage), code=code_metrics(snapshot), snapshot_files=stage['sha256'],
                session_sha256=hashlib.sha256(stage['session_id'].encode()).hexdigest(),
                cases=cases, passed=receipt['counts']['passed'], total=TOTALS[n-1],
                summary_sha256=receipt['summary_sha256'], previous_counts=None, changes=[],
                repeatability=receipt['repeatability'], completion_nudges=0))
        retained, history = job(lane, root/'evaluation/retained', 'retained', 5)
        final = row['releases'][-1]
        families = {}
        for case in final['cases']:
            families.setdefault(case['family'], Counter()).update([case['status']])
        file = lane+'-m5-source.tar.gz'
        archive(root/'snapshots/milestone-5', archives/file)
        seconds, usage = sum(r['seconds'] for r in row['releases']), sum_usage(row['releases'])
        row.update(seconds=seconds, reused_seconds=0, new_seconds=seconds, usage=usage,
            reused_usage=sum_usage([]), new_usage=usage, code=final['code'],
            passed=final['passed'], total=123, retained_passed=history['counts']['passed'], retained_total=20,
            uncontested_passed=sum(c['status']=='passed' and c['key'] not in DISPUTED for c in final['cases']),
            uncontested_total=121, cases=final['cases'], families=families, retained=retained,
            repeatability=final['repeatability'], previous_counts=None, changes=[], retained_changes=[],
            retained_previous_counts=None, source_archive=dict(file=file, sha256=sha(archives/file)),
            evidence=dict(final_summary_sha256=final['summary_sha256'], retained_summary_sha256=history['summary_sha256'],
                          snapshot_files=final['snapshot_files']),
            cost_limitation='API-equivalent pricing for archived requests, not native subscription charges.')
        data['runs'].append(row)

    assert len(all_sessions) == len(all_runtimes) == 15
    jobs = public['jobs']
    assert len({(j['lane'], j['kind'], j['milestone']) for j in jobs}) == len(jobs) == 198
    assert sum(sum(j['counts'].values()) for j in jobs) == 13093
    assert sum(j.get('exceptions',0) for j in jobs) == 13
    assert data['pricing']['rates']['gpt-6.1-sol'] == RATES
    data['pricing']['rates'][MODEL] = RATES
    data['pricing']['sol62'] = dict(verified_on=DATE, source='https://developers.openai.com/api/docs/pricing',
        standard_short_rates=RATES, standard_long_rates=[4, .2, 15], long_threshold=272000, matches_sol61=True)
    data['sol62_protocol'] = dict(independent_starts=3, completion_nudges=0, reused_m1=0,
        runtime='Pinned Colima VZ arm64 image, derived from Terra runtime with only the CLI layer changed.',
        compatibility='Sol 6.2 CLI 0.169.0 differs from Sol 6.1 CLI 0.159.0 and its older runtime.',
        timing='Three concurrent candidates shared the host. No timing adjustment is applied.')
    data.update(version=VERSION, date=DATE)
    data['qualification'].update(jobs=198, scenario_outcomes=13093, snapshot_count=160, incremental_jobs=18,
        main_snapshot_rows=145, unique_api_snapshot_jobs=166, regression_tests=98)
    data['incremental_publication'] = dict(baseline_version='1.7.0', evaluator_changed=False, old_jobs_rerun=False,
        completed_work_verified_from_raw_evidence=True, new_unique_jobs=18, main_comparison_runs=29,
        supplementary_paired_runs=3)
    public['version'] = VERSION
    write(output/'results.json', data)
    write(output/'EVALUATION_R4.json', public)
    (output/'data.js').write_text('window.BILLING_RESULTS = '+json.dumps(data)+';\n')
    print('Verified 15 Sol 6.2 sessions/runtimes, 18 R4 jobs; 198 comparison jobs / 13093 outcomes.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base','evidence','freeze','output','archives'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    export(args.base, args.evidence, args.freeze, args.output, args.archives)
