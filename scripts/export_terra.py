#!/usr/bin/env python3
"""Append paired strict/assisted Terra evidence without changing earlier results."""
import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from export_r3 import DISPUTED, FIELDS, sum_usage
from export_v1 import archive, code_metrics, compact_result, read, sha, write

VERSION = '1.6.0'
MODEL = 'gpt-6.1-terra'
RATES = [1, .05, 5]
TOTALS = [34, 51, 71, 87, 123]
IMAGE = 'sha256:c791f9b773193163d79bd909468a3840b697d54a1a5008c9c910f4662ccaea2b'


def hashes(path):
    return {p.relative_to(path).as_posix(): sha(p) for p in path.rglob('*') if p.is_file()}


def usage_records(events):
    """Price each deduplicated response, never cumulative resume counters."""
    totals, buckets, seen, dollars = Counter(), {'short': Counter(), 'long': Counter()}, {}, Decimal(0)
    for e in events:
        if e.get('type') != 'token_usage_record':
            continue
        p = e['payload']; key = (p['session_id'], p['response_id']); u = p['usage']
        if key in seen:
            assert seen[key] == u
            continue
        seen[key] = u
        assert u.get('cache_write_input_tokens', 0) == 0
        assert 0 <= u['cached_input_tokens'] <= u['input_tokens']
        assert u['reasoning_output_tokens'] <= u['output_tokens']
        long = u['input_tokens'] > 272000
        values = {k: u.get(k, 0) for k in FIELDS[:6]}
        totals.update(values); buckets['long' if long else 'short'].update(values)
        totals['long_requests'] += int(long)
        dollars += ((Decimal(u['input_tokens'] - u['cached_input_tokens']) +
                     Decimal(u['cached_input_tokens']) * Decimal('.05')) * (2 if long else 1) +
                    Decimal(u['output_tokens']) * 5 * (Decimal('1.5') if long else 1)) / 1000000
    assert seen
    return dict({k: totals[k] for k in FIELDS}, requests=len(seen), api_equivalent_usd=float(dollars),
                pricing_buckets=buckets, boundary_verified=True,
                basis='Deduplicated archived response records; per-request long-context tiers; reasoning included in output.')


def session_usage(directory, session):
    files = list((directory / 'sessions').rglob(f'rollout-*{session}.jsonl'))
    assert len(files) == 1, (directory, session, files)
    rows = [json.loads(line) for line in files[0].read_text().splitlines() if line.strip()]
    contexts = [r['payload'] for r in rows if r['type'] == 'turn_context']
    assert contexts and all(r['model'] == MODEL and r['effort'] == 'xhigh' for r in contexts)
    boundaries = [i for i, r in enumerate(rows) if r.get('type') == 'event_msg' and r['payload'].get('type') == 'task_complete']
    assert len(boundaries) in (1, 2), 'Only one initial turn and one completion nudge are authorized'
    assert not any(r['type'] == 'token_usage_record' for r in rows[boundaries[-1]+1:])
    phases, start = [], 0
    for end in boundaries:
        u = usage_records(rows[start:end+1]); u['source_sha256'] = {'request_records': sha(files[0])}
        phases.append(u); start = end+1
    total = usage_records(rows[:boundaries[-1]+1]); total['source_sha256'] = {'request_records': sha(files[0])}
    for key in FIELDS:
        assert total[key] == sum(u[key] for u in phases)
    assert abs(total['api_equivalent_usd'] - sum(u['api_equivalent_usd'] for u in phases)) < 1e-8
    return total, phases


