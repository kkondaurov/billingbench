#!/usr/bin/env python3
"""Export verified fresh-session evidence without publishing sessions or credentials."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from export_v1 import archive, code_metrics, compact_result, read, sha, write

VERSION = '1.1.0'
RATES = {'gpt-6-astra': [10, 1, 50], 'gpt-6-sol': [2, .2, 10],
         'gpt-6-luna': [.1, .01, .5], 'claude-opus-5-5': [4, .2, 20]}
FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_5m_tokens',
          'cache_write_1h_tokens', 'output_tokens', 'reasoning_output_tokens', 'requests', 'long_requests')
DISPUTED = {'interaction-concession-termination-retained-27000', 'interaction-held-correction-new-month'}


def events(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def price(usage, model):
    pi, pc, po = map(lambda x: Decimal(str(x)), RATES[model])
    cost = ((usage['input_tokens'] - usage['cached_input_tokens'] -
             usage.get('cache_write_5m_tokens', 0) - usage.get('cache_write_1h_tokens', 0)) * pi +
            usage['cached_input_tokens'] * pc + usage.get('cache_write_5m_tokens', 0) * pi * Decimal('1.25') +
            usage.get('cache_write_1h_tokens', 0) * pi * 2)
    long = model.startswith('gpt-') and usage['input_tokens'] > 272000
    return (cost * (2 if long else 1) + usage['output_tokens'] * po * (Decimal('1.5') if long else 1)) / 1000000


def codex_usage(directory, stage, model):
    source = Path(stage.get('inherited_from', directory))
    files = list((source / 'sessions').rglob(f'rollout-*{stage["session_id"]}.jsonl'))
    assert len(files) == 1, (source, stage['session_id'], files)
    rows = events(files[0])
    deliveries = [e for e in rows if e.get('type') == 'event_msg' and e['payload'].get('type') == 'task_complete']
    cutoff = deliveries[0]['timestamp'] if stage.get('inherited_from') else deliveries[-1]['timestamp']
    log = events(Path(stage['log']))
    messages = [e['item']['text'] for e in log if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message']
    delivery = next(e for e in deliveries if e['timestamp'] == cutoff)
    assert delivery['payload']['last_agent_message'] == messages[-1], 'Delivery boundary mismatch'
    total, seen, dollars, buckets = Counter(), set(), Decimal(0), {'short': Counter(), 'long': Counter()}
    for e in rows:
        if e.get('type') != 'token_usage_record' or e['timestamp'] > cutoff:
            continue
        p = e['payload']; key = (p['session_id'], p['response_id'])
        if key in seen:
            continue
        seen.add(key)
        u = p['usage']
        assert u.get('cache_write_input_tokens', 0) == 0
        assert 0 <= u['cached_input_tokens'] <= u['input_tokens']
        short = {k: u.get(k, 0) for k in FIELDS[:6]}
        long = u['input_tokens'] > 272000
        total.update(short); buckets['long' if long else 'short'].update(short)
        dollars += price(short, model)
        total['long_requests'] += int(long)
    assert seen
    return dict({k: total[k] for k in FIELDS}, requests=len(seen), api_equivalent_usd=float(dollars),
                pricing_buckets=buckets, boundary_verified=True, source_sha256={'request_records': sha(files[0])},
                basis='deduplicated request records through release delivery; includes compaction'), stage['seconds']


def claude_usage(directory, stage, model):
    source = Path(stage.get('inherited_from', directory))
    files = sorted((source / 'logs').glob(f'milestone-{stage["milestone"]}-attempt-*.jsonl'))
    assert files and files[-1].resolve() == Path(stage['log']).resolve()
    total, dollars, seconds, sources, final, attempts = Counter(), Decimal(0), 0, {}, None, []
    for path in files:
        rows = events(path)
        results = [r for r in rows if r.get('type') == 'result']
        assert len(results) == 1
        r = results[0]; final = r; u = r['usage']
        assert r['session_id'] == stage['session_id']
        assert set(r['modelUsage']) == {model}
        cache = u['cache_creation']
        assert sum(cache.values()) == u['cache_creation_input_tokens']
        assert not any(u.get('server_tool_use', {}).values())
        values = dict(input_tokens=u['input_tokens'] + u['cache_read_input_tokens'] + u['cache_creation_input_tokens'],
                      cached_input_tokens=u['cache_read_input_tokens'],
                      cache_write_5m_tokens=cache['ephemeral_5m_input_tokens'],
                      cache_write_1h_tokens=cache['ephemeral_1h_input_tokens'],
                      output_tokens=u['output_tokens'],
                      reasoning_output_tokens=u['output_tokens_details']['thinking_tokens'])
        total.update(values); dollars += price(values, model)
        seconds += r['duration_ms'] / 1000
        sources[path.name] = sha(path)
        attempts.append(dict(seconds=r['duration_ms']/1000, outcome=r['subtype']))
    assert final['subtype'] == 'success'
    cumulative = final['modelUsage'][model]
    assert cumulative['outputTokens'] == total['output_tokens']
    assert cumulative['cacheReadInputTokens'] == total['cached_input_tokens']
    assert abs(float(dollars) - final['total_cost_usd']) < 1e-7
    return dict({k: total[k] for k in FIELDS}, requests=None, api_equivalent_usd=float(dollars),
                boundary_verified=True, source_sha256=sources, attempts=attempts,
                cli_cost_usd=final['total_cost_usd'], basis='sum of per-attempt usage; checked against final cumulative CLI cost'), seconds


def sum_usage(stages):
    total = {k: sum(s['usage'][k] for s in stages) for k in FIELDS if k != 'requests'}
    requests = [s['usage']['requests'] for s in stages]
    return dict(total, requests=sum(requests) if all(x is not None for x in requests) else None,
                api_equivalent_usd=sum(s['usage']['api_equivalent_usd'] for s in stages), boundary_verified=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rescore', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--archives', required=True, type=Path)
    parser.add_argument('--timing-audit', type=Path)
    args = parser.parse_args()
    m = read(args.rescore / 'MANIFEST.json'); results = read(args.rescore / 'RESULTS.json')
    assert results['complete'] and len(results['jobs']) == 60
    indexed = {(j['lane'], j['kind'], j['milestone']): j for j in results['jobs']}
    timing = {r['lane']: r for r in read(args.timing_audit)['rows']} if args.timing_audit else {}
    all_runs = []
    for lane in m['lanes']:
        directory = Path(lane['run']); state = read(directory / 'status.json'); model = state['model']
        stages = []
        for stage in state['completed']:
            n = stage['milestone']; snapshot = Path(stage['snapshot'])
            expected = next(s['sha256'] for s in lane['stages'] if s['milestone'] == n)
            assert {str(p.relative_to(snapshot)): sha(p) for p in snapshot.rglob('*') if p.is_file()} == expected
            usage, seconds = (claude_usage if model.startswith('claude') else codex_usage)(directory, stage, model)
            job = indexed[lane['label'], 'api', n]; summary = Path(job['revised'])
            assert sha(summary) == job['summary_sha256']
            cases = [compact_result(r) for r in read(summary)['results']]
            for c in cases:
                if c['key'] in DISPUTED: c['interpretation'] = 'disputed-contract-expectation'
            stages.append(dict(release=n, seconds=seconds, reused=bool(stage.get('inherited_from')), usage=usage,
                               code=code_metrics(snapshot), cases=cases, passed=job['counts'].get('passed', 0),
                               total=len(cases), snapshot_files=expected, summary_sha256=sha(summary),
                               session_sha256=__import__('hashlib').sha256(stage['session_id'].encode()).hexdigest()))
        assert len(stages) == 5 and len({s['session_sha256'] for s in stages}) == 5
        final = stages[-1]; job = indexed[lane['label'], 'api', 5]
        history_job = indexed[lane['label'], 'retained', 5]
        histories = [compact_result(r) for r in read(Path(history_job['revised']))]
        assert sha(Path(history_job['revised'])) == history_job['summary_sha256']
        grouped = {}
        for c in final['cases']: grouped.setdefault(c['family'], Counter()).update([c['status']])
        filename = lane['label'] + '-m5-source.tar.gz'
        archive(Path(lane['stages'][-1]['snapshot']), args.archives / filename)
        reused = [s for s in stages if s['reused']]; fresh = [s for s in stages if not s['reused']]
        row = dict(id=lane['label'], model=model, effort=state['effort'], sample=int(lane['label'][-2:]),
                   harness='Claude Code' if model.startswith('claude') else 'Codex CLI', cohort='2026-09-27/28',
                   protocol='fresh-session-per-release', seconds=sum(s['seconds'] for s in stages),
                   reused_seconds=sum(s['seconds'] for s in reused), new_seconds=sum(s['seconds'] for s in fresh),
                   usage=sum_usage(stages), reused_usage=sum_usage(reused), new_usage=sum_usage(fresh),
                   passed=final['passed'], total=123, uncontested_passed=job['uncontested_counts'].get('passed', 0),
                   uncontested_total=121, retained_passed=history_job['counts'].get('passed', 0), retained_total=20,
                   code=final['code'], releases=stages, families=grouped, cases=final['cases'], retained=histories,
                   repeatability=job['repeatability'], previous_counts=job['old_counts'], changes=job['changes'],
                   source_archive=dict(file=filename, sha256=sha(args.archives / filename)),
                   evidence=dict(final_summary_sha256=job['summary_sha256'], retained_summary_sha256=history_job['summary_sha256'],
                                 snapshot_files=final['snapshot_files']))
        if lane['label'] in timing:
            row['timing_audit'] = {k: timing[lane['label']][k] for k in
                ('releases', 'recorded_seconds', 'tool_wait_seconds', 'outside_tool_seconds', 'runner_overhead_seconds')}
        all_runs.append(row)
        print(row['id'], row['passed'], round(row['seconds']/3600, 3), round(row['usage']['api_equivalent_usd'], 2), row['code']['production'], row['code']['test'])
    dataset = dict(version=VERSION, date='2026-09-28', evaluator='R3', protocol='fresh-session-per-release',
        pricing=dict(verified_on='2026-09-28', rates=RATES, long_threshold=272000,
                     long_input_multiplier=2, long_output_multiplier=1.5,
                     claude_cache_write_5m=5, claude_cache_write_1h=8,
                     sources=['https://developers.openai.com/api/docs/pricing',
                              'https://platform.claude.com/docs/en/models/opus-5-5/overview']),
        qualification=dict(regression_tests=44, jobs=60, evaluator_exceptions=0,
                           raw_manifest_sha256=sha(args.rescore/'MANIFEST.json'), results_sha256=sha(args.rescore/'RESULTS.json')),
        disputed_cases=sorted(DISPUTED), scaffold=code_metrics(Path(__file__).resolve().parents[1]/'benchmark/v1/scaffold'), runs=all_runs)
    write(args.output/'results.json', dataset)
    (args.output/'data.js').write_text('window.BILLING_RESULTS = '+json.dumps(dataset)+';\n')


if __name__ == '__main__':
    main()
