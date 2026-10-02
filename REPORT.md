# Billing Bench v1.3.0: Results

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

## Reused Work, New Work, and Cost

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

## Code and Downloads

Final source archives contain application sources and configuration only, not
sessions, credentials, build outputs or the private evaluator. Every file has a
SHA-256 in [results.json](site/results.json), alongside all 70 snapshot manifests.


| Run | Production files | Test files | Largest production file | Lines | Source |
| --- | --- | --- | --- | --- | --- |
| Astra low #1 | 25 | 10 | `lib/billing_bench/domain/agreements.ex` | 1476 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/astra-low-01-m5-source.tar.gz) |
| Astra low #2 | 25 | 8 | `lib/billing_bench/metering.ex` | 1607 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/astra-low-02-m5-source.tar.gz) |
| Astra low #3 | 23 | 16 | `lib/billing_bench/agreements.ex` | 1777 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/astra-low-03-m5-source.tar.gz) |
| Sol 6 xhigh #1 | 23 | 10 | `lib/billing_bench/billing.ex` | 3099 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/sol6-xhigh-01-m5-source.tar.gz) |
| Sol 6 xhigh #2 | 23 | 10 | `lib/billing_bench/billing.ex` | 2344 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/sol6-xhigh-02-m5-source.tar.gz) |
| Sol 6 xhigh #3 | 28 | 8 | `lib/billing_bench/billing.ex` | 2115 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/sol6-xhigh-03-m5-source.tar.gz) |
| Luna 6 xhigh #1 | 14 | 8 | `lib/billing_bench_web/api.ex` | 15176 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/luna6-xhigh-01-m5-source.tar.gz) |
| Luna 6 xhigh #2 | 15 | 8 | `lib/billing_bench/domain/api.ex` | 13853 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/luna6-xhigh-02-m5-source.tar.gz) |
| Luna 6 xhigh #3 | 22 | 4 | `lib/billing_bench/domain/sell.ex` | 3414 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/luna6-xhigh-03-m5-source.tar.gz) |
| Opus 5.5 xhigh #1 | 67 | 28 | `lib/billing_bench/domain/billing.ex` | 1480 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/opus55-xhigh-01-m5-source.tar.gz) |
| Sol 6.1 xhigh #1 | 27 | 9 | `lib/billing_bench/agreements.ex` | 2139 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/sol61-xhigh-01-m5-source.tar.gz) |
| Sol 6.1 xhigh #2 | 33 | 10 | `lib/billing_bench/billing/agreements.ex` | 1669 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/sol61-xhigh-02-m5-source.tar.gz) |
| Sol 6.1 xhigh #3 | 30 | 14 | `lib/billing_bench/domain/history.ex` | 2129 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/sol61-xhigh-03-m5-source.tar.gz) |
| Opus 5.5 xhigh #2 | 74 | 27 | `lib/billing_bench/domain/billing.ex` | 1669 | [Download](https://github.com/kkondaurov/billingbench/releases/download/v1.3.0/opus55-xhigh-02-m5-source.tar.gz) |

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