def export(base, original, store, freeze, output, archives):
    data, public = read(base / 'results.json'), read(base / 'EVALUATION_R4.json')
    assert data['version'] == '1.5.0' and len(data['runs']) == 17 and len(public['jobs']) == 102
    old_runs, old_jobs = deepcopy(data['runs']), deepcopy(public['jobs'])
    assert sha(freeze / 'MANIFEST.json') == 'ca1de4f5b677291d326501ffcdca642fe75e89b635ef5e8df620d07f840de5a7'
    assert hashes(freeze / 'harness') == read(freeze / 'MANIFEST.json')['harness_sha256']
    source = freeze / 'harness/benchmark/v1'
    spec = importlib.util.spec_from_file_location('terra_audit_controller', store / 'terra61-final-stage-20261027-v2/controller.py')
    controller = importlib.util.module_from_spec(spec); spec.loader.exec_module(controller)
    controller.verify(); sys.path.insert(0, str(controller.settings.ROOT))
    baseline = data['runs'][0]
    ids = {(j['lane'], j['kind'], j['milestone']) for j in public['jobs']}
    audit = []

    def job(lane, n, path, retained=False):
        kind = 'retained' if retained else 'api'
        key = lane, kind, n
        if key in ids:
            return next(j for j in public['jobs'] if (j['lane'], j['kind'], j['milestone']) == key)
        summary = read(path / 'summary.json')
        rows = summary if retained else summary['results']
        expected = baseline['retained'] if retained else baseline['releases'][n-1]['cases']
        assert len(rows) == len(expected) == len({r['key'] for r in rows})
        assert {r['key'] for r in rows} == {r['key'] for r in expected}
        assert all(r['status'] in ('passed', 'failed') for r in rows), 'Unexplained case errors need diagnosis'
        for r in rows:
            assert read(path / ('' if retained else 'cases') / (r['key']+'.json'))['result'] == r
        copied = path / 'evaluator-source' if retained else path / 'evaluator-source/billing_eval'
        assert hashes(copied) == hashes(source / 'evaluation/0.5/billing_eval')
        script = path / 'evaluate_retained.py' if retained else path / 'evaluator-source/evaluate.py'
        assert sha(script) == sha(source / ('evaluate_retained_v05.py' if retained else 'evaluate_v05.py'))
        receipt = dict(lane=lane, kind=kind, milestone=n, summary_sha256=sha(path/'summary.json'),
                       counts=dict(Counter(r['status'] for r in rows)), old_counts=None,
                       uncontested_counts=dict(Counter(r['status'] for r in rows if r['key'] not in DISPUTED)),
                       changes=[], repeatability={r['key']: [p['status'] for p in r['repetitions']] for r in rows if 'repetitions' in r},
                       exceptions=0, complete_case_inventory=True, evaluation_basis='Unchanged frozen R4')
        public['jobs'].append(receipt); ids.add(key)
        return receipt

    def stage(lane, n, directory, snapshot, state, evaluation, seconds, evaluation_lane=None):
        assert hashes(snapshot) == state.get('snapshot_sha256', state.get('sha256'))
        for name, digest in state.get('input_receipt', {}).get('sha256', {}).items():
            assert sha(snapshot / name) == digest
        u, phases = session_usage(directory, state['session_id'])
        receipt = job(evaluation_lane or lane, n, evaluation)
        rows = [compact_result(r) for r in read(evaluation/'summary.json')['results']]
        for r in rows:
            if r['key'] in DISPUTED: r['interpretation'] = 'disputed-contract-expectation'
        return dict(release=n, seconds=seconds, reused=False, usage=u, code=code_metrics(snapshot),
                    snapshot_files=hashes(snapshot), session_sha256=hashlib.sha256(state['session_id'].encode()).hexdigest(),
                    cases=rows, passed=receipt['counts'].get('passed',0), total=len(rows),
                    summary_sha256=receipt['summary_sha256'], previous_counts=None, changes=[], repeatability=receipt['repeatability'],
                    usage_phases=phases, evaluation_lane=evaluation_lane or lane)

    def finish(row, retained_path, snapshot):
        history = job(row['id'], 5, retained_path, True)
        retained = [compact_result(r) for r in read(retained_path/'summary.json')]
        stages = row['releases']; final = stages[-1]; families = {}
        for c in final['cases']: families.setdefault(c['family'], Counter()).update([c['status']])
        filename = row['id'] + '-m5-source.tar.gz'; archive(snapshot, archives / filename)
        row.update(model=MODEL, effort='xhigh', harness='Codex CLI', codex_cli_version='0.164.0', cohort='2026-10-26/27',
                   seconds=sum(s['seconds'] for s in stages), reused_seconds=0, new_seconds=sum(s['seconds'] for s in stages),
                   usage=sum_usage(stages), reused_usage=sum_usage([]), new_usage=sum_usage(stages), code=final['code'],
                   passed=final['passed'], total=123, retained_passed=history['counts'].get('passed',0), retained_total=20,
                   uncontested_passed=sum(c['status']=='passed' and c['key'] not in DISPUTED for c in final['cases']),
                   uncontested_total=121, cases=final['cases'], families=families, retained=retained,
                   repeatability=final['repeatability'], previous_counts=None, changes=[], retained_changes=[], retained_previous_counts=None,
                   source_archive=dict(file=filename, sha256=sha(archives/filename)),
                   evidence=dict(final_summary_sha256=final['summary_sha256'], retained_summary_sha256=history['summary_sha256'], snapshot_files=final['snapshot_files']),
                   pricing_rates=RATES, pricing_verified_on='2026-10-27',
                   runtime=dict(image=IMAGE, virtualization='VZ/aarch64', elixir='1.20.2', otp='29.0.4', postgres='17.11'))
        assert len({s['session_sha256'] for s in stages}) == 5
        return row

    supplementary = []
    for sample in range(1,4):
        num = f'{sample:02}'
        strict = original / 'runs' / ('terra61-xhigh-'+num)
        state = read(strict / 'status.json'); assert state['status'] == 'completed'
        lane = 'terra61-strict-xhigh-' + num
        row = dict(id=lane, sample=sample, group_id='terra61-strict-xhigh', cohort_label='strict one-turn', protocol='fresh-session-per-release', releases=[], independent_fresh_m1=True)
        for s in state['completed']:
            n = s['milestone']; snapshot = Path(s['snapshot'])
            runtime = read(strict / ('runtime.json' if n==5 else f'runtimes/milestone-{n}.json'))
            assert runtime['image_id'] == IMAGE and runtime['container_id'] == s['runtime_container_id']
            if n < 5:
                for db in read(strict / f'databases/milestone-{n}/manifest.json'): assert sha(Path(db['path'])) == db['sha256']
            row['releases'].append(stage(lane,n,strict,snapshot,s,strict/f'evaluation/api-m{n}',s['seconds']))
        data['runs'].append(finish(row,strict/'evaluation/retained',Path(state['completed'][-1]['snapshot'])))

        chain = store / f'terra61-assisted-final-chain-{num}-20261027'
        watcher = read(store / f'terra61-final-stage-20261027-v2/STATUS-{num}.json')
        assert watcher['status']=='completed_pending_audit' and not watcher['case_errors_require_diagnosis']
        mapping = read(chain/'SOURCE_MAP.json'); assert mapping['branch']==sample
        lane = 'terra61-assisted-xhigh-' + num
        row = dict(id=lane, sample=sample, group_id='terra61-assisted-xhigh', cohort_label='completion-assisted', protocol='completion-assisted-handoff',
                   paired_strict_run='terra61-strict-xhigh-'+num, independent_fresh_m1=False, releases=[])
        for item in mapping['release_sources']:
            n = item['milestone']; root = Path(item['source']); s = controller.validate_probe(root,n)
            assert sha(root/'RESULT.json') == item['source_result_sha256']
            assert hashes(chain/f'snapshots/milestone-{n}') == s['snapshot_sha256']
            assert s['same_session_verified'] and s['originals_unchanged']
            probe_spec = importlib.util.spec_from_file_location('probe_audit',root/'probe.py')
            probe = importlib.util.module_from_spec(probe_spec); probe_spec.loader.exec_module(probe)
            assert probe.original_evidence() == read(root/'ORIGINAL_HASHES.json')
            first_seconds=s['original_stage_seconds']; extra_seconds=s['additional_seconds']
            st = stage(lane,n,root,root/'snapshot',s,root/f'evaluation/api-m{n}',first_seconds+extra_seconds)
            assert len(st['usage_phases'])==2
            parent = Path(s['original'])
            if n<=2:
                before = read(parent/'status.json')['completed'][n-1]
                before_path = parent/f'evaluation/api-m{n}'
                before_lane = ('terra61-strict-xhigh-' if n==1 else 'terra61-m1-assisted-xhigh-')+num
            else:
                before_path = parent/f'evaluation/api-m{n}'; before_lane=f'terra61-before-r{n}-'+num
            before_receipt=job(before_lane,n,before_path)
            before_rows=read(before_path/'summary.json')['results']
            before_snapshot=Path(before['snapshot']) if n<=2 else parent/'snapshot'
            before_pass={c['key'] for c in before_rows if c['status']=='passed'}
            after_pass={c['key'] for c in st['cases'] if c['status']=='passed'}
            st.update(completion_nudges=1, initial_seconds=first_seconds, additional_seconds=extra_seconds,
                      initial_usage=st['usage_phases'][0], additional_usage=st['usage_phases'][1],
                      initial_code=code_metrics(before_snapshot), initial_cases=[compact_result(c) for c in before_rows],
                      initial_passed=before_receipt['counts'].get('passed',0), initial_summary_sha256=before_receipt['summary_sha256'],
                      initial_evaluation_lane=before_lane, gained_cases=sorted(after_pass-before_pass), lost_cases=sorted(before_pass-after_pass))
            row['releases'].append(st)
            audit.append(dict(lane=lane,milestone=n,result_sha256=sha(root/'RESULT.json'),source_map_sha256=sha(chain/'SOURCE_MAP.json'),
                              session_id=s['session_id'],runtime_container_id=s['runtime_container_id'],snapshot_sha256=s['snapshot_sha256'],
                              input_receipt=s['input_receipt'],database_manifest_sha256=sha(root/'databases/manifest.json')))
        row['initial_seconds']=sum(s['initial_seconds'] for s in row['releases'])
        row['additional_seconds']=sum(s['additional_seconds'] for s in row['releases'])
        row['completion_nudges']=5
        data['runs'].append(finish(row,chain/'evaluation/retained',chain/'snapshots/milestone-5'))

        middle = store / f'terra61-recovered-trajectories-20261026/runs/terra61-recovered-{num}'
        ms=read(middle/'status.json'); assert ms['status']=='completed'
        lane='terra61-m1-assisted-xhigh-'+num
        mid=dict(id=lane,sample=sample,group_id='terra61-m1-assisted-xhigh',cohort_label='M1 assistance only',protocol='m1-assisted-handoff',
                 independent_fresh_m1=False,paired_strict_run='terra61-strict-xhigh-'+num,releases=[])
        for s in ms['completed']:
            n=s['milestone']; snapshot=Path(s['snapshot'])
            if n==1:
                st=deepcopy(row['releases'][0]); st['evaluation_lane']='terra61-assisted-xhigh-'+num
                assert hashes(snapshot)==st['snapshot_files']
            else:
                if n < 5:
                    for db in read(middle/f'databases/milestone-{n}/manifest.json'): assert sha(Path(db['path']))==db['sha256']
                st=stage(lane,n,middle,snapshot,s,middle/f'evaluation/api-m{n}',s['seconds'])
            mid['releases'].append(st)
        supplementary.append(finish(mid,middle/'evaluation/retained',Path(ms['completed'][-1]['snapshot'])))

    assert data['runs'][:17]==old_runs and public['jobs'][:102]==old_jobs
    assert len(public['jobs'])==162
    assert sum(sum(j['counts'].values()) for j in public['jobs'])==10777
    assert sum(j.get('exceptions',0) for j in public['jobs'])==13
    data.update(version=VERSION,date='2026-10-27',supplementary_runs=supplementary)
    data['pricing']['rates'][MODEL]=RATES
    data['pricing']['terra']=dict(verified_on='2026-10-27',dated_launch_rates=RATES,publication_rates=RATES,
        long_threshold=272000,long_input_multiplier=2,long_output_multiplier=1.5,
        source='https://developers.openai.com/api/docs/pricing',
        limitation='Standard API equivalents, not subscription bills. Archived request records only; interrupted requests without usage receipts may be missing.')
    data['terra_protocol']=dict(paired_starts=3,strict_turns_per_release=1,max_completion_nudges_per_release=1,
        completion_decision='Explicit incomplete delivery, not private scores; latest submitted artifact carried forward.',
        supplementary='M1-assisted-only branches are paired intermediate experiments, not additional independent samples.',
        timing='Assisted totals include initial and nudge implementation; discarded alternative branches and evaluator time excluded.',
        compatibility='Codex CLI 0.164.0 and rebuilt VZ runtime differ from older cohorts; parallel candidates shared the host. No measured contention penalty or provider/host time split.')
    data['qualification'].update(jobs=162,scenario_outcomes=10777,snapshot_count=130,incremental_jobs=60,regression_tests=92,
        main_snapshot_rows=115,supplementary_snapshot_rows=15,paired_normal_snapshot_rows=9,unique_api_snapshot_jobs=136,
        evaluator_exceptions=13,candidate_contract_error_occurrences=13,execution_failures=0)
    data['incremental_publication']=dict(baseline_version='1.5.0',evaluator_changed=False,old_jobs_rerun=False,
        completed_work_verified_from_raw_evidence=True,new_unique_jobs=60,main_comparison_runs=23,supplementary_paired_runs=3)
    public['version']=VERSION
    write(output/'results.json',data);write(output/'EVALUATION_R4.json',public)
    (output/'data.js').write_text('window.BILLING_RESULTS = '+json.dumps(data)+';\n')
    write(output.parent/'TERRA_PRIVATE_AUDIT.json',dict(status='verified',releases=audit,jobs=162,scenario_outcomes=10777))
    for r in data['runs'][17:]+supplementary:
        print(r['id'],[s['passed'] for s in r['releases']],r['retained_passed'],round(r['seconds']/60,2),
              r['usage']['api_equivalent_usd'],r['code']['production'],r['code']['test'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('base','original','store','freeze','output','archives'): p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();export(a.base,a.original,a.store,a.freeze,a.output,a.archives)
