"""Case registration and failure-stage reporting, separate from score aggregation."""

import json
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from .checks import Mismatch
from .fixtures import Fixture


@dataclass(frozen=True)
class Case:
    key: str
    milestone: int
    family: str
    criteria: tuple
    distinguishes: str
    run: object


CASES = {}


def case(key, milestone, family, criteria, distinguishes):
    def decorate(fn):
        if key in CASES:
            raise ValueError(f"duplicate case {key}")
        CASES[key] = Case(key, milestone, family, tuple(criteria.split()), distinguishes, fn)
        return fn
    return decorate


class Context:
    def __init__(self, fixture, runtime=None, receiver=None):
        self.f = fixture
        self.stage = "setup"
        self.observations = []
        self.runtime, self.receiver = runtime, receiver

    def checkpoint(self, label):
        self.stage = label
        self.observations.append({"stage": label, "request_count": len(self.f.api.trace)})


def execute(case, base_url, secret, directory, runtime=None, receiver=None):
    trace, context = [], None
    started = time.monotonic()
    result = dict(key=case.key, milestone=case.milestone, family=case.family,
                  criteria=case.criteria, distinguishes=case.distinguishes)
    try:
        fixture = Fixture(base_url, secret, case.key, trace)
        context = Context(fixture, runtime, receiver)
        case.run(context)
        result.update(status="passed", stage=context.stage)
    except Mismatch as exc:
        result.update(status="failed", stage=context.stage if context else "tenant_setup", error=str(exc))
    except Exception as exc:
        result.update(status="error", stage=context.stage if context else "tenant_setup",
                      error=f"{type(exc).__name__}: {exc}", traceback=traceback.format_exc())
    result.update(seconds=round(time.monotonic() - started, 3), requests=len(trace),
                  checkpoints=context.observations if context else [])
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{case.key}.json").write_text(json.dumps(dict(result=result, trace=trace), indent=2) + "\n")
    return result


def aggregate(results):
    groups = {}
    for r in results:
        groups.setdefault(r["family"], []).append(r)
    return {family: {"passed": all(r["status"] == "passed" for r in rows),
                     "cases_passed": sum(r["status"] == "passed" for r in rows),
                     "cases": len(rows), "case_ids": [r["key"] for r in rows]}
            for family, rows in sorted(groups.items())}
