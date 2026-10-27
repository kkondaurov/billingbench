# Billing Bench

Can a coding agent build a B2B billing backend, then evolve it through five
releases without losing the financial history?

**[Results dashboard](https://kkondaurov.github.io/billingbench/)**

Seventeen completed trajectories: three each of GPT-6 Astra low, GPT-6.1 Sol
xhigh, GPT-6 Sol xhigh and GPT-6 Luna xhigh, plus two Claude Opus 5.5 xhigh
and three DeepSeek V4.1 Flash high.
Terra adds three strict one-turn runs and three completion-assisted follow-ups
from those same starts. These are separate protocol cohorts, not six independent
samples. Three earlier M1-only-assisted branches remain in supplementary details.
Each release starts a fresh conversation. OpenAI models use Codex CLI; Opus
uses Claude Code; DeepSeek uses OpenCode 1.18.31 with Reka on OpenRouter.

## Results

| Model / effort | Runs | Mean API /123 | Mean histories /20 | Mean time | Mean API cost | Median prod LOC | Median test LOC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-6 Astra low | 3 | 110.7 | 18.0 | 2h 59m | $54.29 | 10,419 | 4,850 |
| GPT-6.1 Sol xhigh | 3 | 110.0 | 16.3 | 5h 20m | $13.63 | 13,266 | 6,527 |
| Claude Opus 5.5 xhigh | 2 | 106.0 | 19.5 | 3h 34m | $79.88 | 21,610 | 7,756 |
| GPT-6.1 Terra xhigh, completion-assisted | 3 paired | 107.7 | 18.3 | 3h 29m | $45.00 | 20,415 | 12,622 |
| GPT-6 Sol xhigh | 3 | 79.0 | 18.0 | 5h 21m | $46.12 | 14,282 | 7,137 |
| DeepSeek V4.1 Flash high | 3 | 40.0 | 7.7 | 3h 54m | $17.52 | 21,033 | 4,745 |
| GPT-6 Luna xhigh | 3 | 40.0 | 5.7 | 7h 12m | $3.08 | 16,880 | 4,038 |
| GPT-6.1 Terra xhigh, strict one-turn | 3 | 1.0 | 0.0 | 0h 09m | $0.88 | 2,666 | 1,094 |

Sol 6.1 approaches Astra's final API correctness at a much lower API-equivalent
cost; Astra finishes faster. Sol 6.1 passes 109-111 cases versus Astra's 105-117
and Sol 6's 71-88. Opus's two results are within Astra's range, at a higher
cost. Luna is much cheaper but substantially less correct. No run passes the
entire API suite, and this cohort does not test effort settings within a model.
DeepSeek scores 50, 12 and 58 API cases and 3, 2 and 18 histories. Times span
3h 06m-4h 50m; production/test LOC span 20,478-25,013 / 4,743-5,553.
The three token mixes cost $15.73-$19.01 at one common Reka quote. This observed
spread does not establish stable population variance. Run #3's four final
candidate response-contract errors remain non-passes, not missing evaluations.

DeepSeek headline costs use $0.08/M uncached input, $0.08/M cached input and
$0.80/M output, verified 24 October 2026 at 01:14 UTC. Other models retain
their dated verified quotes. The report preserves each original SDK estimate
and reprices all three DeepSeek token mixes at every dated quote.

Time and cost include all five releases, including reused R1 for Astra, Sol 6
and Opus #1. Luna, Sol 6.1, Opus #2 and DeepSeek implement all five releases in new trajectories,
carrying their code forward between releases. The dashboard
separates reused and new work. Sol 6.1 uses CLI 0.159.0 versus 0.155.1 for the
older OpenAI runs, so this is not an isolated model-only comparison.
Costs are standard API equivalents, not subscription bills. LOC counts physical
lines including comments/blanks. Shared-host build time is not a controlled
latency benchmark. Two disputed API checks are also reported separately.

Terra's strict runs explicitly stopped incomplete at every release, without a
runner timeout, context exhaustion or usage cutoff. One generic same-session
completion request per release raised final scores to 102, 112 and 109/123 and
histories to 15, 20 and 20/20. Assisted time spans 3h 15m-3h 38m, costs
$43.97-$46.26, production LOC 19,491-25,148 and test LOC 6,320-22,712.
Time/cost include initial work and all five nudges. The intermediate M1-only
branches score 37,43,35/123 with 8/20 histories each; they are not in these means.
These observed three-run ranges are not stable estimates of population variance.
Terra uses Codex CLI 0.164.0 and the rebuilt VZ runtime; comparisons with older
CLI/runtime cohorts do not isolate model weights. Parallel work shared the host,
with no measured contention penalty or provider/host time split.

Terra Standard API rates were verified at launch on 26 October and again on
27 October: $1/M uncached input, $0.05/M cached input and $5/M output, with
2x input/cache and 1.5x output on actual requests above 272K input. Dated and
current rates are identical; resumed cumulative counters are never added twice,
and reasoning is already included in output. These are archived-request API
equivalents, not subscription bills; unrecorded interrupted usage may be missing.

## Publication v1.6.0

- [Full report, per-run metrics and limitations](REPORT.md)
- [Benchmark definition and commands](benchmark/v1/README.md)
- [Candidate packets](benchmark/v1/candidate/0.5/manifest.json)
- [Evaluator audit and controls](benchmark/v1/AUDIT_R4.md)
- [Machine-readable results, tokens, hashes and per-case outcomes](site/results.json)
- [Release and final application sources](https://github.com/kkondaurov/billingbench/releases/tag/v1.6.0)
- [Previous seventeen-run report](https://kkondaurov.github.io/billingbench/archive/v1.5.0/)
- [Previous fifteen-run report](https://kkondaurov.github.io/billingbench/archive/v1.4.0/)
- [Previous fourteen-run report](https://kkondaurov.github.io/billingbench/archive/v1.3.0/)
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

DeepSeek adds eighteen complete evaluations under unchanged frozen R4 sources,
bringing the comparison to 102 jobs and 6,562 scenario outcomes. Run #3 has 13
preserved candidate-contract error occurrences across R2-R5. All its evaluation
processes exited zero with complete inventories. Run #1's readout recovered a
post-scoring supervisor parsing failure; no candidate or evaluator was rerun.
The run-start Reka quote was $0.15/M uncached input, $0.003/M cached input and
$0.60/M output, including reasoning; #2 froze $0.08/$0.004/$0.40 and #3
$0.08/$0.08/$0.80. Pricing changed during #2; its exact bill needs receipts.
The SDK estimate is not native billing and
can miss unarchived interrupted-request usage. Its rebuilt VZ/aarch64 runtime
uses Elixir 1.20.2 / OTP 29.0.4: the older QEMU image was no longer available.
Harness, runtime and requested reasoning differences are not controlled away.

Terra adds 60 unique scoring jobs, including each before/after submission and
all three sets of histories: 162 jobs and 10,777 outcomes overall. Reused R1
receipts are counted once. All Terra jobs have complete case inventories and
zero case errors; the 13 earlier DeepSeek contract errors remain unchanged.
The R4 evaluator, previous seventeen rows and 102 receipts were not changed or
rerun. All original, intermediate and assisted artifacts are retained separately.

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
