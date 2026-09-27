#!/usr/bin/env python3
"""Export audited results, not transcripts, from the local evidence archive."""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

LANES = ['astra-low-01', 'astra-low-02', 'astra-low-03', 'astra-xhigh-01',
         'sol6-xhigh-01', 'sol6-xhigh-02', 'sol6-xhigh-03', 'sol6-low-01']
OLD = set(LANES[:2] + LANES[4:6])
RATES = {'gpt-6-astra': [10, 1, 50], 'gpt-6-sol': [2, .2, 10]}
FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def code_files(snapshot):
    files = [p for folder in ('lib', 'test', 'config', 'priv')
             for p in (snapshot / folder).rglob('*') if p.is_file()]
    files += [snapshot / name for name in ('mix.exs', 'mix.lock', '.formatter.exs')
              if (snapshot / name).is_file()]
    for path in files:
        assert not path.is_symlink(), path
        assert not any(part in ('deps', '_build', '.env', '.git') for part in path.relative_to(snapshot).parts)
    return sorted(files)


def code_metrics(snapshot):
    rows = []
    for path in code_files(snapshot):
        relative = path.relative_to(snapshot).as_posix()
        lines = len(path.read_bytes().splitlines())
        category = ('production' if relative.startswith(('lib/', 'priv/repo/migrations/'))
                    else 'test' if relative.startswith('test/') else 'configuration')
        rows.append(dict(path=relative, lines=lines, category=category, sha256=sha(path)))
    prod = [r for r in rows if r['category'] == 'production']
    return dict(production=sum(r['lines'] for r in prod),
                test=sum(r['lines'] for r in rows if r['category'] == 'test'),
                production_files=len(prod), largest=max(prod, key=lambda r: r['lines']), files=rows)


