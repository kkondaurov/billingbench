# Billing Bench v1.1.0

Five cumulative releases of an API-only B2B billing application. Agents choose
their own architecture on a minimal Elixir/Phoenix/PostgreSQL scaffold.
This publication uses fresh conversations per release and the corrected R3 evaluator.

## Contents

- [Candidate manifest](candidate/0.5/manifest.json) and [public API](candidate/0.5/01-api.md).
- [Foundation](candidate/0.5/01-foundation.md), [operations](candidate/0.5/01-operations.md),
  [changes](candidate/0.5/02-changes.md), [metering](candidate/0.5/03-metering.md),
  [sharing](candidate/0.5/03-sharing.md), [agreements](candidate/0.5/04-agreements.md),
  and [historical correction](candidate/0.5/05-history.md).
- [Scaffold](scaffold/), [evaluator selection](evaluation/0.5/billing_eval/selection.py),
  [source hashes](SOURCE_MANIFEST.json), and [full report](../../REPORT.md).

The original `0.5` paths are retained. They identify the five-release definition,
not the evaluator revision. No experimental sixth release or FX scenario is
selected. Requirements and scaffold are unchanged from v1.0.0; the old tag and
[R1 source manifest](SOURCE_MANIFEST_R1.json) preserve that historical publication.

## Protocol

Use `--protocol handoff`: each release starts a new conversation and container,
carrying only the submitted source and available development-database checkpoints.
Agent home directories, previous transcripts, temporary files and live processes
do not carry forward. Same-release interruption recovery resumes that release's
session, never an earlier release's conversation. `continuous` is available only
as an explicitly selected historical comparison protocol.

Deliver only the current and earlier public requests. No subagents, hidden tests,
evaluator feedback or external benchmark solutions are available to candidates.
Freeze each delivery and evaluate disposable copies, never the active workspace.
The reference runtime has 2 CPUs and 4 GiB RAM.

The reported Astra/Sol and Opus trajectories reuse their own unchanged R1, then
implement R2-R5 under the handoff protocol. Luna starts all five releases from
scratch. Opus's imported R1 lacked a development-database checkpoint, so R2
started with a fresh development database. The separately scored retained-history
suites exercise actual database upgrades for every model.

## Commands

Python 3.12+ and Docker are required. Run commands from the repository root.
Candidate execution requires authenticated Codex CLI and spends subscription/API
usage. Listing cases and running unit tests do not launch models.

```sh
python3 -B benchmark/v1/evaluate_v05.py --list

# Five releases with a fresh conversation at every release.
python3 -B benchmark/v1/run.py candidate --protocol handoff \
  --directory .runs/example --model gpt-6-astra --effort low

# Evaluate an immutable submitted copy with R3.
python3 -B benchmark/v1/run.py evaluate --kind api \
  --snapshot .runs/example/snapshots/milestone-5 --through 5 \
  --output .runs/example-r3-api

python3 -B benchmark/v1/run.py evaluate --kind retained \
  --run .runs/example --output .runs/example-r3-retained

python3 -B scripts/verify_v1.py
PYTHONPATH=benchmark/v1/evaluation/0.5 python3 -B -m unittest discover -s tests/v1
```

The packaged candidate command runs Codex, not Claude Code. Opus results include
its submitted sources and score/usage evidence; this is not a portable Claude
runner distribution. The verified handoff runner is packaged with path defaults
adjusted for its published location. Model-free tests cover conversation/runtime
isolation, same-release retries, source integrity and rejected protocol changes.

See [runtime prerequisites](runtime/README.md). Container images and credentials
are not distributed. Do not silently substitute a different environment and call
it an exact reproduction. Never mount this whole repository inside a candidate.

Every evaluation output must be new. The wrapper serializes evaluations under
`.runtime/evaluation.lock`; set `BILLING_EVALUATION_LOCK` to share an existing
controller's lock. Do not duplicate scheduled jobs or evaluate an active workspace.
Retained/performance entrypoints use the original Docker context; only the API
entrypoint supports an alternate `--context`.

## Corrected Tests

R2 turns missing required accounting-response fields into explicit application
failures instead of evaluator exceptions. It does not invent zero values.
R3 also supports valid corrected-transfer representations, validates correction
preview fields and independently checks expected economics in the closed-sale
scenario. Valid daily, aggregate and separate accounting projections are accepted.

Four ID-sensitive scenarios run eight times on fresh tenants and must pass all
eight attempts. Every attempt is retained; the best result is never selected.
This improves detection, but cannot mathematically eliminate accidental passes.
Structural preview validation is broad; independent expected-amount validation
is not exhaustive across every preview scenario.

Qualification included 44 evaluator regression tests, 354 recorded previews,
482 transfer collections and four deliberately corrupted preview controls. All
50 unchanged release snapshots and ten retained-history suites were rescored:
3,860 scenario outcomes, zero evaluator exceptions. Candidate failures remain
failures; no implementation was repaired from evaluator feedback.

## Scoring Boundaries

Final API scores count complete passing scenarios out of 123, not independent
bugs. A prerequisite failure can block several workflows. Histories are ten
fresh/upgrade pairs, scored separately out of 20. Optional application-latency
checks are not included in this rescore or in the correctness score.

Two contract ambiguities remain: offsetting billing documents on zero-net
termination and rejecting versus holding a closed-month correction. Strict /123
scores retain the original expectations. The report also removes the same two
scenarios from every run and shows /121 results. This does not rewrite what the
candidates were asked to build.
