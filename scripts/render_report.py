#!/usr/bin/env python3
"""Render the text report from the same reviewed data as the dashboard."""
import json
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'site/results.json').read_text())
assert data['version'] == '1.3.0' and data['evaluator'] == 'R4' and data['qualification']['jobs'] == 84
runs = data['runs']
assert len(runs) == 14
names = {'gpt-6-astra': 'Astra', 'gpt-6.1-sol': 'Sol 6.1', 'gpt-6-sol': 'Sol 6',
         'gpt-6-luna': 'Luna 6', 'claude-opus-5-5': 'Opus 5.5'}


def label(r):
    return f"{names[r['model']]} {r['effort']} #{r['sample']}"


def time(seconds):
    minutes = int(seconds / 60 + .5)
    return f'{minutes // 60}h {minutes % 60:02d}m'


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])


sections = ['''# Billing Bench v1.3.0: Results

2 October 2026. Fourteen trajectories, five releases.
[Interactive dashboard](https://kkondaurov.github.io/billingbench/).

## Setup and Result

Each agent builds and evolves an Elixir/Phoenix/PostgreSQL billing backend.
Every release begins a new conversation and runtime. The agent retains its
submitted code, not the previous conversation. No private evaluator feedback or
subagents are provided. Three runs each use GPT-6 Astra low, GPT-6.1 Sol xhigh,
GPT-6 Sol xhigh and GPT-6 Luna xhigh in Codex CLI; two use Claude Opus 5.5 xhigh
in Claude Code.

Sol 6.1 passed 109-111 of 123 final API cases, close to Astra's 105-117, for
$12.58-$15.73 per run versus Astra's $48.49-$61.26. Every Astra run finished
in under four hours; Sol 6.1 took 4h 44m-6h 27m. Every Sol 6.1 run outscored every Sol 6 run
(71-88), with a much narrower observed score range. Opus scored 105 and 107
for $82.21 and $77.55; its second run passed all 20 retained histories.
Luna cost about $3 but delivered much less of the required
behavior. No run passed the entire API suite.

This is not a controlled estimate of model-only improvement: Sol 6.1 used
Codex CLI 0.159.0 and five entirely new releases; the older OpenAI runs used
0.155.1, and Astra/Sol 6 reused their own original R1. This cohort does not
isolate effort effects either. Two Opus runs offer limited evidence of variation.

## Final Results

All figures include five releases. API scores require every assertion in a
scenario to pass; they are not independent bug counts. Histories are ten
fresh/upgrade pairs. LOC means physical lines including comments and blanks:
production is `lib/` plus database migrations; tests are `test/`. Dependencies
and generated builds are excluded. The common scaffold is 123 production lines
and 58 test lines.
''']
sections.append(table(['Run', 'API /123', 'Undisputed /121', 'Histories /20', 'Time', 'API cost', 'Prod LOC', 'Test LOC'], [
    [label(r), r['passed'], r['uncontested_passed'], r['retained_passed'], time(r['seconds']),
     f"${r['usage']['api_equivalent_usd']:.2f}", f"{r['code']['production']:,}", f"{r['code']['test']:,}"] for r in runs]))
sections.append('''## Release Scores

Requirements and denominators grow with each release; a larger pass count alone
does not establish that earlier behavior survived unchanged.
''')
sections.append(table(['Run', 'R1 /34', 'R2 /51', 'R3 /71', 'R4 /87', 'R5 /123'], [
    [label(r), *[s['passed'] for s in r['releases']]] for r in runs]))
