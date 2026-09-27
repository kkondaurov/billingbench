# Billing Bench v1: Results

[Interactive report](https://kkondaurov.github.io/billingbench/) ·
[Benchmark definition](benchmark/v1/README.md) · [Result data](site/results.json) ·
[Release and application sources](https://github.com/kkondaurov/billingbench/releases/tag/v1.0.0)

Eight autonomous runs built the same B2B billing backend through five successive
releases. Agents started from a small Elixir/Phoenix scaffold, chose their domain
architecture, wrote their tests, and evolved their own application without
private evaluation feedback.

**Astra low gave the strongest balance of correctness and implementation time.**
Each of its three runs outscored each of the three Sol xhigh runs. Sol used fewer
API-equivalent dollars, but required more time and produced less reliable systems.

| Model / effort | n | API /123 | Histories /20 | Time | API-equivalent cost | Prod LOC | Test LOC |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-6 Astra low | 3 | 108.7 (103–115) | 18.7 (18–20) | 3h 12m | $64.99 | 11,417 | 4,869 |
| GPT-6 Astra xhigh | 1 | 114 | 20 | 4h 18m | $70.09 | 11,684 | 6,811 |
| GPT-6 Sol xhigh | 3 | 87.0 (73–99) | 16.0 (14–20) | 4h 37m | $40.19 | 13,392 | 5,859 |
| GPT-6 Sol low | 1 | 76 | 11 | 4h 05m | $41.78 | 13,123 | 5,366 |

Scores, time and cost are means; code sizes are medians. Parentheses show observed
run ranges, not confidence intervals. API and retained-history scores are separate.

## What Separated the Applications

The consequential failures concern old financial state: retaining a concession
through correction, keeping the original invoice's ownership through successive
transfers, and moving the full revenue distribution after accounting rules change.
The endpoint surface alone was not enough.

For example, Astra xhigh folded a new 30,000 sale into a transferred 40,000 billed
position. Reversing the old source then removed the new sale's coverage. All three
Astra low runs and all three Sol xhigh runs missed a current-routing one-cent
correction whose correct total hides an incorrect account distribution; Astra
xhigh passed that check.

Some defects have broad operational impact. Sol xhigh #3 rejected parent-linked
customer creation, blocking 17 scenarios. Those workflows fail as delivered, but
the evidence establishes one common setup blocker, not 17 different arithmetic
errors. Sol low placed Jan 20 pooled service on Jan 31 in its journal; four cases
expose that same date defect.

Higher effort did not guarantee a stronger result. The Astra xhigh probe scored
114 in 4.3 hours, versus the best low-effort result of 115 in 3.2 hours. Sol low's
76 falls within the wide xhigh range. One alternate-effort sample each supports
this comparison, not a general effort-response curve.

Five releases provide useful separation. No run passes the full API suite. The
retained-data checks also matter: they exercise later binaries against records
created by earlier releases rather than only testing empty databases.

## Run Results

| Run | API /123 | Histories /20 | Time | API cost | Prod LOC | Test LOC |
|---|---:|---:|---:|---:|---:|---:|
| Astra low #1 | 108 | 18 | 3h 22m | $70.67 | 11,417 | 5,431 |
| Astra low #2 | 103 | 18 | 3h 00m | $62.93 | 10,420 | 4,524 |
| Astra low #3 | 115 | 20 | 3h 15m | $61.39 | 11,482 | 4,869 |
| Astra xhigh #1 | 114 | 20 | 4h 18m | $70.09 | 11,684 | 6,811 |
| Sol xhigh #1 | 99 | 14 | 4h 26m | $37.07 | 13,701 | 5,859 |
| Sol xhigh #2 | 73 | 14 | 4h 37m | $37.31 | 13,099 | 5,703 |
| Sol xhigh #3 | 89 | 20 | 4h 49m | $46.21 | 13,392 | 5,904 |
| Sol low #1 | 76 | 11 | 4h 05m | $41.78 | 13,123 | 5,366 |

The final codebases contain 10,420–13,701 production lines and 4,524–6,811 test
lines. Physical lines include comments and blanks. Production comprises `lib/`
and database migrations; tests comprise `test/`. The shared scaffold contributes
123 and 58 lines respectively. Dependencies and generated builds are excluded.

## Measurement

- Five staged releases: foundation; changes; metering/sharing; agreements;
  historical correction. One continuing Codex CLI session per candidate, no
  subagents or evaluator feedback. Runtime allocation: 2 CPUs, 4 GiB RAM.
- Final API score: 123 complete deterministic scenarios, rerun for all eight
  unchanged final snapshots under the same audited R1 evaluator.
- Histories: ten paired fresh/upgrade scenarios ending at release 5, preserving
  the earlier database during upgrades. Reported from their separate history
  evaluations, not the final API-only repair pass.
- Main-effort samples #1–2 come from the preceding experiment's matching M1–M5
  prefix; #3 and the two effort probes are fresh five-release runs. Public packet
  and scaffold bytes match. Later experimental releases and goldens are excluded.
- Time sums candidate implementation intervals, including tools/self-tests but
  excluding evaluator time and between-release waits.
- Cost prices unique archived requests through M5, including compaction, at
  standard API rates. Cached input and reasoning are not double-counted. The
  detailed data preserves both request totals and CLI cumulative counters.
  This is not a subscription invoice.

Rates were verified on 27 September 2026: [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)
at $10/$1/$50 and [Sol](https://developers.openai.com/api/docs/models/gpt-6-sol)
at $2/$0.20/$10 per million input/cached-input/output tokens. No included request
crossed the 272K long-context threshold.

## Evaluation Boundaries

Strict scores retain two disputed termination outcomes in each of Astra low #2
and #3, and three disputed transfer-source outcomes in Sol xhigh #3. These concern
output semantics, not seven proven money errors; the JSON labels them individually.
They do not determine the Astra-low versus Sol-xhigh ordering. Required interface
omissions and wrong accounting-effect classifications remain contract failures.

All four new M5 applications pass the four published latency-gated operations at
up to 128 customers. An extra, unscored correction probe timed out on Sol xhigh #3
on a shared host. It remains unobserved pending an isolated repeat and is outside
the correctness score.

Evaluator repairs were qualified with 24 test methods and recorded-response
controls for five deliberately corrupted outputs. All original submissions and
raw results remain preserved. Version 1 publishes the settled 0.5 five-release
contract and repaired evaluator without retroactively changing candidate requests.

This is a benchmark of implementing a specified financial backend, not UI design,
product discovery or general production readiness. The defined accounting rules
are synthetic policies, not a claim of accounting-standard compliance.
