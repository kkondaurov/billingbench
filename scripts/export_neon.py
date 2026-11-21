#!/usr/bin/env python3
"""Verify and append a single-turn Antigravity run to the frozen R4 comparison."""
import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from export_r3 import DISPUTED, FIELDS
from export_sol62 import FREEZE_HASH
from export_terra import TOTALS, hashes
from export_terra_max import checked_job
from export_v1 import archive, code_metrics, compact_result, read, sha, write

LANE, MODEL, VERSION = 'neon-xhigh-01', 'gemini-4-neon-xhigh', '1.10.0'
DATE, RATES = '2026-11-20', [3, .15, 15]
PRICING = 'https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-neon/'


@dataclass(frozen=True)
class Publication:
    lane: str
    model: str
    effort: str
    cohort: str
    version: str
    baseline_version: str
    date: str
    rates: tuple[float, float, float]
    pricing_url: str
    pricing_key: str
    regression_tests: int


NEON = Publication(LANE, MODEL, 'xhigh', '2026-11-19', VERSION, '1.9.0',
                   DATE, tuple(RATES), PRICING, 'neon', 100)


def session_usage(stage, publication=NEON):
    log = Path(stage['log'])
    events = [json.loads(line) for line in log.read_text().splitlines()]
    heads = [e for e in events if e['event'] == 'init']
    deliveries = [e['result'] for e in events if e['event'] == 'result']
    assert len(heads) == len(deliveries) == 1 and heads[0]['init']['model'] == publication.model
    result, session = deliveries[0], stage['session_id']
    assert heads[0]['conversation_id'] == result['conversation_id'] == session
    assert events[-1]['event'] == 'result' and result['status'] == 'SUCCESS' and result['num_turns'] == 1
    raw = result['usage']
    assert raw == stage['usage']
    assert raw['total_tokens'] == raw['input_tokens'] + raw['output_tokens']
    assert 0 <= raw['thinking_tokens'] <= raw['output_tokens']
    uncached, cached, output = (raw[k] for k in ('input_tokens', 'cache_read_tokens', 'output_tokens'))
    input_rate, cached_rate, output_rate = publication.rates
    return dict(input_tokens=uncached+cached, cached_input_tokens=cached, output_tokens=output,
                reasoning_output_tokens=raw['thinking_tokens'], requests=None,
                cache_write_5m_tokens=0, cache_write_1h_tokens=0, cli_cumulative_receipt=raw,
                api_equivalent_usd=(uncached*input_rate+cached*cached_rate+output*output_rate)/1e6,
                boundary_verified=True, source_sha256={'agy_ndjson': sha(log)})


def sum_usage(stages):
    fields = (*FIELDS[:6], 'api_equivalent_usd')
    return dict({k: sum(s['usage'][k] for s in stages) for k in fields},
                requests=None if stages else 0, boundary_verified=True)