sections.append('''## Reused Work, New Work, and Cost

Astra, Sol 6 and Opus #1 reuse their own unchanged first-release submission; R2-R5
were implemented again with fresh conversations. Luna, Sol 6.1 and Opus #2 begin at the
scaffold and implement all five releases, carrying their code forward each time.
Reused work is included in the headline totals, not free
work. The paired Astra/Sol 6 trajectories share an R1 baseline with the old
cohort; these are not fourteen entirely new independent starts.

Time sums active candidate execution, including tools, self-tests and all
same-release retry attempts. It excludes evaluator time, between-release waits
and quota waits between attempts. Opus #1's saved status contained only its last
retry for R1 and R5; these published times instead sum every CLI attempt receipt.
''')
sections.append(table(['Run', 'Reused R1', 'Reused cost', 'New work', 'New cost', 'Total'], [
    [label(r), time(r['reused_seconds']), f"${r['reused_usage']['api_equivalent_usd']:.2f}",
     time(r['new_seconds']), f"${r['new_usage']['api_equivalent_usd']:.2f}", time(r['seconds'])] for r in runs]))
sections.append('''### Tokens and Pricing

Input includes cached reads and cache writes; reasoning is included in output.
OpenAI usage is deduplicated request-level evidence through each delivery,
including compaction. Opus #1 usage sums per-attempt receipts and reconciles to
the cumulative CLI dollar total. Opus #2 deduplicates archived model messages
and discloses its interrupted-request counter difference below. Cumulative
resumed-session totals are not added twice. Opus #1 request counts were not recorded. Opus #2 has 457 deduplicated model messages.

Standard USD per million input / cached-read / output tokens: Astra $10 / $1 /
$50; Sol 6.1 $2 / $0.10 / $10; Sol 6 $2 / $0.20 / $10;
Luna $0.10 / $0.01 / $0.50; Opus $4 / $0.20 / $20.
Opus cache writes cost $5 (five-minute) or $8 (one-hour); observed writes use the
one-hour rate. Opus rates were reverified 2 October 2026. OpenAI long-context pricing applies per request above 272K input
tokens, at 2x input and 1.5x output; no included request crossed that threshold.
These are API-equivalent usage estimates, not subscription charges or evaluator
costs. Rates verified 30 September 2026 against
[OpenAI pricing](https://developers.openai.com/api/docs/pricing) and
[Opus pricing](https://platform.claude.com/docs/en/models/opus-5-5/overview).
''')
sections.append(table(['Run', 'Input tokens', 'Cached read', 'Cache write', 'Output', 'Reasoning', 'Requests', 'API cost'], [
    [label(r), *[f"{r['usage'][k]:,}" for k in ('input_tokens', 'cached_input_tokens')],
     f"{r['usage']['cache_write_5m_tokens'] + r['usage']['cache_write_1h_tokens']:,}",
     *[f"{r['usage'][k]:,}" for k in ('output_tokens', 'reasoning_output_tokens')],
     r['usage']['requests'] if r['usage']['requests'] is not None else 'Not recorded',
     f"${r['usage']['api_equivalent_usd']:.2f}"] for r in runs]))
sections.append('''## Code and Downloads

Final source archives contain application sources and configuration only, not
sessions, credentials, build outputs or the private evaluator. Every file has a
SHA-256 in [results.json](site/results.json), alongside all 70 snapshot manifests.
''')
sections.append(table(['Run', 'Production files', 'Test files', 'Largest production file', 'Lines', 'Source'], [
    [label(r), r['code']['production_files'], sum(f['category'] == 'test' for f in r['code']['files']),
     '`' + r['code']['largest']['path'] + '`', r['code']['largest']['lines'],
     f"[Download](https://github.com/kkondaurov/billingbench/releases/download/v{data['version']}/{r['source_archive']['file']})"] for r in runs]))
