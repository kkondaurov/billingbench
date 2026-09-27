# Billing Bench

An autonomous software-engineering benchmark: build a B2B billing backend, then
evolve it through five releases without losing the financial history.

**[Read the v1 results](https://kkondaurov.github.io/billingbench/)**

Eight completed runs: three GPT-6 Astra low, three GPT-6 Sol xhigh, and one each
of Astra xhigh and Sol low. The report includes audited correctness, retained-data
histories, code size, implementation time, token usage and API-equivalent cost.

## Version 1.0.0

- [Benchmark definition and commands](benchmark/v1/README.md)
- [Candidate packets](benchmark/v1/candidate/0.5/manifest.json)
- [Evaluator](benchmark/v1/evaluation/0.5/billing_eval/selection.py)
- [Report in Markdown](REPORT.md)
- [Machine-readable results](site/results.json)
- [Tagged release and final application sources](https://github.com/kkondaurov/billingbench/releases/tag/v1.0.0)

Version 1 packages the settled five-release 0.5 specification and audited R1
evaluator. The candidate requirements are unchanged. Original internal version
paths are retained for exact source provenance.

## Results at a Glance

| Model / effort | Runs | Mean API cases /123 | Mean implementation time | Mean API-equivalent cost |
|---|---:|---:|---:|---:|
| GPT-6 Astra low | 3 | 108.7 | 3h 12m | $64.99 |
| GPT-6 Astra xhigh | 1 | 114 | 4h 18m | $70.09 |
| GPT-6 Sol xhigh | 3 | 87.0 | 4h 37m | $40.19 |
| GPT-6 Sol low | 1 | 76 | 4h 05m | $41.78 |

Every Astra-low sample outscored every Sol-xhigh sample and finished sooner.
Sol used fewer API-equivalent dollars. The two single-run effort probes did not
establish a reliable advantage from additional reasoning effort.

## Verify the Publication

```sh
python3 -B scripts/verify_v1.py
PYTHONPATH=benchmark/v1/evaluation/0.5 python3 -B -m unittest discover -s tests/v1
```

The static report is `site/index.html`; it also opens directly from disk.
GitHub Pages deploys the same files. The export script reads local evidence
without changing submitted snapshots. Raw workspaces, session transcripts,
credentials and exploratory experiments are not part of the publication.

The original container image IDs and local runtime prerequisites are documented
in [runtime/README.md](benchmark/v1/runtime/README.md); the images themselves are
not distributed with this source release.

Earlier design notes in `docs/0.1/` are historical, not the v1 contract.
This is an independent synthetic benchmark. Its accounting rules are policies of
the test application, not a claim of ASC 606 or IFRS 15 compliance.
