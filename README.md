# Billing Bench

A software-engineering benchmark in which coding agents build and evolve an
enterprise SaaS billing application, including revenue recognition and a
double-entry revenue subledger.

## Version 0.1

**Research and design proposal. Not an executable benchmark or a calibrated
measurement of model capability.**

The proposed product follows a sale from negotiated terms through usage, invoices,
payments, revenue recognition and subsequent corrections. Six milestones change
the commercial model while the application retains the records created by its
earlier versions. Candidates start from infrastructure, not an existing business
implementation, and may test and revise their work before delivery.

Start with the [proposal](docs/0.1/PROPOSAL.md).

| Document | Contents |
|---|---|
| [Proposal](docs/0.1/PROPOSAL.md) | Product, scope, difficulty hypothesis and recommended experiment |
| [Milestones](docs/0.1/MILESTONES.md) | Six releases, early pivots, retained history and acceptance examples |
| [Requirements](docs/0.1/REQUIREMENTS.md) | Identities, dates, pricing, funding, amendments and API capabilities |
| [Accounting](docs/0.1/ACCOUNTING.md) | Explicit accounting policies and independently checkable worked examples |
| [Evaluation](docs/0.1/EVALUATION.md) | Deterministic scoring, coverage, historical evaluation and calibration |
| [Design review](docs/0.1/DESIGN_REVIEW.md) | Evidence from Sweat Bench and SlopCodeBench; attacks on this proposal |
| [Research](docs/0.1/RESEARCH.md) | Primary documentation, API findings and deliberate vendor differences |

Research reviewed on 13 September 2026. Billing Bench is an independent synthetic
benchmark, not affiliated with Zuora, Metronome or Stripe. Its accounting policies
define a bounded test application; they are not a claim of ASC 606 or IFRS 15
compliance.