def archive(snapshot, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('wb') as output, gzip.GzipFile(fileobj=output, mode='wb', mtime=0, filename='') as gz:
        with tarfile.open(fileobj=gz, mode='w') as tar:
            for path in code_files(snapshot):
                data = path.read_bytes()
                info = tarfile.TarInfo(path.relative_to(snapshot).as_posix())
                info.size, info.mode = len(data), 0o644
                tar.addfile(info, io.BytesIO(data))


def usage(directory, target, model):
    # Price archived requests through the fifth completed delivery, excluding
    # M6. CLI cumulative counters are retained separately, not added together.
    records, total, dollars, long_requests = set(), Counter(), Decimal(0), 0
    price_in, price_cache, price_out = map(lambda x: Decimal(str(x)), RATES[model])
    rows, completions = [], {}
    for path in (directory / 'sessions').rglob('rollout-*.jsonl'):
        for line in path.open():
            event = json.loads(line)
            if event.get('type') == 'token_usage_record':
                rows.append(event)
            elif event.get('type') == 'event_msg' and event['payload'].get('type') == 'task_complete':
                completions[event['payload']['turn_id']] = event
    deliveries = sorted(completions.values(), key=lambda r: r['timestamp'])
    assert len(deliveries) >= 5
    cutoff = deliveries[4]['timestamp']
    log = [json.loads(line) for line in (directory / 'logs/milestone-5.jsonl').open()]
    messages = [r['item']['text'] for r in log if r.get('type') == 'item.completed'
                and r.get('item', {}).get('type') == 'agent_message']
    assert deliveries[4]['payload']['last_agent_message'] == messages[-1], 'M5 delivery mismatch'
    for event in sorted(rows, key=lambda r: (r['timestamp'], r.get('ordinal', 0))):
        if event['timestamp'] > cutoff:
            continue
        payload = event['payload']
        key = (payload['session_id'], payload['response_id'])
        if key in records:
            continue
        records.add(key)
        u = payload['usage']
        assert u.get('cache_write_input_tokens', 0) == 0
        inputs, cached, outputs = (u[k] for k in FIELDS[:3])
        assert 0 <= cached <= inputs
        long = inputs > 272000
        long_requests += long
        dollars += ((inputs-cached)*price_in + cached*price_cache)*(2 if long else 1)/1000000
        dollars += outputs*price_out*(Decimal('1.5') if long else 1)/1000000
        total.update({k: u.get(k, 0) for k in FIELDS})
    assert records
    return dict(total, requests=len(records), long_requests=long_requests,
                api_equivalent_usd=float(dollars), boundary_verified=True,
                cli_cumulative_receipt={k: target[k] for k in FIELDS},
                receipt_delta={k: total[k]-target[k] for k in FIELDS})


def compact_result(result):
    return {k: result[k] for k in ('key', 'milestone', 'family', 'criteria', 'status', 'stage', 'error') if k in result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True, help='billingbench .runs directory')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archives', type=Path, required=True)
    args = parser.parse_args()
    root, runs = args.evidence, []
    repaired = root / 'v05-author-audit-20260927'
    scaffold = repaired / 'harness-r1/scaffold'
    for lane in LANES:
        source = root / ('v04-screen-20260926' if lane in OLD else 'v05-expansion-20260927') / lane
        status = read(source / 'status.json')
        stages = [m for m in status['completed'] if m['milestone'] <= 5]
        assert [m['milestone'] for m in stages] == [1, 2, 3, 4, 5]
        stage_metrics = []
        for stage in stages:
            snapshot = source / 'snapshots' / f'milestone-{stage["milestone"]}'
            actual = {p.relative_to(snapshot).as_posix(): sha(p) for p in snapshot.rglob('*') if p.is_file()}
            assert actual == stage['sha256'], (lane, stage['milestone'], 'snapshot changed')
            stage_metrics.append(dict(release=stage['milestone'], seconds=stage['seconds'],
                                      code=code_metrics(snapshot)))
        final = source / 'snapshots/milestone-5'
        summary_path = repaired / 'r1-results' / lane / 'summary.json'
        summary = read(summary_path)
        assert summary['status'] == 'completed' and len(summary['results']) == 123
        retained_path = root / 'v05-expansion-20260927' / ('legacy' if lane in OLD else '') / lane
        retained_path /= 'retained/summary.json' if lane in OLD else 'evaluation/retained/summary.json'
        retained = read(retained_path)
        assert len(retained) == 20
        timing = source / 'evaluation/performance-m5/summary.json'
        measurements = read(timing).get('measurements', []) if timing.exists() else []
        # Keep only explicit measurement fields, never workspace or auth state.
        performance = [{k: r[k] for k in ('operation', 'customers', 'functional_status',
                        'latency_status', 'median_seconds') if k in r} for r in measurements]
        outcomes = [compact_result(r) for r in summary['results']]
        for result in outcomes:
            disputed = (lane in ('astra-low-02', 'astra-low-03') and
                        result['key'].startswith('interaction-concession-termination-retained-'))
            disputed |= (lane == 'sol6-xhigh-03' and (result['key'].startswith('v03-source-ownership-') or
                          result['key'] == 'v04-mixed-paid-source-chain-reclassified-termination'))
            if disputed:
                result['interpretation'] = 'disputed-output-semantics'
            if lane == 'sol6-xhigh-03' and 'POST /customers:' in result.get('error', ''):
                result['common_blocker'] = 'parent-linked-customer-creation'
        grouped = {}
        for result in outcomes:
            counts = grouped.setdefault(result['family'], Counter())
            counts[result['status']] += 1
        filename = f'{lane}-m5-source.tar.gz'
        archive(final, args.archives / filename)
        row = dict(id=lane, model=status['model'], effort=status['effort'],
                   sample=int(lane[-2:]), cohort='2026-09-26' if lane in OLD else '2026-09-27',
                   seconds=sum(m['seconds'] for m in stages), passed=summary['counts']['passed'], total=123,
                   retained_passed=sum(r['status'] == 'passed' for r in retained), retained_total=20,
                   usage=usage(source, stages[-1]['usage'], status['model']), code=code_metrics(final),
                   releases=stage_metrics, families=grouped, cases=outcomes,
                   retained=[{k: r[k] for k in ('key', 'status', 'stage', 'error') if k in r} for r in retained],
                   performance=performance,
                   source_archive=dict(file=filename, sha256=sha(args.archives / filename)),
                   evidence=dict(final_summary_sha256=sha(summary_path),
                                 retained_summary_sha256=sha(retained_path),
                                 snapshot_files=stages[-1]['sha256']))
        runs.append(row)
        print(lane, row['passed'], row['code']['production'], row['code']['test'],
              round(row['seconds']/60, 1), round(row['usage']['api_equivalent_usd'], 2))
    dataset = dict(version='1.0.0', date='2026-09-27', evaluator='R1',
                   pricing=dict(verified_on='2026-09-27', rates=RATES,
                                units='USD per million: input, cached input, output',
                                long_threshold=272000, long_input_multiplier=2, long_output_multiplier=1.5,
                                sources=[f'https://developers.openai.com/api/docs/models/{m}' for m in RATES]),
                   scaffold=code_metrics(scaffold), runs=runs)
    write(args.output / 'results.json', dataset)
    (args.output / 'data.js').write_text('window.BILLING_RESULTS = ' + json.dumps(dataset) + ';\n')


if __name__ == '__main__':
    main()