sections.append('''## Independent Opus Replicate

Opus #2 starts from the scaffold, including a new R1. The first run reused its
own original R1. Actual candidate init events show Claude Code 2.1.283 for #1
and 2.1.285 for #2. These protocol and CLI differences are not isolated.

The second run scored 30/34, 47/51, 64/71, 79/87 and 105/123 across releases,
and 20/20 retained histories. All six evaluations completed under unchanged
qualified R4 sources, without exceptions. The previous 78 jobs were not rerun.

All nine invocation attempts contribute to 3h 32m of implementation time.
Quota waits add 42h 45m; first launch to final delivery took 47h 33m.
Quota interruptions resumed the same release session and runtime.
Each new release used a fresh conversation and runtime.

Usage is deduplicated by archived model-message identity; repeated content
blocks and cumulative resumed-session counters are not added twice.
The observed archive estimate is $82.21, compared with $82.08 in cumulative
CLI counters. One interrupted M5 request accounts for $0.12 of observed input,
cache and initial output usage; its final interrupted output is unknown.
The actual run used Claude Pro with extra usage disabled, not paid API billing.
''')
sections.append('''## What the Evaluator Repairs Changed

All 65 unchanged release snapshots and thirteen retained-history suites were
rescored using identical frozen R4 sources. Across 5,018 scenario outcomes,
there were zero evaluator exceptions. All 5,681 prior evidence-file hashes and
65 submitted snapshot trees were reverified. The applications were not changed.

The audit found two sources of false negatives. Covered billing scopes may link
old issued documents; the fixture incorrectly counted those links as newly
issued invoices or credits. It now distinguishes new documents by before/after
IDs and checks that old face facts stay unchanged. A preview's aggregate
accounting projection may have a null customer while its billing row identifies
the correct debtor; the old check incorrectly required a debtor on every row.

Two false-positive controls were strengthened: monetary document fields must
be integers rather than booleans/floats that compare equal in Python, and
billing/recognition preview amounts must agree with independently expected
economics even if their internal delta and address projections are consistent.
New controls reject hidden new documents, deleted or rewritten old documents,
duplicate IDs, wrong debtors and wrong economic targets without rejecting
valid settlement-balance changes or response extensions.

The frozen suite passed 73 regression tests. All 1,599 final-case recordings
were considered for replay: 1,101 passed, 464 still failed, 21 needed live
continuation beyond their old failure, and 13 concurrency cases required live
execution. Every previously passing replayable case still passed. All 78 jobs
then ran live, including restart/concurrency and retained-history tests.
This is evidence-backed qualification, not proof of exhaustive correctness.

Four ID-sensitive scenarios run eight times on fresh tenants and require eight
passes. Opus #1's two customer-boundary checks passed only 4/8 and 3/8 trials;
failures shifted adjustments by one cent. Sol 6 #2's successor-agreement scenario
passed only 2/8 trials in this rescore; failures create an extra $400 invoice
despite no new sale. Its prior 6/8 record remains preserved. Repetition detects
these unstable results but cannot prove that no other nondeterminism remains.

On final API snapshots, Sol 6.1 #3 rises from 97 to 110: twelve covered-document
false failures and one nullable-projection false failure are corrected.
Luna #1 rises from 42 to 43 for the covered-document fix. The other eleven
final API totals are unchanged. Retained histories improve from 6 to 16 of 20
for Sol 6.1 #3 and from 4 to 7 for Luna #1, also from the covered-document fix.
No previously passing scenario loses its pass. Per-release and retained-history
changes, alongside all repetition statuses, are included in the download.

Only the following trajectories have changed pass totals (before to after):
''')
sections.append(table(['Run', 'R1', 'R2', 'R3', 'R4', 'R5', 'Histories'], [
    [label(r), *[f"{s['previous_counts'].get('passed', 0)} to {s['passed']}" for s in r['releases']],
     f"{r['retained_previous_counts'].get('passed', 0)} to {r['retained_passed']}"]
    for r in runs if any(s['changes'] for s in r['releases']) or r['retained_changes']]))
