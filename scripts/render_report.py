#!/usr/bin/env python3
"""Render the text report from the same reviewed data as the dashboard."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'site/results.json').read_text())
runs = data['runs']
names = {'gpt-6-astra': 'Astra', 'gpt-6-sol': 'Sol 6', 'gpt-6-luna': 'Luna 6', 'claude-opus-5-5': 'Opus 5.5'}


def label(r):
    return f"{names[r['model']]} {r['effort']} #{r['sample']}"


def time(seconds):
    minutes = int(seconds / 60 + .5)
    return f'{minutes // 60}h {minutes % 60:02d}m'


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])


sections = ['''# Billing Bench v1.1.0: Fresh-Session Results

28 September 2026. Ten trajectories, five releases, one corrected R3 evaluator.
[Interactive dashboard](https://kkondaurov.github.io/billingbench/).

## Setup and Result

Each agent builds and evolves an Elixir/Phoenix/PostgreSQL billing backend.
Every release begins a new conversation and runtime. The agent retains its
submitted code, not the previous conversation. No private evaluator feedback or
subagents are provided. Three runs each use GPT-6 Astra low, GPT-6 Sol xhigh and
GPT-6 Luna xhigh in Codex CLI; one uses Claude Opus 5.5 xhigh in Claude Code.

Every Astra run outscored and finished faster than every Sol run. Opus landed
within Astra's score range, at a higher API-equivalent cost. Luna cost about $3
per run but delivered much less of the required behavior. No run passed the
entire API suite. This cohort does not isolate effort effects or model effects
from harness differences. One Opus run is not an estimate of its variation.

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

Astra, Sol and Opus reuse their own unchanged first-release submission; R2-R5
were implemented again with fresh conversations. Luna starts all five releases
from scratch. Reused work is included in the headline totals, not free work.
The paired Astra/Sol trajectories therefore share an R1 baseline with the old
cohort and are not ten entirely new independent starts.

Time sums active candidate execution, including tools, self-tests and all
same-release retry attempts. It excludes evaluator time, between-release waits
and quota waits between attempts. Opus's saved status contained only its last
retry for R1 and R5; these published times instead sum every CLI attempt receipt.
''')
sections.append(table(['Run', 'Reused R1', 'Reused cost', 'New work', 'New cost', 'Total'], [
    [label(r), time(r['reused_seconds']), f"${r['reused_usage']['api_equivalent_usd']:.2f}",
     time(r['new_seconds']), f"${r['new_usage']['api_equivalent_usd']:.2f}", time(r['seconds'])] for r in runs]))
sections.append('''### Tokens and Pricing

Input includes cached reads and cache writes; reasoning is included in output.
OpenAI usage is deduplicated request-level evidence through each delivery,
including compaction. Claude usage sums per-attempt receipts and reconciles to
the cumulative CLI dollar total; cumulative resumed-session totals are not added
twice. Claude request counts were not recorded.

Standard USD per million input / cached-read / output tokens: Astra $10 / $1 /
$50; Sol $2 / $0.20 / $10; Luna $0.10 / $0.01 / $0.50; Opus $4 / $0.20 / $20.
Opus cache writes cost $5 (five-minute) or $8 (one-hour); observed writes use the
one-hour rate. OpenAI long-context pricing applies per request above 272K input
tokens, at 2x input and 1.5x output; no included request crossed that threshold.
These are API-equivalent usage estimates, not subscription charges or evaluator
costs. Rates verified 28 September 2026 against
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
SHA-256 in [results.json](site/results.json), alongside all 50 snapshot manifests.
''')
sections.append(table(['Run', 'Production files', 'Test files', 'Largest production file', 'Lines', 'Source'], [
    [label(r), r['code']['production_files'], sum(f['category'] == 'test' for f in r['code']['files']),
     '`' + r['code']['largest']['path'] + '`', r['code']['largest']['lines'],
     f"[Download](https://github.com/kkondaurov/billingbench/releases/download/v{data['version']}/{r['source_archive']['file']})"] for r in runs]))
sections.append('''## What the Evaluator Repairs Changed

All 50 unchanged release snapshots and ten retained-history suites were rescored
using identical frozen R3 sources. Across 3,860 scenario outcomes, there were
zero evaluator exceptions. All 7,473 prior evidence-file hashes and 50 snapshot
trees were reverified. The candidate applications were not changed.

R2 converts missing required response fields into explicit contract failures.
R3 supports valid corrected-transfer layouts, validates preview response fields
and checks independent expected economics in the closed-sale scenario. The suite
passed 44 evaluator regression tests and recorded-response qualification covering
354 previews and 482 transfer collections. Four deliberately corrupted preview
responses failed; the valid original passed. Structural validation is not an
exhaustive independent calculation of every preview's economics.

Four ID-sensitive scenarios run eight times on fresh tenants and require eight
passes. Opus's two customer-boundary checks passed only 4/8 and 3/8 trials;
failures shifted adjustments by one cent. Sol #2's successor-agreement scenario
passed 6/8 trials, with the two failures creating an extra $400 invoice despite
no new sale. Repetition detects these unstable results but cannot prove that no
other nondeterminism remains.

Opus's old score of 107 first rose to 109 when two false failures were fixed,
then returned to 107 when repeated tests exposed two lucky rounding passes.
Sol #2 fell from 79 to 78. Other final API totals and all retained-history totals
were unchanged. Per-case changes and all eight repetition statuses are included
in the download.

## Disputed Expectations

Two checks remain disputed: whether a zero-net termination may create offsetting
billing documents, and whether a closed-month correction may be rejected instead
of entering a held-operation workflow. Strict /123 scores retain the original
test expectations. The /121 comparison excludes both scenarios uniformly for
every run, rather than selectively granting credit. The Astra-versus-Sol ordering
survives either treatment. Failing a scenario does not always mean a wrong total;
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
''')
sections.append(table(['Run', 'Releases observed', 'Tool-call intervals', 'Outside tool calls'], [
    [label(r), ', '.join(map(str, r['timing_audit']['releases'])),
     f"{100 * r['timing_audit']['tool_wait_seconds'] / r['timing_audit']['recorded_seconds']:.1f}%",
     f"{100 * r['timing_audit']['outside_tool_seconds'] / r['timing_audit']['recorded_seconds']:.1f}%"]
    for r in runs if 'timing_audit' in r]))
sections.append('''## Protocol and Provenance Limits

Development databases carry forward where a checkpoint exists. Opus's imported
R1 had none, so its R2 began with a fresh development database. This differs from
the restored Codex development databases. Independent retained-history tests
exercise real upgrades for every model. Luna #2 changed its candidate-local
schema file after delivery of the verified public packet; frozen requirements
and private evaluator sources remained unchanged.

The [old continuous-session cohort](https://kkondaurov.github.io/billingbench/archive/v1.0.0/)
is preserved separately. Its published scores used R1, while this cohort uses R3,
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
print('Rendered REPORT.md from site/results.json')
