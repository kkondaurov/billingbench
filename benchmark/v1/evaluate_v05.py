#!/usr/bin/env python3
"""Run deterministic API cases on a frozen candidate snapshot; no model feedback."""

import argparse
from collections import Counter
import json
from pathlib import Path
import secrets
import shutil
import sys

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "evaluation/0.5"), str(ROOT / "runtime")]
from billing_eval.selection import SELECTED as CASES
from billing_eval.suite import execute, aggregate
from docker_runtime import Runtime, CONTEXTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--through", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--context", choices=CONTEXTS, default=CONTEXTS[0])
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--base-url")
    parser.add_argument("--secret", default="billingbench-local-development-only")
    args = parser.parse_args()
    selected = [c for c in CASES.values() if c.milestone <= args.through and (not args.case or c.key in args.case)]
    unknown = set(args.case) - CASES.keys()
    if unknown:
        parser.error(f"unknown cases: {sorted(unknown)}")
    if args.list:
        print(json.dumps([dict(key=c.key, milestone=c.milestone, family=c.family, criteria=c.criteria,
                               distinguishes=c.distinguishes) for c in selected], indent=2))
        return
    if not args.output or not (args.snapshot or args.base_url):
        parser.error("execution requires --output and --snapshot (or an existing --base-url)")
    runtime = None
    secret, base_url = args.secret, args.base_url
    try:
        args.output.mkdir(parents=True, exist_ok=False)
        shutil.copytree(ROOT / "evaluation/0.5/billing_eval", args.output / "evaluator-source/billing_eval",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(Path(__file__), args.output / "evaluator-source/evaluate.py")
        if args.snapshot:
            secret = secrets.token_urlsafe(32)
            workspace = args.output / "workspace"
            shutil.copytree(args.snapshot, workspace, symlinks=True)
            runtime = Runtime.create(workspace, context=args.context,
                                     environment=dict(BILLING_AUTH_SECRET=secret))
            runtime.save(args.output / "runtime.json")
            runtime.start()
            base_url = runtime.base_url
        results = []
        for case in selected:
            print(f"START {case.key}", flush=True)
            result = execute(case, base_url, secret, args.output / "cases", runtime)
            results.append(result)
            print(f"{result['status'].upper()} {case.key} ({result['stage']}, {result['seconds']}s)", flush=True)
            summary = dict(version="0.5", milestone=args.through, snapshot=str(args.snapshot) if args.snapshot else None,
                           status="running", counts=dict(Counter(r["status"] for r in results)),
                           families=aggregate(results), results=results)
            (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        summary["status"] = "completed"
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary["counts"]), flush=True)
    finally:
        if runtime:
            runtime.destroy()


if __name__ == "__main__":
    main()