sections.append('''

## Disputed Expectations

Two checks remain disputed: whether a zero-net termination may create offsetting
billing documents, and whether a closed-month correction may be rejected instead
of entering a held-operation workflow. Strict /123 scores retain the original
test expectations. The /121 comparison excludes both scenarios uniformly for
every run, rather than selectively granting credit. Both Astra and Sol 6.1
remain ahead of Sol 6 under either treatment. Failing a scenario does not always mean a wrong total;
it can also mean a missing record or unusable promised workflow.

## Timing Limitations

Candidates had 2 CPUs and 4 GiB RAM each, but several jobs overlapped on a shared
host. The following observed Codex intervals count the union of tool dispatch to
tool-result time, avoiding double-counting concurrent calls. Time outside those
intervals includes model responses, network/client delays and other overhead;
it is not a direct measurement of provider thinking time. Tool waiting includes
ordinary tool work, not just contention. No continuous throttling measurement
supports a quantified contention penalty. These are build times, not application
latency results. Optional speed tests were not rerun for this publication.

The interval breakdown below covers the nine older Codex runs. Sol 6.1's newer
CLI logs contain tool-result timestamps preceding their matching calls, so no
interval breakdown is reported for those three runs. Their host-runner totals
are reported without a guessed adjustment. Usage-record order and timestamps
agree at all fifteen delivery boundaries, so this does not alter token costs.
''')
sections.append(table(['Run', 'Releases observed', 'Tool-call intervals', 'Outside tool calls'], [
    [label(r), ', '.join(map(str, r['timing_audit']['releases'])),
     f"{100 * r['timing_audit']['tool_wait_seconds'] / r['timing_audit']['recorded_seconds']:.1f}%",
     f"{100 * r['timing_audit']['outside_tool_seconds'] / r['timing_audit']['recorded_seconds']:.1f}%"]
    for r in runs if 'timing_audit' in r]))
sections.append('''## Protocol and Provenance Limits

Development databases carry forward where a checkpoint exists. Opus #1's imported
R1 had none, so its R2 began with a fresh development database. This differs from
the restored Codex development databases. Independent retained-history tests
exercise real upgrades for every model. Luna #2 changed its candidate-local
schema file after delivery of the verified public packet; frozen requirements
and private evaluator sources remained unchanged.

The CLI 0.155.1 setup attempts for Sol 6.1 were rejected before any model work;
the authorized upgrade to 0.159.0 then ran three fresh trajectories. Failed
setup attempts are preserved separately and excluded from implementation time.
The CLI change is not isolated from the model comparison. The same public
requirements, scaffold and resource limits were used throughout.

The [old continuous-session cohort](https://kkondaurov.github.io/billingbench/archive/v1.0.0/)
is preserved separately. Its published scores used R1, while this cohort uses R4,
so a raw before/after comparison changes both session protocol and evaluator.
The new results are not a clean causal estimate of the effect of resetting a
conversation. The old tag and eight source archives remain available.

The download includes per-case outcomes, per-release code/usage/time, hashed
session identities (five distinct sessions per trajectory), snapshot hashes,
summary hashes and source-archive hashes. Raw conversations, auth state and local
filesystem paths are not published. The [benchmark package](benchmark/v1/README.md)
documents reproduction commands and the original nonportable runtime dependency.
Accounting rules are policies of this synthetic application, not a claim of
accounting-standard compliance.
''')
(ROOT / 'REPORT.md').write_text('\n\n'.join(sections).rstrip() + '\n')

groups = []
full_names = {'gpt-6-astra': 'GPT-6 Astra', 'gpt-6.1-sol': 'GPT-6.1 Sol',
              'claude-opus-5-5': 'Claude Opus 5.5', 'gpt-6-sol': 'GPT-6 Sol', 'gpt-6-luna': 'GPT-6 Luna'}
for model, name in full_names.items():
    group = [r for r in runs if r['model'] == model]
    assert group
    groups.append([f"{name} {group[0]['effort']}", len(group),
                   f"{mean(r['passed'] for r in group):.1f}",
                   f"{mean(r['retained_passed'] for r in group):.1f}",
                   time(mean(r['seconds'] for r in group)),
                   f"${mean(r['usage']['api_equivalent_usd'] for r in group):.2f}",
                   f"{median(r['code']['production'] for r in group):,.0f}",
                   f"{median(r['code']['test'] for r in group):,.0f}"])
