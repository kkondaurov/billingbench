# Billing Bench v1.6.0: Results

27 October 2026. Seventeen earlier trajectories plus three paired Terra starts,
with strict and completion-assisted cohorts and intermediate branches.
[Interactive dashboard](https://kkondaurov.github.io/billingbench/).

## GPT-6.1 Terra: Strict and Completion-Assisted

Three independent starts produced three strict one-turn M1-M5 trajectories.
Every standard delivery explicitly admitted unfinished work; all CLI turns
completed normally, without timeout, quota cutoff or context exhaustion. All
three final strict scores are 1/123 and retained histories 0/20. Those submissions
are unchanged, not replaced by the later recoveries.

In the separate assisted experiment, each release received at most one generic
same-session request to complete its delivery, on an isolated source/database/
runtime clone. No private evaluator information was supplied. The latest source
and development database, rather than the highest-scoring source, were handed
to the next fresh conversation/runtime. There are five completion nudges per
assisted chain. These paired follow-ups are not three additional independent
starting samples or interchangeable baseline results.

| Branch | R1 /34 | R2 /51 | R3 /71 | R4 /87 | R5 /123 | Histories /20 | Total time | Extra nudge time | API equivalent | Production LOC | Test LOC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Strict #1 | 1 | 1 | 1 | 1 | 1 | 0 | 8.05 min | 0 | $0.787446 | 1,909 | 1,049 |
| Strict #2 | 1 | 1 | 1 | 1 | 1 | 0 | 8.01 min | 0 | $0.839399 | 2,892 | 1,287 |
| Strict #3 | 1 | 1 | 1 | 1 | 1 | 0 | 9.69 min | 0 | $1.005257 | 2,666 | 1,094 |
| Assisted #1 | 33 | 47 | 66 | 80 | 102 | 15 | 214.20 min | 202.07 min | $44.782999 | 19,491 | 6,320 |
| Assisted #2 | 32 | 48 | 67 | 82 | 112 | 20 | 218.24 min | 207.79 min | $46.256800 | 25,148 | 22,712 |
| Assisted #3 | 32 | 47 | 66 | 78 | 109 | 20 | 195.33 min | 181.83 min | $43.972189 | 20,415 | 12,622 |

Assisted mean final score is 107.7/123, observed range 102-112; mean histories
18.3/20, range 15-20. Mean time is 3h 29m; mean API-equivalent cost $45.00.
The score spread is 10 cases (8.1 percentage points), not a stable population
variance estimate. Sol 6.1's existing strict-protocol mean is 110/123 at $13.63;
Terra's assisted performance is therefore not evidence of better strict
reliability or lower total token cost. Faster wall-clock completion can coexist
with substantial token use. No model-only causality is established.

| Assisted chain | Archived input tokens | Cached input tokens | Output tokens, including reasoning | Reasoning subset | Requests | Long requests |
| --- | --- | --- | --- | --- | --- | --- |
| #1 | 449,299,651 | 446,179,968 | 933,192 | 368,428 | 1,867 | 748 |
| #2 | 433,836,168 | 430,375,040 | 1,045,928 | 410,297 | 1,801 | 772 |
| #3 | 439,857,273 | 436,833,920 | 944,860 | 370,044 | 1,860 | 745 |

The dashboard exposes all fifteen paired initial/nudged scores, extra time and
cost, gains and regressions. Branch #3's R3 nudge gained all twenty new cases but
lost one earlier held-scope-recovery case; that loss was retained and never fed
back. All three final M5 nudges gained passes without losing a previously
passing same-release case. Initial R2-R5 scores on recovered prefixes are not the
strict cohort's later scores; the experiment changes the input prefix.

The earlier M1-only-assisted experiment is supplementary: final scores 37, 43
and 35/123, histories 8/20 each, times 51.30, 64.96 and 46.54 minutes and costs
$9.606800, $12.126012 and $8.320016. Production/test LOC are 6,739/1,767,
11,070/5,358 and 7,738/2,735. These share recovered R1 with the fully assisted
chains, so their shared snapshot evaluation is counted once. Their source
downloads, stage scores, usage and histories are preserved in supplementary
results rather than pooled into headline comparisons.

Exact model `gpt-6.1-terra`, xhigh, standard speed, Codex CLI 0.164.0. Runtime is
the pinned VZ/aarch64 Elixir 1.20.2 / OTP 29.0.4 / PostgreSQL 17.11 image, with
2 CPUs and 4 GiB per runtime. Older models used different CLI/runtime versions;
the concurrent Terra branches shared the host. No measured contention penalty
or provider-thinking/host-resource time split is claimed.

[Official Standard pricing](https://developers.openai.com/api/docs/pricing) was
verified on 26 and 27 October: $1/M input, $0.05/M cached input, $5/M output.
[Long-context pricing](https://developers.openai.com/api/docs/models/gpt-6.1-terra)
uses 2x input/cache and 1.5x output for actual requests over 272K input. Dated and
publication rates match. Pricing deduplicates archived response identities and
adds individual usage, never cumulative resumed counters; reasoning is already
in output. All initial/nudge usage counts, but discarded alternative branches
and evaluator work do not. These are API equivalents for subscription runs,
not native bills; interrupted requests without usage records may be missing.

All 60 new unique evaluation jobs finished with full inventories and zero case
errors. Combined inventory: 162 jobs, 10,777 scenario outcomes, preserving the
13 earlier DeepSeek candidate-contract errors. Frozen R4 sources and previous
102 jobs/17 rows are unchanged. Source, input, session, runtime and database
hashes, all unique cases, raw results and copied evaluator sources were checked.
The original, intermediate, normal-before and assisted snapshots remain separate.
The release gate includes 92 regression/export tests, archive/privacy checks and
desktop/mobile checks at 1440/768/390/320 pixels across all chart axes/cost bases.

## Earlier Comparison

## Setup and Result

Each agent builds and evolves an Elixir/Phoenix/PostgreSQL billing backend.
Every release begins a new conversation and runtime. The agent retains its
submitted code, not the previous conversation. No private evaluator feedback or
subagents are provided. Three runs each use GPT-6 Astra low, GPT-6.1 Sol xhigh,
GPT-6 Sol xhigh and GPT-6 Luna xhigh in Codex CLI; two use Claude Opus 5.5 xhigh
in Claude Code. Three use DeepSeek V4.1 Flash high through OpenCode / OpenRouter,
pinned to Reka with no fallback.

Sol 6.1 passed 109-111 of 123 final API cases, close to Astra's 105-117, for
$12.58-$15.73 per run versus Astra's $48.49-$61.26. Every Astra run finished
in under four hours; Sol 6.1 took 4h 44m-6h 27m. Every Sol 6.1 run outscored every Sol 6 run
(71-88), with a much narrower observed score range. Opus scored 105 and 107
for $82.21 and $77.55; its second run passed all 20 retained histories.
Luna cost about $3 but delivered much less of the required
behavior. DeepSeek scored 50, 12 and 58 API cases, with 3, 2 and 18 histories,
in 3h 06m-4h 50m. At one common Reka quote the token mixes cost $15.73-$19.01.
The observed three-run spread is not a stable estimate of population variance.
No run passed the entire API suite.

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

DeepSeek costs in headline tables use one quote for all three token mixes:
$0.08/M uncached input, $0.08/M cached input and $0.80/M output, verified
24 October 2026 at 01:14 UTC. Other models retain their dated verified rates.
Original DeepSeek SDK estimates are preserved separately below. Costs are not bills.


| Run | API /123 | Undisputed /121 | Histories /20 | Time | API cost | Prod LOC | Test LOC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Astra low #1 | 110 | 109 | 14 | 2h 25m | $48.49 | 10,510 | 4,264 |
| Astra low #2 | 117 | 116 | 20 | 3h 53m | $61.26 | 10,419 | 4,850 |
| Astra low #3 | 105 | 104 | 20 | 2h 40m | $53.13 | 10,119 | 4,851 |
| Sol 6 xhigh #1 | 88 | 87 | 20 | 6h 15m | $45.13 | 14,282 | 7,237 |
| Sol 6 xhigh #2 | 78 | 78 | 18 | 4h 48m | $46.30 | 13,183 | 5,550 |
| Sol 6 xhigh #3 | 71 | 71 | 16 | 5h 01m | $46.92 | 14,590 | 7,137 |
| Luna 6 xhigh #1 | 43 | 43 | 7 | 6h 50m | $3.18 | 16,124 | 3,773 |
| Luna 6 xhigh #2 | 30 | 30 | 4 | 7h 59m | $3.21 | 17,291 | 6,204 |
| Luna 6 xhigh #3 | 47 | 47 | 6 | 6h 47m | $2.85 | 16,880 | 4,038 |
| Opus 5.5 xhigh #1 | 107 | 107 | 19 | 3h 37m | $77.55 | 21,818 | 8,149 |
| Sol 6.1 xhigh #1 | 109 | 107 | 17 | 4h 44m | $12.58 | 12,318 | 6,527 |
| Sol 6.1 xhigh #2 | 111 | 111 | 16 | 4h 48m | $12.58 | 13,266 | 5,814 |
| Sol 6.1 xhigh #3 | 110 | 109 | 16 | 6h 27m | $15.73 | 13,351 | 7,883 |
| Opus 5.5 xhigh #2 | 105 | 104 | 20 | 3h 32m | $82.21 | 21,402 | 7,363 |
| DeepSeek V4.1 Flash high #1 | 50 | 50 | 3 | 3h 45m | $19.01 | 20,478 | 4,745 |
| DeepSeek V4.1 Flash high #2 | 12 | 11 | 2 | 4h 50m | $15.73 | 21,033 | 4,743 |
| DeepSeek V4.1 Flash high #3 | 58 | 57 | 18 | 3h 06m | $17.82 | 25,013 | 5,553 |

## Release Scores

Requirements and denominators grow with each release; a larger pass count alone
does not establish that earlier behavior survived unchanged.


| Run | R1 /34 | R2 /51 | R3 /71 | R4 /87 | R5 /123 |
| --- | --- | --- | --- | --- | --- |
| Astra low #1 | 33 | 49 | 67 | 77 | 110 |
| Astra low #2 | 33 | 50 | 69 | 81 | 117 |
| Astra low #3 | 31 | 47 | 65 | 78 | 105 |
| Sol 6 xhigh #1 | 26 | 40 | 55 | 63 | 88 |
| Sol 6 xhigh #2 | 30 | 45 | 64 | 67 | 78 |
| Sol 6 xhigh #3 | 28 | 43 | 62 | 70 | 71 |
| Luna 6 xhigh #1 | 15 | 24 | 35 | 36 | 43 |
| Luna 6 xhigh #2 | 15 | 27 | 27 | 30 | 30 |
| Luna 6 xhigh #3 | 19 | 32 | 41 | 45 | 47 |
| Opus 5.5 xhigh #1 | 33 | 50 | 70 | 77 | 107 |
| Sol 6.1 xhigh #1 | 32 | 49 | 68 | 73 | 109 |
| Sol 6.1 xhigh #2 | 33 | 49 | 68 | 78 | 111 |
| Sol 6.1 xhigh #3 | 34 | 51 | 67 | 79 | 110 |
| Opus 5.5 xhigh #2 | 30 | 47 | 64 | 79 | 105 |
| DeepSeek V4.1 Flash high #1 | 21 | 31 | 39 | 43 | 50 |
| DeepSeek V4.1 Flash high #2 | 7 | 8 | 9 | 12 | 12 |
| DeepSeek V4.1 Flash high #3 | 21 | 33 | 47 | 47 | 58 |

## Reused Work, New Work, and Cost

Astra, Sol 6 and Opus #1 reuse their own unchanged first-release submission; R2-R5
were implemented again with fresh conversations. Luna, Sol 6.1, Opus #2 and DeepSeek begin at the
scaffold and implement all five releases, carrying their code forward each time.
Reused work is included in the headline totals, not free
work. The paired Astra/Sol 6 trajectories share an R1 baseline with the old
cohort; these are not seventeen entirely new independent starts.

Time sums active candidate execution, including tools, self-tests and all
same-release retry attempts. It excludes evaluator time, between-release waits
and quota waits between attempts. Opus #1's saved status contained only its last
retry for R1 and R5; these published times instead sum every CLI attempt receipt.


| Run | Reused R1 | Reused cost | New work | New cost | Total |
| --- | --- | --- | --- | --- | --- |
| Astra low #1 | 0h 43m | $11.39 | 1h 42m | $37.09 | 2h 25m |
| Astra low #2 | 0h 48m | $12.90 | 3h 04m | $48.36 | 3h 53m |
| Astra low #3 | 0h 49m | $10.40 | 1h 51m | $42.73 | 2h 40m |
| Sol 6 xhigh #1 | 1h 17m | $9.31 | 4h 58m | $35.82 | 6h 15m |
| Sol 6 xhigh #2 | 1h 24m | $11.08 | 3h 24m | $35.22 | 4h 48m |
| Sol 6 xhigh #3 | 1h 27m | $13.19 | 3h 34m | $33.73 | 5h 01m |
| Luna 6 xhigh #1 | 0h 00m | $0.00 | 6h 50m | $3.18 | 6h 50m |
| Luna 6 xhigh #2 | 0h 00m | $0.00 | 7h 59m | $3.21 | 7h 59m |
| Luna 6 xhigh #3 | 0h 00m | $0.00 | 6h 47m | $2.85 | 6h 47m |
| Opus 5.5 xhigh #1 | 0h 54m | $17.91 | 2h 43m | $59.64 | 3h 37m |
| Sol 6.1 xhigh #1 | 0h 00m | $0.00 | 4h 44m | $12.58 | 4h 44m |
| Sol 6.1 xhigh #2 | 0h 00m | $0.00 | 4h 48m | $12.58 | 4h 48m |
| Sol 6.1 xhigh #3 | 0h 00m | $0.00 | 6h 27m | $15.73 | 6h 27m |
| Opus 5.5 xhigh #2 | 0h 00m | $0.00 | 3h 32m | $82.21 | 3h 32m |
| DeepSeek V4.1 Flash high #1 | 0h 00m | $0.00 | 3h 45m | $19.01 | 3h 45m |
| DeepSeek V4.1 Flash high #2 | 0h 00m | $0.00 | 4h 50m | $15.73 | 4h 50m |
| DeepSeek V4.1 Flash high #3 | 0h 00m | $0.00 | 3h 06m | $17.82 | 3h 06m |

### Tokens and Pricing

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


| Run | Input tokens | Cached read | Cache write | Output | Reasoning | Requests | API cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Astra low #1 | 28,927,487 | 28,193,664 | 0 | 259,095 | 67,046 | 285 | $48.49 |
| Astra low #2 | 38,035,484 | 37,153,792 | 0 | 305,736 | 96,516 | 326 | $61.26 |
| Astra low #3 | 31,243,280 | 30,437,888 | 0 | 292,764 | 93,087 | 283 | $53.13 |
| Sol 6 xhigh #1 | 171,036,477 | 168,866,048 | 0 | 701,989 | 312,242 | 1231 | $45.13 |
| Sol 6 xhigh #2 | 181,362,979 | 179,368,704 | 0 | 643,967 | 269,175 | 1258 | $46.30 |
| Sol 6 xhigh #3 | 176,676,000 | 174,342,784 | 0 | 738,857 | 317,936 | 1308 | $46.92 |
| Luna 6 xhigh #1 | 229,339,924 | 225,653,504 | 0 | 1,106,626 | 628,719 | 1557 | $3.18 |
| Luna 6 xhigh #2 | 227,512,907 | 223,342,592 | 0 | 1,111,017 | 601,585 | 1604 | $3.21 |
| Luna 6 xhigh #3 | 198,677,224 | 195,114,496 | 0 | 1,088,189 | 615,130 | 1402 | $2.85 |
| Opus 5.5 xhigh #1 | 139,882,189 | 136,862,476 | 3,018,741 | 1,301,373 | 692,524 | Not recorded | $77.55 |
| Sol 6.1 xhigh #1 | 51,850,278 | 50,460,416 | 0 | 475,844 | 188,806 | 395 | $12.58 |
| Sol 6.1 xhigh #2 | 48,230,999 | 46,687,232 | 0 | 481,924 | 196,102 | 366 | $12.58 |
| Sol 6.1 xhigh #3 | 55,768,951 | 53,771,904 | 0 | 636,288 | 317,386 | 442 | $15.73 |
| Opus 5.5 xhigh #2 | 134,178,057 | 130,452,869 | 3,724,274 | 1,315,965 | 725,753 | 457 | $82.21 |
| DeepSeek V4.1 Flash high #1 | 227,443,334 | 226,728,320 | 0 | 1,021,431 | 536,052 | 1028 | $19.01 |
| DeepSeek V4.1 Flash high #2 | 186,469,383 | 185,723,392 | 0 | 1,018,179 | 580,227 | 845 | $15.73 |
| DeepSeek V4.1 Flash high #3 | 212,622,296 | 211,546,496 | 0 | 1,014,848 | 540,108 | 890 | $17.82 |

## Code and Downloads

Final source archives contain application sources and configuration only, not
sessions, credentials, build outputs or the private evaluator. Every file has a
SHA-256 in [results.json](site/results.json), alongside all 85 snapshot manifests.


| Run | Production files | Test files | Largest production file | Lines | Source |
| --- | --- | --- | --- | --- | --- |
| Astra low #1 | 25 | 10 | `lib/billing_bench/domain/agreements.ex` | 1476 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/astra-low-01-m5-source.tar.gz) |
| Astra low #2 | 25 | 8 | `lib/billing_bench/metering.ex` | 1607 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/astra-low-02-m5-source.tar.gz) |
| Astra low #3 | 23 | 16 | `lib/billing_bench/agreements.ex` | 1777 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/astra-low-03-m5-source.tar.gz) |
| Sol 6 xhigh #1 | 23 | 10 | `lib/billing_bench/billing.ex` | 3099 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/sol6-xhigh-01-m5-source.tar.gz) |
| Sol 6 xhigh #2 | 23 | 10 | `lib/billing_bench/billing.ex` | 2344 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/sol6-xhigh-02-m5-source.tar.gz) |
| Sol 6 xhigh #3 | 28 | 8 | `lib/billing_bench/billing.ex` | 2115 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/sol6-xhigh-03-m5-source.tar.gz) |
| Luna 6 xhigh #1 | 14 | 8 | `lib/billing_bench_web/api.ex` | 15176 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/luna6-xhigh-01-m5-source.tar.gz) |
| Luna 6 xhigh #2 | 15 | 8 | `lib/billing_bench/domain/api.ex` | 13853 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/luna6-xhigh-02-m5-source.tar.gz) |
| Luna 6 xhigh #3 | 22 | 4 | `lib/billing_bench/domain/sell.ex` | 3414 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/luna6-xhigh-03-m5-source.tar.gz) |
| Opus 5.5 xhigh #1 | 67 | 28 | `lib/billing_bench/domain/billing.ex` | 1480 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/opus55-xhigh-01-m5-source.tar.gz) |
| Sol 6.1 xhigh #1 | 27 | 9 | `lib/billing_bench/agreements.ex` | 2139 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/sol61-xhigh-01-m5-source.tar.gz) |
| Sol 6.1 xhigh #2 | 33 | 10 | `lib/billing_bench/billing/agreements.ex` | 1669 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/sol61-xhigh-02-m5-source.tar.gz) |
| Sol 6.1 xhigh #3 | 30 | 14 | `lib/billing_bench/domain/history.ex` | 2129 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/sol61-xhigh-03-m5-source.tar.gz) |
| Opus 5.5 xhigh #2 | 74 | 27 | `lib/billing_bench/domain/billing.ex` | 1669 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/opus55-xhigh-02-m5-source.tar.gz) |
| DeepSeek V4.1 Flash high #1 | 27 | 8 | `lib/billing_bench/api.ex` | 4261 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/deepseek41-high-01-m5-source.tar.gz) |
| DeepSeek V4.1 Flash high #2 | 25 | 8 | `lib/billing_bench/billing.ex` | 3355 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/deepseek41-high-02-m5-source.tar.gz) |
| DeepSeek V4.1 Flash high #3 | 33 | 8 | `lib/billing_bench/billing/operations.ex` | 3479 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.5.0/deepseek41-high-03-m5-source.tar.gz) |

## Independent Opus Replicate

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


## DeepSeek V4.1 Flash

Exact model `deepseek/deepseek-v4.1-flash-1017`, OpenCode 1.18.31 / OpenRouter,
Reka only with no fallback, high requested reasoning and a 262,144-token response
cap. Quantization and native reasoning-budget equivalence are unknown. This is
three independent fresh M1-M5 trajectories, with a new conversation/runtime per release.
Final API scores are 50, 12 and 58 of 123; retained histories are 3, 2 and 18
of 20. Fresh/upgrade passes are 3/0, 1/1 and 9/9 of ten each. Implementation
times are 3h 45m, 4h 50m and 3h 06m. Production LOC range from 20,478 to
25,013; test LOC range from 4,743 to 5,553. These are observed min/max ranges,
not confidence intervals or a reliable population-variance estimate.

Implementation time is 3h 45m including one 30-second transport backoff in M5.
The upstream 429 resumed the same release session and runtime. Archived SDK
counters total 715,014 uncached input, 226,728,320 cached input, 485,379 output
excluding reasoning and 536,052 reasoning tokens. The public tables normalize
input to include cached reads, and output to include reasoning, without counting
either twice. There are 1,028 archived assistant messages including the failed
429 message with zero recorded usage.

Run #1's $1.40029566 estimate uses the archived run-start Reka rates on 23 October:
$0.15/M uncached input, $0.003/M cached input and $0.60/M output including
reasoning. These are dated estimate rates, not a current quote or native billing
receipt. Unarchived interrupted-request usage may be missing; account-level
credit changes are not run-exclusive. Native preflight charges are separate.
Run #2 froze $0.08/$0.004/$0.40 per million uncached/cached/output tokens,
for a $1.209844448 SDK estimate. Run #3 froze $0.08/$0.08/$0.80,
for $17.82166208. The live quote changed during run #2, so its exact billed
cost cannot be reconstructed without provider receipts. Repricing the same
archived token mixes at run #3's quote gives $19.01261152, $15.73209384 and
$17.82166208: a mean of $17.52, not the misleading mean of mixed dated prices.
All three mixes are also available at each dated quote in the table below.

The original QEMU VM/image had been removed. All three runs used the same qualified rebuilt
VZ/aarch64 runtime with Elixir 1.20.2, OTP 29.0.4 and PostgreSQL 17.11, with the
same frozen scaffold, audited R4 evaluator and 2 CPU / 4 GiB candidate limits.
Harness, provider and runtime differences from older models are not isolated.

All five snapshot and session/runtime identities, eight development-database
checkpoints, copied evaluator sources and six scoring outputs were verified.
The supervisor's final bookkeeping expected an object instead of the retained
evaluator's array and crashed after scoring. All twenty records and individual
traces were independently checked; the readout was recovered without rerunning
the candidate or evaluator, or changing frozen sources. The public receipt
preserves the unavailable retained-process exit code rather than inventing one.
Run #1 had no evaluator exceptions or application-startup failures.
Runs #2 and #3 add twelve complete jobs without rerunning prior work. The
previous fifteen result rows and 90 scoring records are unchanged.

Run #2's M1 diagnostic reproduced a candidate rate-unit bug on disposable
controls; the official 7/34 score and candidate submissions were not changed.
Run #3 has 2, 3, 4 and 4 raw error rows at R2-R5: 13 occurrences, four distinct
final cases. Required nested application `source:{kind,id}` or rated-charge
`overage_minor` fields are absent. Unchanged disposable replays reproduced
the exceptions. These candidate response-contract errors remain errors in
the raw outcomes, stay in the denominator and are not counted as passes.
All six evaluation processes exited zero with complete unique case inventories.
The supervisor's over-strict `execution_failure` labels are preserved separately;
there are no missing jobs or unexplained execution failures. The comparison
now contains 102 jobs and 6,562 outcomes under unchanged frozen R4 sources.

Run #3's first release and part of its second overlapped run #2 and its scoring.
No measured contention penalty or provider-thinking-time split is available;
times are not adjusted by a guessed factor.


| Run | Dated rates: uncached / cached / output | Dated SDK estimate | At #1 rates | At #2 rates | At #3 common rates |
| --- | --- | --- | --- | --- | --- |
| DeepSeek V4.1 Flash high #1 | $0.15 / $0.003 / $0.6 | $1.40029566 | $1.40029566 | $1.37268680 | $19.01261152 |
| DeepSeek V4.1 Flash high #2 | $0.08 / $0.004 / $0.4 | $1.20984445 | $1.27997623 | $1.20984445 | $15.73209384 |
| DeepSeek V4.1 Flash high #3 | $0.08 / $0.08 / $0.8 | $17.82166208 | $1.40491829 | $1.33818918 | $17.82166208 |

| Run / release | API | Case errors | Time | Prod LOC | Test LOC | Common-rate cost |
| --- | --- | --- | --- | --- | --- | --- |
| DeepSeek V4.1 Flash high #1 / R1 | 21/34 | 0 | 0h 53m | 7,672 | 651 | $5.774450 |
| DeepSeek V4.1 Flash high #1 / R2 | 31/51 | 0 | 0h 46m | 10,678 | 1,810 | $2.774102 |
| DeepSeek V4.1 Flash high #1 / R3 | 39/71 | 0 | 1h 04m | 15,244 | 2,729 | $6.114464 |
| DeepSeek V4.1 Flash high #1 / R4 | 43/87 | 0 | 0h 26m | 17,782 | 3,875 | $1.722212 |
| DeepSeek V4.1 Flash high #1 / R5 | 50/123 | 0 | 0h 37m | 20,478 | 4,745 | $2.627382 |
| DeepSeek V4.1 Flash high #2 / R1 | 7/34 | 0 | 1h 31m | 7,798 | 744 | $4.053835 |
| DeepSeek V4.1 Flash high #2 / R2 | 8/51 | 0 | 1h 23m | 10,412 | 1,888 | $2.459229 |
| DeepSeek V4.1 Flash high #2 / R3 | 9/71 | 0 | 0h 52m | 14,716 | 2,864 | $3.015031 |
| DeepSeek V4.1 Flash high #2 / R4 | 12/87 | 0 | 0h 29m | 17,631 | 3,555 | $2.303248 |
| DeepSeek V4.1 Flash high #2 / R5 | 12/123 | 0 | 0h 35m | 21,033 | 4,743 | $3.900750 |
| DeepSeek V4.1 Flash high #3 / R1 | 21/34 | 0 | 1h 10m | 10,006 | 1,269 | $5.032971 |
| DeepSeek V4.1 Flash high #3 / R2 | 33/51 | 2 | 0h 27m | 13,053 | 2,547 | $2.400460 |
| DeepSeek V4.1 Flash high #3 / R3 | 47/71 | 3 | 0h 25m | 17,430 | 3,490 | $2.294205 |
| DeepSeek V4.1 Flash high #3 / R4 | 47/87 | 4 | 0h 41m | 21,521 | 4,554 | $5.333962 |
| DeepSeek V4.1 Flash high #3 / R5 | 58/123 | 4 | 0h 23m | 25,013 | 5,553 | $2.760064 |

## What the Evaluator Repairs Changed

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


| Run | R1 | R2 | R3 | R4 | R5 | Histories |
| --- | --- | --- | --- | --- | --- | --- |
| Luna 6 xhigh #1 | 15 to 15 | 24 to 24 | 34 to 35 | 35 to 36 | 42 to 43 | 4 to 7 |
| Sol 6.1 xhigh #3 | 34 to 34 | 47 to 51 | 61 to 67 | 70 to 79 | 97 to 110 | 6 to 16 |



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


| Run | Releases observed | Tool-call intervals | Outside tool calls |
| --- | --- | --- | --- |
| Astra low #1 | 2, 3, 4, 5 | 4.1% | 95.8% |
| Astra low #2 | 2, 3, 4, 5 | 1.9% | 98.1% |
| Astra low #3 | 2, 3, 4, 5 | 2.7% | 97.2% |
| Sol 6 xhigh #1 | 2, 3, 4, 5 | 6.1% | 93.8% |
| Sol 6 xhigh #2 | 2, 3, 4, 5 | 10.8% | 89.1% |
| Sol 6 xhigh #3 | 2, 3, 4, 5 | 4.6% | 95.3% |
| Luna 6 xhigh #1 | 1, 2, 3, 4, 5 | 3.0% | 96.9% |
| Luna 6 xhigh #2 | 1, 2, 3, 4, 5 | 2.8% | 97.2% |
| Luna 6 xhigh #3 | 1, 2, 3, 4, 5 | 2.4% | 97.5% |

## Protocol and Provenance Limits

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
