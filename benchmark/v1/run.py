#!/usr/bin/env python3
"""Billing Bench v1: staged candidates and isolated evaluation."""
import argparse
import fcntl
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'runtime')]
import network_support
network_support.enable()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    candidate = sub.add_parser('candidate')
    candidate.add_argument('--directory', type=Path, required=True)
    candidate.add_argument('--model', required=True)
    candidate.add_argument('--effort', choices=('low', 'xhigh'), required=True)
    candidate.add_argument('--through', type=int, choices=range(1, 6), default=5)
    candidate.add_argument('--resume', action='store_true')
    candidate.add_argument('--image', default='sha256:d916afedec259eb95d980bdf210d77e0d5ea622fac46a9e189081d9ddd068cdc')
    candidate.add_argument('--context', default='colima-sweatbench-qemu')
    candidate.set_defaults(version='0.5', harness='codex')
    evaluate = sub.add_parser('evaluate')
    evaluate.add_argument('--kind', choices=('api', 'retained', 'performance'), required=True)
    evaluate.add_argument('--snapshot', type=Path)
    evaluate.add_argument('--run', type=Path)
    evaluate.add_argument('--through', type=int, choices=range(1, 6), default=5)
    evaluate.add_argument('--output', type=Path, required=True)
    evaluate.add_argument('--context', default='colima-sweatbench-qemu')
    args = parser.parse_args()
    if args.action == 'candidate':
        import run_candidate
        return run_candidate.run(args)
    if args.output.exists():
        parser.error('evaluation requires a new output directory; preserve previous results')
    if args.kind == 'retained':
        if not args.run:
            parser.error('retained evaluation requires --run')
        command, script = ['--run', str(args.run)], 'evaluate_retained_v05.py'
    else:
        if not args.snapshot:
            parser.error('API/performance evaluation requires --snapshot')
        command = ['--snapshot', str(args.snapshot), '--through', str(args.through)]
        script = 'evaluate_v05.py' if args.kind == 'api' else 'evaluate_performance_v05.py'
    lock_path = Path(os.environ.get('BILLING_EVALUATION_LOCK', ROOT.parent.parent / '.runtime/evaluation.lock'))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        sys.argv = [str(ROOT / script), *command, '--output', str(args.output), '--context', args.context]
        runpy.run_path(str(ROOT / script), run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