readme = '''# Billing Bench

Can a coding agent build a B2B billing backend, then evolve it through five
releases without losing the financial history?

**[Results dashboard](https://kkondaurov.github.io/billingbench/)**

Fourteen completed trajectories: three each of GPT-6 Astra low, GPT-6.1 Sol
xhigh, GPT-6 Sol xhigh and GPT-6 Luna xhigh, plus two Claude Opus 5.5 xhigh.
Each release starts a fresh conversation. OpenAI models use Codex CLI; Opus
uses Claude Code.

## Results

'''
readme += table(['Model / effort', 'Runs', 'Mean API /123', 'Mean histories /20',
                 'Mean time', 'Mean API cost', 'Median prod LOC', 'Median test LOC'], groups)
readme += '''

Sol 6.1 approaches Astra's final API correctness at a much lower API-equivalent
cost; Astra finishes faster. Sol 6.1 passes 109-111 cases versus Astra's 105-117
and Sol 6's 71-88. Opus's two results are within Astra's range, at a higher
cost. Luna is much cheaper but substantially less correct. No run passes the
entire API suite, and this cohort does not test effort settings within a model.

Time and cost include all five releases, including reused R1 for Astra, Sol 6
and Opus #1. Luna, Sol 6.1 and Opus #2 implement all five releases in new trajectories,
carrying their code forward between releases. The dashboard
separates reused and new work. Sol 6.1 uses CLI 0.159.0 versus 0.155.1 for the
older OpenAI runs, so this is not an isolated model-only comparison.
Costs are standard API equivalents, not subscription bills. LOC counts physical
lines including comments/blanks. Shared-host build time is not a controlled
latency benchmark. Two disputed API checks are also reported separately.

## Publication v1.3.0

- [Full report, per-run metrics and limitations](REPORT.md)
- [Benchmark definition and commands](benchmark/v1/README.md)
- [Candidate packets](benchmark/v1/candidate/0.5/manifest.json)
- [Evaluator audit and controls](benchmark/v1/AUDIT_R4.md)
- [Machine-readable results, tokens, hashes and per-case outcomes](site/results.json)
- [Release and final application sources](https://github.com/kkondaurov/billingbench/releases/tag/v1.3.0)
- [Previous thirteen-run R4 report](https://kkondaurov.github.io/billingbench/archive/v1.2.0/)
- [Previous ten-run report](https://kkondaurov.github.io/billingbench/archive/v1.1.0/)
- [Archived continuous-session report](https://kkondaurov.github.io/billingbench/archive/v1.0.0/)

All 65 release snapshots and thirteen retained-history suites were rescored
with one frozen R4 evaluator. No candidate implementation changed. The
five-release requirements are unchanged; historical tags and cohorts remain
preserved separately. Opus #2 adds six completed evaluations under the same R4
sources, with zero exceptions; the original 78 jobs were not rerun.
Actual Claude Code versions were 2.1.283 (#1) and 2.1.285 (#2). The second run
starts fresh at R1 and passes 105/123 API cases and 20/20 histories. Its time
includes all nine invocation attempts and excludes 42h 45m of quota waits.
Its archive estimate of $82.21 includes $0.12 in observed interrupted-request
usage absent from the $82.08 CLI counters; final interrupted output is unknown.

## Verify

```sh
python3 -B scripts/verify_v1.py
PYTHONPATH=benchmark/v1/evaluation/0.5 python3 -B -m unittest discover -s tests/v1
node scripts/check_site.cjs # requires Playwright and Chromium
```

The static report is `site/index.html` and opens directly from disk. GitHub Pages
deploys the same files. Export scripts read preserved local evidence and publish
sanitized application sources, not raw sessions, credentials or workspaces.

Original container image IDs and prerequisites are documented in
[runtime/README.md](benchmark/v1/runtime/README.md); images are not distributed.
Earlier `docs/0.1/` design notes are historical, not the v1 contract. This is an
independent synthetic benchmark, not a claim of accounting-standard compliance.
'''
(ROOT / 'README.md').write_text(readme)
print('Rendered REPORT.md and README.md from site/results.json')
