#!/usr/bin/env python3
"""Small serial scale experiment; preparation, correctness and latency stay distinct."""
import argparse
import copy
import json
from pathlib import Path
import secrets
import shutil
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'evaluation/0.5'), str(ROOT / 'runtime')]
from billing_eval.fixtures import Fixture
from billing_eval.client import identifier
from billing_eval.checks import equal, require, document_totals
from billing_eval.m6 import correction
from docker_runtime import Runtime

SIZES = (1, 16, 64, 128)
LIMIT = 5.0


def check_preview(value, buyer):
    equal(value['issues'], [], 'complete focal preview was held')
    documents = value['result']['documents']
    document_totals(documents, [('invoice', 10000)], 'focal February preview')
    require(all(d['customer_id'] == buyer['id'] and d['currency'] == 'USD' for d in documents),
            'preview contains unrelated service')


def run(snapshot, output, through):
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(snapshot, output / 'workspace', symlinks=True)
    runtime, trace = None, []
    state = dict(version='0.5', milestone=through, status='starting', setup=[], measurements=[],
                 sizes=SIZES, latency_limit_seconds=LIMIT, started_at=time.time())

    def save():
        state['updated_at'] = time.time()
        (output / 'summary.json').write_text(json.dumps(state, indent=2)+'\n')

    def sample(label, fn, repeat=3, threshold=LIMIT):
        samples = []
        row = dict(operation=label, customers=state['prepared_customers'], functional_status='passed', samples=samples)
        state['measurements'].append(row)
        for _ in range(repeat):
            start = time.monotonic()
            try:
                fn()
                samples.append(round(time.monotonic()-start, 4))
            except Exception as exc:
                row.update(functional_status='unreached' if isinstance(exc, TimeoutError) else 'failed',
                           error=f'{type(exc).__name__}: {exc}', failed_request_seconds=round(time.monotonic()-start, 4))
                row['latency_status'] = 'timeout' if isinstance(exc, TimeoutError) else 'not_scored'
                save()
                raise
        row['median_seconds'] = statistics.median(samples)
        row['latency_status'] = 'reported_only' if threshold is None else ('passed' if row['median_seconds'] <= threshold else 'failed')
        save()
        print(json.dumps(row), flush=True)

    try:
        secret = secrets.token_hex(24)
        runtime = Runtime.create(output / 'workspace', environment={'BILLING_AUTH_SECRET': secret})
        runtime.save(output / 'runtime.json')
        runtime.start()
        f = Fixture(runtime.base_url, secret, 'scale-v03', trace)
        # Ten seconds allows a measured miss of the five-second target without
        # letting one pathological request block the remainder of evaluation.
        f.api.timeout = 10
        health_start = time.monotonic()
        f.api.request('GET', '/health', status=200)
        state['health_seconds'] = time.monotonic()-health_start
        f.chart()
        buyer = f.customer('focal')
        sub, catalog, _ = f.subscription(buyer, end='2029-01-01')
        f.api.at('2028-01-31')
        _, docs = f.bill(customers=[buyer['id']])
        document_totals(docs, [('invoice', 10000)])
        baseline = copy.deepcopy(f.units(sub, '2028-01-31'))
        require(baseline, 'focal revenue-unit read returned no service')
        require(any(r.get('net_minor') == 10000 for r in baseline), 'focal read must contain priced service')
        initial_statement = f.statement(buyer)
        receipts = 0
        state.update(status='preparing', prepared_customers=1)
        for size in SIZES:
            state['status'] = 'preparing'
            start, base = time.monotonic(), state['prepared_customers']
            setup = dict(from_customers=base, target_customers=size, status='running')
            state['setup'].append(setup)
            while state['prepared_customers'] < size:
                i = state['prepared_customers']
                t = time.monotonic()
                customer = f.customer(f'background-{i:04d}')
                child = f.create('/subscriptions', customer_id=customer['id'], currency='USD',
                    starts_on='2028-01-01', ends_before='2029-01-01', renewal_months=None,
                    plans=[dict(catalog_id=catalog['id'], plan_key='standard', overrides={})], attrs={})
                f.api.action(f"/subscriptions/{identifier(child['id'])}/accept")
                f.evidence(child, 'base', 'activation', '2028-01-01')
                state['prepared_customers'] += 1
                setup.update(seconds=round(time.monotonic()-start, 3), last_customer_seconds=round(time.monotonic()-t, 3))
                n = state['prepared_customers']-base
                setup['estimated_remaining_seconds'] = round(setup['seconds']/n*(size-state['prepared_customers']), 1)
                save()
                if state['prepared_customers'] % 16 == 0:
                    print(json.dumps(dict(stage='preparation', customers=state['prepared_customers'], **setup)), flush=True)
            setup.update(status='completed', seconds=round(time.monotonic()-start, 3))
            f.api.at('2028-01-31')
            state['status'] = 'measuring'

            def statement():
                expected = {k: initial_statement[k] for k in ('ar_minor', 'available_backed_minor', 'available_restricted_minor',
                                                             'cash_received_minor', 'cash_refunded_minor')}
                expected['available_backed_minor'] += receipts
                expected['cash_received_minor'] += receipts
                actual = f.statement(buyer)
                equal({k: actual[k] for k in expected}, expected, 'unrelated background cannot change focal funds')

            def receipt():
                nonlocal receipts
                f.receipt(buyer, 1)
                receipts += 1

            def units():
                current = f.units(sub, '2028-01-31')
                keep = ('scope_key', 'window', 'quantity', 'gross_minor', 'net_minor', 'billed_minor', 'earned_minor')
                normalize = lambda rows: sorted((json.dumps({k: r.get(k) for k in keep}, sort_keys=True) for r in rows))
                equal(normalize(current), normalize(baseline), 'background changed focal service')

            def preview():
                value = f.api.preview('/bill-runs/preview', dict(key='focal-preview',
                    customer_ids=[buyer['id']], target_date='2028-02-01', invoice_date='2028-02-01',
                    posting_date='2028-01-31'))
                check_preview(value, buyer)

            repeat = 3 if size in (16, SIZES[-1]) else 1
            sample('statement', statement, repeat)
            sample('receipt', receipt, repeat)
            sample('preview', preview, repeat)
            # The final read also checks invariance. Don't repeatedly trigger a
            # known quadratic endpoint while growing the preparation dataset.
            if size in (1, 16, SIZES[-1]):
                sample('revenue_units', units, repeat)
            statement()
        if through >= 5:
            state['status'] = 'correcting_focal_history'
            original = f.api.get(f"/documents/{identifier(docs[0]['id'])}")
            ids = {d['id'] for d in f.api.all('/documents')}
            sample('historical_correction', lambda: correction(f, {}, dict(kind='recorded_term',
                resource=dict(kind='subscription', id=sub['id']), path=['charges', 'base', 'price'],
                replacement='90'), date='2028-01-31'), 1, threshold=None)
            issued = [d for d in f.api.all('/documents') if d['id'] not in ids]
            document_totals(issued, [('credit', 1000)])
            equal(f.api.get(f"/documents/{identifier(docs[0]['id'])}")['total_minor'], original['total_minor'], 'old invoice is immutable')
            current = f.units(sub, '2028-01-31')
            require(any(r.get('net_minor') == 9000 for r in current), 'correction did not invalidate focal calculation')
        state['status'] = 'completed'
    except Exception as exc:
        state.update(status='stopped', stopped_at_stage=state['status'], error=f'{type(exc).__name__}: {exc}',
                     unreached='Remaining operations and sizes were not evaluated; not additional functional failures.')
    finally:
        state['growth'] = {}
        for operation in ('statement', 'receipt', 'preview', 'revenue_units'):
            rows = {r['customers']: r for r in state['measurements']
                    if r['operation'] == operation and 'median_seconds' in r}
            if 128 in rows:
                rows[128]['quiet_host_recheck_recommended'] = 4 <= rows[128]['median_seconds'] <= 6.25
            if 16 in rows and 128 in rows:
                state['growth'][operation] = dict(
                    ratio_128_to_16=round(rows[128]['median_seconds']/max(rows[16]['median_seconds'], 0.0001), 3), report_only=True)
        state['seconds'] = round(time.time()-state['started_at'], 3)
        save()
        (output / 'trace.json').write_text(json.dumps(trace, indent=2)+'\n')
        if runtime:
            runtime.destroy()
    return state


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--through', type=int, choices=range(1, 6), default=5)
    a = p.parse_args()
    print(json.dumps(run(a.snapshot, a.output, a.through), indent=2))
