#!/usr/bin/env python3
"""Paired fresh/upgrade histories, including actual paid credit and closed reports."""

import argparse
import json
from pathlib import Path
import secrets
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "evaluation/0.5"), str(ROOT / "runtime")]
from billing_eval.history import prepare, resume
from billing_eval import policies, metering_evolution
from billing_eval.suite import Context
from billing_eval.fixtures import Fixture
from billing_eval.checks import Mismatch
from docker_runtime import Runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(ROOT / "evaluation/0.5/billing_eval", args.output / "evaluator-source", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(__file__, args.output / "evaluate_retained.py")
    snapshots = {m: args.run / "snapshots" / f"milestone-{m}" for m in range(1, 6)}
    results = []

    def record(result, trace):
        results.append(result)
        (args.output / (result["key"] + ".json")).write_text(json.dumps(dict(result=result, trace=trace), indent=2)+"\n")
        (args.output / "summary.json").write_text(json.dumps(results, indent=2)+"\n")
        print(json.dumps(result), flush=True)

    # One old VM can seed several isolated tenant histories before the same upgrade.
    plans = [("fresh", 5, range(1, 5))] + [("upgrade", m, [m]) for m in range(1, 5)]
    for kind, boot, shapes in plans:
        runtime = None
        pending = []
        try:
            workspace = args.output / f"workspace-{kind}-{boot}"
            shutil.copytree(snapshots[boot], workspace, symlinks=True)
            secret = secrets.token_urlsafe(32)
            runtime = Runtime.create(workspace, environment=dict(BILLING_AUTH_SECRET=secret))
            runtime.start()
            for shape in shapes:
                for mode in ("draft", "settled"):
                    trace, started = [], time.monotonic()
                    result = dict(key=f"{kind}-m{shape}-to-m5-{mode}", kind=kind, source_milestone=shape, mode=mode,
                                  stage="old_version_setup" if kind == "upgrade" else "fresh_setup")
                    try:
                        f = Fixture(runtime.base_url, secret, result["key"], trace)
                        # Legacy helper shapes: basic, discounted, paid capacity, allocation.
                        state = prepare(f, {1: 1, 2: 3, 3: 5, 4: 4}[shape], mode)
                        pending.append((f, state, result, trace, started))
                    except Exception as exc:
                        result.update(status="failed" if isinstance(exc, Mismatch) else "error", error=str(exc), seconds=round(time.monotonic()-started, 3))
                        record(result, trace)
            if kind == "upgrade":
                for m in range(boot+1, 6):
                    runtime.upgrade(snapshots[m])
            else:
                runtime.restart()
            for f, state, result, trace, started in pending:
                result["stage"] = "cold_continuation"
                try:
                    resume(f, state, result["mode"])
                    result["status"] = "passed"
                except Exception as exc:
                    result.update(status="failed" if isinstance(exc, Mismatch) else "error", error=str(exc))
                result["seconds"] = round(time.monotonic()-started, 3)
                record(result, trace)
        finally:
            if runtime:
                runtime.destroy()

    for kind in ('fresh', 'upgrade'):
        runtime = None
        trace, started = [], time.monotonic()
        result = dict(key=f'{kind}-metering-evolution', kind=kind, source_milestone=1,
                      mode='metering', stage='old_version_setup' if kind == 'upgrade' else 'fresh_setup')
        try:
            workspace = args.output / f'workspace-{kind}-metering'
            shutil.copytree(snapshots[1 if kind == 'upgrade' else 5], workspace, symlinks=True)
            secret = secrets.token_urlsafe(32)
            runtime = Runtime.create(workspace, environment=dict(BILLING_AUTH_SECRET=secret))
            runtime.start()
            f = Fixture(runtime.base_url, secret, result['key'], trace)
            state = metering_evolution.prepare(f)
            if kind == 'upgrade':
                result['stage'] = 'upgrade_to_m2'
                runtime.upgrade(snapshots[2])
            result['stage'] = 'migrate_old_subscription_policy'
            metering_evolution.change_policy(f, state)
            if kind == 'upgrade':
                result['stage'] = 'upgrade_to_m3'
                runtime.upgrade(snapshots[3])
            result['stage'] = 'add_metering_to_old_subscription'
            metering_evolution.introduce_metering(f, state)
            if kind == 'upgrade':
                for milestone in (4, 5):
                    result['stage'] = f'upgrade_to_m{milestone}'
                    runtime.upgrade(snapshots[milestone])
            result['stage'] = 'retained_metering_continuation'
            metering_evolution.verify(f, state)
            result['status'] = 'passed'
        except Exception as exc:
            result.update(status='failed' if isinstance(exc, Mismatch) else 'error', error=f'{type(exc).__name__}: {exc}')
        finally:
            result['seconds'] = round(time.monotonic()-started, 3)
            record(result, trace)
            if runtime:
                runtime.destroy()

    # Same history on fresh final code and on actual M1 storage carried through
    # each delivery. New behavior is applied by M2, not delayed until final code.
    for kind in ('fresh', 'upgrade'):
        runtime = None
        trace, started = [], time.monotonic()
        result = dict(key=f'{kind}-policy-evolution', kind=kind, source_milestone=1,
                      mode='policy', stage='old_version_setup' if kind == 'upgrade' else 'fresh_setup')
        try:
            workspace = args.output / f'workspace-{kind}-policy'
            shutil.copytree(snapshots[1 if kind == 'upgrade' else 5], workspace, symlinks=True)
            secret = secrets.token_urlsafe(32)
            runtime = Runtime.create(workspace, environment=dict(BILLING_AUTH_SECRET=secret))
            runtime.start()
            f = Fixture(runtime.base_url, secret, result['key'], trace)
            state = policies.prepare(f)
            if kind == 'upgrade':
                result['stage'] = 'upgrade_to_m2'
                runtime.upgrade(snapshots[2])
            result['stage'] = 'new_policy_on_old_database'
            state = policies.bind_and_change(f, state)
            policies.rebill_and_cancel(f, state)
            if kind == 'upgrade':
                for milestone in (3, 4, 5):
                    result['stage'] = f'upgrade_to_m{milestone}'
                    runtime.upgrade(snapshots[milestone])
            result['stage'] = 'correct_old_order_across_retained_policy'
            policies.correct_across_policy(f, state)
            result['status'] = 'passed'
        except Exception as exc:
            result.update(status='failed' if isinstance(exc, Mismatch) else 'error',
                          error=f'{type(exc).__name__}: {exc}')
        finally:
            result['seconds'] = round(time.monotonic()-started, 3)
            record(result, trace)
            if runtime:
                runtime.destroy()


if __name__ == "__main__":
    main()
