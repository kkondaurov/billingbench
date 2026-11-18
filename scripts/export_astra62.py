#!/usr/bin/env python3
"""Append audited Astra 6.2 low evidence without changing earlier rows or jobs."""
import argparse
import json
from pathlib import Path

from export_sol62 import audit_cohort
from export_v1 import code_metrics, read, write

MODEL, VERSION = 'gpt-6.2-astra', '1.9.0'
RATES, LONG_RATES = [8, .4, 40], [16, .8, 60]


def measure_code(snapshot):
    # The Phoenix runtime invokes the Python domain worker from priv/billing.
    return code_metrics(snapshot, extra_production_prefixes=('priv/billing/',))


def export(base, evidence, freeze, output, archives):
    data, public = read(base/'results.json'), read(base/'EVALUATION_R4.json')
    assert data['version'] == public['version'] == '1.8.0'
    assert len(data['runs']) == 29 and len(public['jobs']) == 198
    quote = read(evidence/'PRICING.json')
    fields = ('uncached_input', 'cached_input', 'output')
    assert quote['model'] == MODEL and quote['tier'] == 'Standard'
    assert quote['long_context_above_input_tokens'] == 272000
    assert [quote['short'][k] for k in fields] == RATES and [quote['long'][k] for k in fields] == LONG_RATES
    runs, receipts = audit_cohort(evidence, freeze, data['runs'][0], archives, model=MODEL,
        effort='low', group='astra62-low', rates=RATES, date='2026-11-17',
        pricing_date=quote['verified_on'], metrics=measure_code)
    runs[1]['architecture'] = 'Python billing worker behind Phoenix'
    data['runs'].extend(runs)
    public['jobs'].extend(receipts)
    jobs = public['jobs']
    assert len({(j['lane'],j['kind'],j['milestone']) for j in jobs}) == len(jobs) == 216
    assert sum(sum(j['counts'].values()) for j in jobs) == 14251
    assert sum(j.get('exceptions',0) for j in jobs) == 13
    data['pricing']['rates'][MODEL] = RATES
    data['pricing']['astra62'] = quote
    data['astra62_protocol'] = dict(independent_starts=3, completion_nudges=0, reused_m1=0,
        effort='low', compatibility='Same effort as GPT-6 Astra low; different CLI/runtime and fresh M1 starts.',
        timing='Three concurrent candidates shared the host. No timing adjustment is applied.',
        code_size='Production LOC includes the Python billing worker in priv/billing for run 2.')
    data.update(version=VERSION, date='2026-11-18')
    data['qualification'].update(jobs=216, scenario_outcomes=14251, snapshot_count=175,
        incremental_jobs=18, main_snapshot_rows=160, unique_api_snapshot_jobs=181, regression_tests=99)
    data['incremental_publication'] = dict(baseline_version='1.8.0', evaluator_changed=False, old_jobs_rerun=False,
        completed_work_verified_from_raw_evidence=True, new_unique_jobs=18, main_comparison_runs=32,
        supplementary_paired_runs=3)
    public['version'] = VERSION
    write(output/'results.json', data)
    write(output/'EVALUATION_R4.json', public)
    (output/'data.js').write_text('window.BILLING_RESULTS = '+json.dumps(data)+';\n')
    print('Verified 15 Astra 6.2 sessions/runtimes, 18 R4 jobs; 216 comparison jobs / 14251 outcomes.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base','evidence','freeze','output','archives'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    export(args.base, args.evidence, args.freeze, args.output, args.archives)
