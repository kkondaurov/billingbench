#!/usr/bin/env python3
"""Append three unnudged Terra max samples, preserving every earlier row/job."""
import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from export_r3 import DISPUTED, sum_usage
from export_terra import IMAGE, MODEL, TOTALS, hashes, usage_records
from export_v1 import archive, code_metrics, compact_result, read, sha, write

VERSION = '1.7.0'
RATES = [1, .05, 5]


def session_usage(root, stage):
    files = list((root/'sessions').rglob(f'rollout-*{stage["session_id"]}.jsonl'))
    assert len(files) == 1
    rows = [json.loads(line) for line in files[0].read_text().splitlines() if line.strip()]
    contexts = [r['payload'] for r in rows if r['type'] == 'turn_context']
    assert len(contexts) == 1 and contexts[0]['model'] == MODEL and contexts[0]['effort'] == 'max'
    meta = [r['payload'] for r in rows if r['type'] == 'session_meta']
    assert len(meta) == 1 and meta[0]['cli_version'] == '0.164.0'
    ends = [i for i,r in enumerate(rows) if r.get('type') == 'event_msg' and r['payload'].get('type') == 'task_complete']
    assert len(ends) == 1, 'Max cohort must have exactly one delivery per release, with no nudge'
    assert not any(r['type'] == 'token_usage_record' for r in rows[ends[0]+1:])
    records = [r for r in rows[:ends[0]+1] if r['type'] == 'token_usage_record']
    assert all(r['payload']['session_id'] == stage['session_id'] for r in records)
    usage = usage_records(rows[:ends[0]+1])
    usage['source_sha256'] = {'request_records': sha(files[0])}
    return usage


def common_price(stages):
    total = Decimal(0)
    for stage in stages:
        for kind, bucket in stage['usage']['pricing_buckets'].items():
            total += ((Decimal(bucket.get('input_tokens',0)-bucket.get('cached_input_tokens',0)) +
                       Decimal(bucket.get('cached_input_tokens',0))*Decimal('.05'))*(2 if kind=='long' else 1) +
                      Decimal(bucket.get('output_tokens',0))*5*(Decimal('1.5') if kind=='long' else 1))/1000000
    return float(total)


def checked_job(path, expected, retained=False):
    summary = read(path/'summary.json')
    assert retained or summary['status'] == 'completed'
    rows = summary if retained else summary['results']
    assert len(rows) == len(expected) == len({r['key'] for r in rows})
    assert {r['key'] for r in rows} == {r['key'] for r in expected}
    assert all(r['status'] in ('passed','failed') for r in rows), 'Unexpected case errors need diagnosis'
    for row in rows:
        assert read(path/('' if retained else 'cases')/(row['key']+'.json'))['result'] == row
    return rows


