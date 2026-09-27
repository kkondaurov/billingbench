# Billing Bench v1.0.0

Five cumulative releases of an API-only B2B billing application. Agents choose
their own domain architecture on a minimal Elixir/Phoenix/PostgreSQL scaffold.
They retain their code and data as billing requirements evolve.

## Contents

- [Candidate manifest](candidate/0.5/manifest.json): staged delivery and agent instructions.
- [Foundation](candidate/0.5/01-foundation.md), [public API](candidate/0.5/01-api.md),
  and [operations](candidate/0.5/01-operations.md).
- [Changes](candidate/0.5/02-changes.md).
- [Metering](candidate/0.5/03-metering.md) and [sharing](candidate/0.5/03-sharing.md).
- [Agreements](candidate/0.5/04-agreements.md).
- [Historical correction](candidate/0.5/05-history.md).
- [Scaffold](scaffold/) and [evaluator selection](evaluation/0.5/billing_eval/selection.py).
- [Source hashes](SOURCE_MANIFEST.json).

Version 1 is the published release of the settled five-release 0.5 definition
and its qualified R1 evaluator. The `0.5` paths and output version strings are
retained deliberately: the 71 files in `SOURCE_MANIFEST.json` are byte-identical
to the evaluated freeze. Historical module names do not define release order;
`selection.py` selects exactly 123 cases through release 5. No FX or experimental
sixth release is selected. Packaging introduces no new business requirements.

## Protocol

Start each candidate from the common scaffold, with no business implementation.
Deliver only the current and earlier requests. Preserve the candidate's own CLI
session and workspace between releases. No subagents, hidden tests, evaluation
feedback or external benchmark solutions are available to the candidate.
Freeze a source snapshot at every delivery. Evaluate copies, never the candidate
workspace. The reference container has 2 CPUs and 4 GiB RAM.

## Commands

Python 3.12+ and Docker are required. Commands are run from the repository root.
Candidate execution additionally requires an authenticated Codex CLI environment.
It launches paid/subscription model work; listing cases and verification do not.

```sh
# Read-only: list the 123 selected scenarios.
python3 -B benchmark/v1/evaluate_v05.py --list

# Implementation: five staged deliveries in the candidate's own session.
python3 -B benchmark/v1/run.py candidate \
  --directory .runs/example --model gpt-6-astra --effort low

# Isolated evaluation of a delivered snapshot.
python3 -B benchmark/v1/run.py evaluate --kind api \
  --snapshot .runs/example/snapshots/milestone-5 --through 5 \
  --output .runs/example-api

# Twenty paired fresh/upgrade histories using all five snapshots.
python3 -B benchmark/v1/run.py evaluate --kind retained \
  --run .runs/example --output .runs/example-retained

# Separate operational measurement, not part of the API score.
python3 -B benchmark/v1/run.py evaluate --kind performance \
  --snapshot .runs/example/snapshots/milestone-5 --through 5 \
  --output .runs/example-performance
```

The runtime adapter retains the original local Docker configuration. See
[runtime prerequisites](runtime/README.md). This release publishes the complete
packet, scaffold and evaluator, not a portable distribution of the original
container images. Do not silently substitute a different environment and label
it an exact reproduction. Never mount the whole benchmark repository into a
candidate container; the evaluator must remain outside its workspace.

Every evaluation output must be new. The wrapper serializes evaluation using
`.runtime/evaluation.lock`; set `BILLING_EVALUATION_LOCK` to share a lock with an
existing controller. Do not launch it against an active candidate or duplicate
an already scheduled evaluation.

## Scoring and Known Boundaries

API: 123 complete scenario outcomes on the final application. A prerequisite
failure remains a failed workflow, but is not a separate demonstrated defect in
every downstream mechanism. Retained histories: ten fresh/upgrade pairs, scored
separately. Performance: four published latency-gated operations plus unscored
diagnostic measurements.

Two interpretation issues remain visible in the result data: offsetting
termination documents and the meaning of source-item lists on transfer
correction rows. Strict scores retain these outcomes with explicit annotations.
Clarifying a future contract must not rewrite what existing candidates saw.

The API R1 repairs were qualified by 24 unit-test methods and replay controls
for five corrupted accounting outputs. All eight final snapshots were rerun;
the retained-history numbers are from their separately completed history runs.
The report and export scripts keep these evaluation scopes distinct.
