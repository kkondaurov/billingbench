# Billing Bench

Can a coding agent build a B2B billing backend, then evolve it through five
releases without losing the financial history?

**[Results dashboard](https://kkondaurov.github.io/billingbench/)**

Thirteen completed trajectories: three each of GPT-6 Astra low, GPT-6.1 Sol
xhigh, GPT-6 Sol xhigh and GPT-6 Luna xhigh, plus one Claude Opus 5.5 xhigh.
Each release starts a fresh conversation. OpenAI models use Codex CLI; Opus
uses Claude Code.

## Results

| Model / effort | Runs | Mean API /123 | Mean histories /20 | Mean time | Mean API cost | Median prod LOC | Median test LOC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-6 Astra low | 3 | 110.7 | 18.0 | 2h 59m | $54.29 | 10,419 | 4,850 |
| GPT-6.1 Sol xhigh | 3 | 110.0 | 16.3 | 5h 20m | $13.63 | 13,266 | 6,527 |
| Claude Opus 5.5 xhigh | 1 | 107.0 | 19.0 | 3h 37m | $77.55 | 21,818 | 8,149 |
| GPT-6 Sol xhigh | 3 | 79.0 | 18.0 | 5h 21m | $46.12 | 14,282 | 7,137 |
| GPT-6 Luna xhigh | 3 | 40.0 | 5.7 | 7h 12m | $3.08 | 16,880 | 4,038 |

Sol 6.1 approaches Astra's final API correctness at a much lower API-equivalent
cost; Astra finishes faster. Sol 6.1 passes 109-111 cases versus Astra's 105-117
and Sol 6's 71-88. Opus's single result is within Astra's range, at a higher
cost. Luna is much cheaper but substantially less correct. No run passes the
entire API suite, and this cohort does not test effort settings within a model.

Time and cost include all five releases, including reused R1 for Astra, Sol 6
and Opus. Luna and Sol 6.1 implement all five releases in new trajectories,
carrying their code forward between releases. The dashboard
separates reused and new work. Sol 6.1 uses CLI 0.159.0 versus 0.155.1 for the
older OpenAI runs, so this is not an isolated model-only comparison.
Costs are standard API equivalents, not subscription bills. LOC counts physical
lines including comments/blanks. Shared-host build time is not a controlled
latency benchmark. Two disputed API checks are also reported separately.

## Publication v1.2.0

- [Full report, per-run metrics and limitations](REPORT.md)
- [Benchmark definition and commands](benchmark/v1/README.md)
- [Candidate packets](benchmark/v1/candidate/0.5/manifest.json)
- [Evaluator audit and controls](benchmark/v1/AUDIT_R4.md)
- [Machine-readable results, tokens, hashes and per-case outcomes](site/results.json)
- [Release and final application sources](https://github.com/kkondaurov/billingbench/releases/tag/v1.2.0)
- [Previous ten-run report](https://kkondaurov.github.io/billingbench/archive/v1.1.0/)
- [Archived continuous-session report](https://kkondaurov.github.io/billingbench/archive/v1.0.0/)

All 65 release snapshots and thirteen retained-history suites were rescored
with one frozen R4 evaluator. No candidate implementation changed. The
five-release requirements are unchanged; historical tags and cohorts remain
preserved separately.

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