def export(base, evidence, freeze, output, archives):
    data, public = read(base/'results.json'), read(base/'EVALUATION_R4.json')
    assert data['version'] == '1.6.0' and len(data['runs']) == 23 and len(public['jobs']) == 162
    old_runs, old_supplementary, old_jobs = deepcopy(data['runs']), deepcopy(data['supplementary_runs']), deepcopy(public['jobs'])
    audit = read(evidence/'COMPLETION_AUDIT.json')
    assert audit['status'] == 'verified_scored_completion' and audit['scoring_jobs'] == 18 and audit['case_errors'] == 0
    assert audit['completion_nudges'] == audit['additional_m1_turns'] == 0
    assert sha(freeze/'MANIFEST.json') == 'ca1de4f5b677291d326501ffcdca642fe75e89b635ef5e8df620d07f840de5a7'
    assert hashes(freeze/'harness') == read(freeze/'MANIFEST.json')['harness_sha256']
    spec = importlib.util.spec_from_file_location('_max_publication_recovery',evidence/'recovery.py')
    recovery = importlib.util.module_from_spec(spec);spec.loader.exec_module(recovery);recovery.verify()
    source = freeze/'harness/benchmark/v1';baseline = old_runs[0]
    all_sessions, all_runtimes = set(), set()

    def job(lane, name, n):
        path = evidence/'runs'/lane/'evaluation'/name;retained = name == 'retained'
        expected = baseline['retained'] if retained else baseline['releases'][n-1]['cases']
        rows = checked_job(path,expected,retained)
        copied = path/'evaluator-source' if retained else path/'evaluator-source/billing_eval'
        assert hashes(copied) == hashes(source/'evaluation/0.5/billing_eval')
        assert sha(path/('evaluate_retained.py' if retained else 'evaluator-source/evaluate.py')) == sha(source/('evaluate_retained_v05.py' if retained else 'evaluate_v05.py'))
        receipt = dict(lane=lane,kind='retained' if retained else 'api',milestone=n,summary_sha256=sha(path/'summary.json'),
            counts=dict(Counter(r['status'] for r in rows)),old_counts=None,
            uncontested_counts=dict(Counter(r['status'] for r in rows if r['key'] not in DISPUTED)),changes=[],
            repeatability={r['key']:[p['status'] for p in r['repetitions']] for r in rows if 'repetitions' in r},
            exceptions=0,complete_case_inventory=True,evaluation_basis='Unchanged frozen R4',exit_code=0)
        public['jobs'].append(receipt)
        cases = [compact_result(r) for r in rows]
        for c in cases:
            if c['key'] in DISPUTED:c['interpretation']='disputed-contract-expectation'
        return cases,receipt

    for sample in range(1,4):
        lane = f'terra61-max-{sample:02}';root = evidence/'runs'/lane
        state = read(root/'status.json');autonomy = read(evidence/(lane+'-AUTONOMY.json'))
        measured = next(r for r in audit['runs'] if r['id'] == lane)
        assert state['status'] == 'completed' and len(state['completed']) == len(autonomy['releases']) == 5
        assert state['model'] == MODEL and state['effort'] == 'max' and autonomy['completion_nudges'] == 0
        assert autonomy['active_runtime_stopped'] and autonomy['status'] == measured['autonomy_status']
        m1 = read(root/'M1_RECOVERY.json')
        assert m1['additional_m1_model_turns'] == 0 and m1['source_unchanged']
        for name,digest in m1['original_evidence'].items(): assert sha(recovery.ORIGINAL/name) == digest
        row = dict(id=lane,model=MODEL,effort='max',sample=sample,group_id='terra61-max',cohort_label='autonomous',
            protocol='autonomous-delivery-gated-handoff',harness='Codex CLI',codex_cli_version='0.164.0',cohort='2026-11-08',
            independent_fresh_m1=True,completion_nudges=0,declared_incomplete=measured['stopped_incomplete'],
            pricing_rates=RATES,pricing_verified_on='2026-11-08',releases=[],
            runtime=dict(image=IMAGE,virtualization='VZ/aarch64',elixir='1.20.2',otp='29.0.4',postgres='17.11'))
        for s,checked in zip(state['completed'],measured['releases'],strict=True):
            n=s['milestone'];snapshot=Path(s['snapshot'])
            assert hashes(snapshot)==s['sha256'] and abs(s['seconds']-checked['seconds'])<1e-8
            for name,digest in s['input_receipt']['sha256'].items():assert sha(snapshot/name)==digest
            assert s['session_id'] not in all_sessions;all_sessions.add(s['session_id'])
            runtime=read(root/('runtime.json' if n==5 else f'runtimes/milestone-{n}.json'))
            assert runtime['image_id']==IMAGE and runtime['container_id']==s['runtime_container_id']
            assert runtime['container_id'] not in all_runtimes;all_runtimes.add(runtime['container_id'])
            for db in read(root/f'databases/milestone-{n}/manifest.json'):assert sha(Path(db['path']))==db['sha256']
            usage=session_usage(root,s);assert usage['api_equivalent_usd']==checked['usage']['api_equivalent_usd']
            cases,receipt=job(lane,f'api-m{n}',n);code=code_metrics(snapshot)
            assert (code['production'],code['test'])==(checked['production_loc'],checked['test_loc'])
            row['releases'].append(dict(release=n,seconds=s['seconds'],reused=False,usage=usage,code=code,
                snapshot_files=s['sha256'],session_sha256=hashlib.sha256(s['session_id'].encode()).hexdigest(),
                cases=cases,passed=receipt['counts'].get('passed',0),total=len(cases),summary_sha256=receipt['summary_sha256'],
                previous_counts=None,changes=[],repeatability=receipt['repeatability'],completion_nudges=0,
                declared_incomplete=autonomy['releases'][n-1]['declared_incomplete']))
        retained,history=job(lane,'retained',5);final=row['releases'][-1]
        families={}
        for c in final['cases']:families.setdefault(c['family'],Counter()).update([c['status']])
        filename=lane+'-m5-source.tar.gz';archive(Path(state['completed'][-1]['snapshot']),archives/filename)
        row.update(seconds=sum(s['seconds'] for s in row['releases']),reused_seconds=0,new_seconds=sum(s['seconds'] for s in row['releases']),
            usage=sum_usage(row['releases']),reused_usage=sum_usage([]),new_usage=sum_usage(row['releases']),code=final['code'],
            passed=final['passed'],total=123,retained_passed=history['counts'].get('passed',0),retained_total=20,
            uncontested_passed=sum(c['status']=='passed' and c['key'] not in DISPUTED for c in final['cases']),uncontested_total=121,
            cases=final['cases'],families=families,retained=retained,repeatability=final['repeatability'],
            previous_counts=None,changes=[],retained_changes=[],retained_previous_counts=None,
            source_archive=dict(file=filename,sha256=sha(archives/filename)),
            evidence=dict(final_summary_sha256=final['summary_sha256'],retained_summary_sha256=history['summary_sha256'],
                snapshot_files=final['snapshot_files'],completion_audit_sha256=sha(evidence/'COMPLETION_AUDIT.json'),
                m1_readout_recovery=True,additional_m1_model_turns=0),
            cost_limitation='Archived-request API equivalents, not subscription bills; unrecorded interrupted usage may be missing.')
        assert row['passed']==measured['final_passed'] and abs(row['usage']['api_equivalent_usd']-measured['api_equivalent_usd'])<1e-7
        assert abs(row['seconds']-measured['seconds'])<1e-7 and row['retained_passed']==measured['retained_counts'].get('passed',0)
        assert row['declared_incomplete']==(sample==2), 'Retain the incomplete M5 submission in the full cohort'
        data['runs'].append(row)
    assert data['runs'][:23]==old_runs and data['supplementary_runs']==old_supplementary and public['jobs'][:162]==old_jobs
    assert len(public['jobs'])==180 and sum(sum(j['counts'].values()) for j in public['jobs'])==11935
    assert sum(j.get('exceptions',0) for j in public['jobs'])==13
    for row in data['runs']+data['supplementary_runs']:
        if row['model']!=MODEL:continue
        stages=row['releases'];dollars=common_price(stages)
        assert abs(dollars-row['usage']['api_equivalent_usd'])<1e-7
        data['comparable_costs'][row['id']]=dict(api_equivalent_usd=dollars,
            reused_api_equivalent_usd=common_price([s for s in stages if s['reused']]),
            new_api_equivalent_usd=common_price([s for s in stages if not s['reused']]),
            releases=[common_price([s]) for s in stages])
    data['pricing']['terra_comparison']=dict(rates=RATES,verified_on='2026-11-08',source='https://developers.openai.com/api/docs/pricing',
        long_threshold=272000,long_input_and_cache_multiplier=2,long_output_multiplier=1.5,
        scope='All Terra max and xhigh request mixes repriced at one Standard quote. Dated Terra quotes are identical; DeepSeek keeps its existing common-rate basis.')
    data['terra_max_protocol']=dict(independent_starts=3,completion_nudges=0,
        incomplete_final_submission='Run 2 admitted unfinished M5 corrections. It remains in every aggregate and has all six scores; no completion nudge was sent.',
        recovery='Completed M1 sessions were archived/snapshotted under Python 3.12 after a host Python 3.9 archive failure; no model work repeated. Recovery waiting excluded from implementation time.',
        compatibility='Same pinned CLI 0.164.0, image and prompts as earlier Terra xhigh; later cohort date and independent starts. Three candidates shared the host; no invented contention adjustment.')
    data.update(version=VERSION,date='2026-11-08')
    data['qualification'].update(jobs=180,scenario_outcomes=11935,snapshot_count=145,incremental_jobs=18,
        main_snapshot_rows=130,supplementary_snapshot_rows=15,paired_normal_snapshot_rows=9,unique_api_snapshot_jobs=151,regression_tests=97)
    data['incremental_publication']=dict(baseline_version='1.6.0',evaluator_changed=False,old_jobs_rerun=False,
        completed_work_verified_from_raw_evidence=True,new_unique_jobs=18,main_comparison_runs=26,supplementary_paired_runs=3)
    public['version']=VERSION
    write(output/'results.json',data);write(output/'EVALUATION_R4.json',public)
    (output/'data.js').write_text('window.BILLING_RESULTS = '+json.dumps(data)+';\n')
    print('Verified 26 headline rows + 3 supplementary branches, 180 jobs / 11935 outcomes; prior rows and receipts unchanged.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','evidence','freeze','output','archives'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();export(args.base,args.evidence,args.freeze,args.output,args.archives)