def export(base, evidence, freeze, output, archives, *, publication=NEON):
    lane, model, effort = publication.lane, publication.model, publication.effort
    data, public = read(base/'results.json'), read(base/'EVALUATION_R4.json')
    assert data['version'] == public['version'] == publication.baseline_version
    assert not any(r['id'] == lane for r in data['runs'])
    qualification = data['qualification']
    prior_jobs = len(public['jobs'])
    assert qualification['jobs'] == prior_jobs
    assert sha(freeze/'MANIFEST.json') == FREEZE_HASH
    assert hashes(freeze/'harness') == read(freeze/'MANIFEST.json')['harness_sha256']
    source = freeze/'harness/benchmark/v1'
    packet = hashes(source/'candidate/0.5')
    frozen_eval = hashes(source/'evaluation/0.5/billing_eval')
    root = evidence/'runs'/lane
    status, screen, ready = read(root/'status.json'), read(evidence/'SCREEN.json'), read(evidence/'READY.json')
    assert hashes(root/'inputs') == packet and status['status'] == 'completed'
    assert screen['status'] == 'completed_pending_outcome_audit' and len(screen['evaluations']) == 6
    assert (status['model'], status['effort'], status['harness'], status['protocol']) == (model, effort, 'agy', 'handoff')
    assert not status['delegation']
    assert (ready['status'], ready['shell_control'], ready['scaffold_tests']) == ('qualified', 'read_blocked', 4)
    assert (ready['model'], ready['effort'], ready['image']) == (model, effort, status['runtime_image'])
    assert sha(Path(ready['qualification'])/'agy.ndjson') == ready['log_sha256']
    stages = status['completed']
    assert len(stages) == len({s['session_id'] for s in stages}) == len({s['runtime_container_id'] for s in stages}) == 5
    assert ready['conversation_id'] not in {s['session_id'] for s in stages}

    def job(name, n, expected):
        path = root/'evaluation'/name
        retained = name == 'retained'
        rows = checked_job(path, expected, retained)
        assert hashes(path/('evaluator-source' if retained else 'evaluator-source/billing_eval')) == frozen_eval
        assert sha(path/('evaluate_retained.py' if retained else 'evaluator-source/evaluate.py')) == sha(
            source/('evaluate_retained_v05.py' if retained else 'evaluate_v05.py'))
        counts = dict(Counter(r['status'] for r in rows))
        receipt = screen['evaluations'][lane+'/'+name]
        assert receipt['status'] == 'completed' and receipt['case_counts'] == counts and receipt['exit_code'] == 0
        repeatability = {r['key']:[p['status'] for p in r['repetitions']] for r in rows if 'repetitions' in r}
        meta = dict(lane=lane, kind='retained' if retained else 'api', milestone=n,
            summary_sha256=sha(path/'summary.json'), counts=counts, old_counts=None, changes=[],
            uncontested_counts=dict(Counter(r['status'] for r in rows if r['key'] not in DISPUTED)),
            repeatability=repeatability, exceptions=0, complete_case_inventory=True,
            evaluation_basis='Unchanged frozen R4', exit_code=0)
        public['jobs'].append(meta)
        cases = [compact_result(r) for r in rows]
        for case in cases:
            if case['key'] in DISPUTED:
                case['interpretation'] = 'disputed-contract-expectation'
        return cases, meta

    releases = []
    baseline = data['runs'][0]
    for n, stage in enumerate(stages, 1):
        snapshot = root/'snapshots'/f'milestone-{n}'
        assert stage['milestone'] == n and Path(stage['snapshot']) == snapshot and stage['seconds'] > 0
        assert hashes(snapshot) == stage['sha256']
        files = {name for part in read(root/'inputs/manifest.json')['milestones']
                 if part['milestone'] <= n for name in part['files']}
        assert {p.name for p in (snapshot/'requests').iterdir()} == files
        assert all(sha(snapshot/'requests'/name) == packet[name] for name in files)
        assert all(sha(snapshot/name) == digest for name, digest in stage['input_receipt']['sha256'].items())
        runtime = read(root/('runtime.json' if n==5 else f'runtimes/milestone-{n}.json'))
        assert runtime['container_id'] == stage['runtime_container_id'] and runtime['image_id'] == ready['image']
        db_dir = root/'databases'/f'milestone-{n}'
        databases = read(db_dir/'manifest.json')
        assert {db['database'] for db in databases} == {'field_desk','field_desk_test'}
        for db in databases:
            path = db_dir/(db['database']+'.dump')
            assert Path(db['path']) == path and sha(path) == db['sha256']
        if n == 5:
            end = read(root/'FINAL_RUNTIME.json')
            assert end['stopped'] and end['runtime_container_id'] == runtime['container_id']
            assert end['image'] == ready['image'] and end['database_checkpoint'] == databases
        cases, meta = job(f'api-m{n}', n, baseline['releases'][n-1]['cases'])
        releases.append(dict(release=n, seconds=stage['seconds'], reused=False, usage=session_usage(stage, publication),
            code=code_metrics(snapshot), snapshot_files=stage['sha256'],
            session_sha256=hashlib.sha256(stage['session_id'].encode()).hexdigest(),
            cases=cases, passed=meta['counts']['passed'], total=TOTALS[n-1], summary_sha256=meta['summary_sha256'],
            previous_counts=None, changes=[], repeatability=meta['repeatability'], completion_nudges=0))
    retained, history = job('retained', 5, baseline['retained'])
    final = releases[-1]
    families = {}
    for case in final['cases']:
        families.setdefault(case['family'], Counter()).update([case['status']])
    file = lane+'-m5-source.tar.gz'
    archive(root/'snapshots/milestone-5', archives/file)
    seconds, usage = sum(r['seconds'] for r in releases), sum_usage(releases)
    data['runs'].append(dict(id=lane, model=model, effort=effort, sample=1, group_id=lane.rsplit('-', 1)[0],
        protocol='fresh-session-per-release', harness='Antigravity CLI', agy_cli_version='1.5.12', cohort=publication.cohort,
        independent_fresh_m1=True, completion_nudges=0, pricing_rates=list(publication.rates), pricing_verified_on=publication.date,
        runtime=dict(image=ready['image'], virtualization='VZ/aarch64',
                     elixir='1.20.2', otp='29.0.4', postgres='17.11'), releases=releases,
        seconds=seconds, reused_seconds=0, new_seconds=seconds, usage=usage, reused_usage=sum_usage([]),
        new_usage=usage, code=final['code'], passed=final['passed'], total=123,
        retained_passed=history['counts']['passed'], retained_total=20,
        uncontested_passed=sum(c['status']=='passed' and c['key'] not in DISPUTED for c in final['cases']),
        uncontested_total=121, cases=final['cases'], families=families, retained=retained,
        repeatability=final['repeatability'], previous_counts=None, changes=[], retained_changes=[],
        retained_previous_counts=None, source_archive=dict(file=file, sha256=sha(archives/file)),
        evidence=dict(final_summary_sha256=final['summary_sha256'], retained_summary_sha256=history['summary_sha256'],
                      snapshot_files=final['snapshot_files']),
        cost_limitation='Published Gemini API token rates applied to Antigravity totals. Not a subscription bill. '
                        'Storage and any unreported usage are excluded.'))
    jobs = public['jobs']
    assert len({(j['lane'],j['kind'],j['milestone']) for j in jobs}) == len(jobs) == prior_jobs + 6
    outcomes = sum(sum(j['counts'].values()) for j in jobs)
    assert outcomes == qualification['scenario_outcomes'] + sum(TOTALS) + 20
    assert sum(j.get('exceptions', 0) for j in jobs) == qualification['evaluator_exceptions']
    data['pricing']['rates'][model] = list(publication.rates)
    data['pricing'][publication.pricing_key] = dict(verified_on=publication.date, source=publication.pricing_url,
        api_token_rates=list(publication.rates), native_subscription_charge=False)
    data.update(version=publication.version, date=publication.date)
    qualification.update(jobs=len(jobs), scenario_outcomes=outcomes, snapshot_count=qualification['snapshot_count']+5,
        incremental_jobs=6, main_snapshot_rows=len(data['runs'])*5,
        unique_api_snapshot_jobs=sum(j['kind']=='api' for j in jobs), regression_tests=publication.regression_tests)
    data['incremental_publication'] = dict(baseline_version=publication.baseline_version, evaluator_changed=False,
        old_jobs_rerun=False, completed_work_verified_from_raw_evidence=True, new_unique_jobs=6,
        main_comparison_runs=len(data['runs']), supplementary_paired_runs=len(data['supplementary_runs']))
    public['version'] = publication.version
    write(output/'results.json', data)
    write(output/'EVALUATION_R4.json', public)
    (output/'data.js').write_text('window.BILLING_RESULTS = '+json.dumps(data)+';\n')
    print(f'Verified {lane}: five releases, six R4 jobs, and {sum(TOTALS) + 20} outcomes.')


def main(publication=NEON):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base','evidence','freeze','output','archives'):
        parser.add_argument('--'+name, type=Path, required=True)
    export(**vars(parser.parse_args()), publication=publication)


if __name__ == '__main__':
    main()
