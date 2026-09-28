# Billing Bench

Can a coding agent build a B2B billing backend, then evolve it through five
releases without losing the financial history?

**[Results dashboard](https://kkondaurov.github.io/billingbench/)**

Ten completed trajectories: three GPT-6 Astra low, three GPT-6 Sol xhigh, three
GPT-6 Luna xhigh, and one Claude Opus 5.5 xhigh. Each release starts a fresh
conversation. OpenAI models use Codex CLI; Opus uses Claude Code.

## Results

| Model / effort | Runs | Mean API /123 | Mean histories /20 | Mean time | Mean API cost | Median prod LOC | Median test LOC |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-6 Astra low | 3 | 110.7 | 18.0 | 2h 59m | $54.29 | 10,419 | 4,850 |
| Claude Opus 5.5 xhigh | 1 | 107 | 19 | 3h 37m | $77.55 | 21,818 | 8,149 |
| GPT-6 Sol xhigh | 3 | 79.0 | 18.0 | 5h 21m | $46.12 | 14,282 | 7,137 |
| GPT-6 Luna xhigh | 3 | 39.7 | 4.7 | 7h 12m | $3.08 | 16,880 | 4,038 |

Every Astra run outscored and finished faster than every Sol run. Opus landed
inside Astra's score range, at a higher cost; one run does not establish its
variation. Luna was much cheaper but substantially less correct. This cohort
does not test different effort settings within a model.

Time and API-equivalent cost include all five releases, including reused R1 for
Astra, Sol and Opus. The dashboard separates reused work from new R2-R5 work.
Costs are standard-rate usage equivalents, not subscription bills. LOC counts
physical lines including comments/blanks. Shared-host time is not a controlled
latency benchmark. Two disputed API checks are also reported separately.

## Publication v1.1.0

- [Full report, per-run metrics and limitations](REPORT.md)
- [Benchmark definition and commands](benchmark/v1/README.md)
- [Candidate packets](benchmark/v1/candidate/0.5/manifest.json)
- [Corrected R3 evaluator](benchmark/v1/evaluation/0.5/billing_eval/selection.py)
- [Machine-readable results, tokens, hashes and per-case outcomes](site/results.json)
- [Release and final application sources](https://github.com/kkondaurov/billingbench/releases/tag/v1.1.0)
- [Archived continuous-session report](https://kkondaurov.github.io/billingbench/archive/v1.0.0/)

All 50 release snapshots and ten retained-history suites were rescored with one
corrected evaluator. No candidate implementation changed. The five-release
requirements are unchanged; the v1.0.0 tag and old cohort remain preserved.

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
