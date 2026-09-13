# Evaluation And Calibration

The evaluator owns deterministic expected results. No model judges financial
correctness, code quality or accounting intent. Analyst explanations accompany
scores but never determine them.

## Development Protocol

Start candidates from an infrastructure-only Elixir/Phoenix/PostgreSQL project
with Ecto, Decimal, Oban and a functioning HTTP client. No billing implementation,
accounting engine or predesigned domain schema is provided. The agent owns its
business architecture and carries its own code through all seven releases.
Several merchants with contrasting catalogs and charts use that same build.
Configure them through public APIs; do not hand candidates already expanded
invoices or separate code paths to implement per merchant.

Give one release at a time, with all earlier requests retained. Permit reading,
testing, debugging and final self-review. Keep private tests and later releases
outside the candidate checkout. A completed snapshot is immutable. Evaluation
can proceed asynchronously without stopping the agent from working on its next
release; private results are not returned to it.

Analyst repairs to an evaluator do not count as candidate improvements. A repair
that changes what a reasonable reading of the request requires is a requirements
revision, not permission to rescore old code under a newly invented contract.

## What Is Reported

Report four separate tracks; do not average them into a single percentage.

| Track | Proposed unit | Purpose |
|---|---|---|
| Economic correctness | 32 families, with every underlying case also reported | Does the configured product compute and preserve required commercial and financial meaning? |
| Continuity | 14 histories | Does actual earlier-version data survive the product changes? |
| Operator workflows | 7 end-to-end browser tasks | Can merchants configure and operate the product? |
| Execution integrity | 4 bounded integration checks | Are durable retries and external export effects correct? |

Family scoring is one point only when its cases pass. Always publish the raw
case numerator/denominator and failure stage too. Grouping cannot create difficulty
when all underlying cases pass. There is no assertion that this score has the
same difficulty scale as Sweat Bench v6 or any v7 iteration.

Runtime, cost, source size and sample count are descriptive metrics. They are not
quality points. Record accepted and interrupted inference work, and child-session
usage if delegation is enabled. Candidate instruction and harness settings must
be held constant within a comparison. Do not enable delegation as an unrecorded
intervention.

## Proposed Economic Families

The family inventory is stable enough for design review. Exact cases and schemas
must be frozen before the screen, after arithmetic and ambiguity review.

| IDs | Release | Family scopes |
|---|---:|---|
| B01-B04 | 1 | Catalog expansion/override provenance; multi-charge dates/calendars; flat/per-unit recurring economics; billing/receipt/service distinctions |
| B05-B08 | 2 | Source identity/completion; metric semantics; allowance/rating/cap composition; effective grouping and attribution |
| B09-B12 | 3 | Discount scope/stacking; fixed-discount redistribution; subscription proration/amendment; cancellation/renewal/version retention |
| B13-B16 | 4 | Relative SSP allocation; acceptance/progress evidence; billing ramps versus service patterns; independent arrangements and versions |
| B17-B20 | 5 | Face versus basis; funder/consumer/payer separation; eligibility/priority/expiry; minimum-spend residual |
| B21-B24 | 6 | Separate addition; prospective replacement; cumulative catch-up; concession versus refund |
| B25-B28 | 7 | Nonlocal corrections across charge/discount/funding; sequential corrections; gross effects after close; economic/accounting reconciliation |
| B29-B32 | 1, 4, 6, 7 | Tenant chart/hierarchy/segments; derivation and splits; configuration/reclassification history; correction routing and frozen export addresses |

Each case has one primary family, a cited requirement, independent expected
observables and a named incorrect approach it distinguishes. A test is not copied
into two tracks to award two discoveries. A history can independently exercise
the same rule on older data, but must be identified as such.

Release-one basics should not dominate the case count. Concentrate distinct
combinations in B05-B32, especially cases that cross configuration boundaries.
Extra random quantities within the
same arithmetic branch are robustness samples, not new semantic families.

### Configuration and composition coverage

Case K tests actual tenant-configured account codes, segment values, distributions
and rollups, not only translation into fixed economic categories. Cases L-N test
single-customer commercial complexity before pooling exists. Run valid alternate
configurations on the same candidate artifact, changing merchant/product names
and the assignment of features to merchants. Neither chart shape nor charge model
may be chosen by recognizing a fixture name.

Use a documented interaction matrix: charge model x allowance x discount scope;
calendar x quantity change x advance/arrears; discount x bundle allocation;
consumer/payer/funder x account derivation; configuration version x correction.
Pairwise coverage is a baseline, not a substitute for a few deep coupled cases.
An implementation passing each isolated feature may still mishandle their order
or scopes. More isolated feature checks alone would repeat the v7 weakness.

## Expected Values

Use small independent reference calculations, not a second production application:

- Exact rational allocation and cumulative rounding for SSP and recognition.
- Direct enumeration of the union of interval boundaries for peak concurrency.
- Whole-bucket calculation for graduated and volume pricing, followed by exact
  attribution. Never derive the expected total by summing candidate invoice lines.
- A small chronological table of grant consumption and basis release.
- Hand-derived subscription proration, discount attribution and revenue amendments.
- Independently resolve the supplied account rules and splits, then compare
  actual journals by account, segment, causal effect and configuration version.
- A fixed operation history for each coupled correction and explicit old/current
  expected views.

These are suitable for a Python reference package later; nothing requires an
Elixir gold business implementation. For a small set of anchors, calculate the
answer two ways, such as a handwritten journal table plus rational arithmetic.
Do not let the same implementation function generate fixtures and judge them.

Global conservation properties are additional checks, not sufficient oracles.
For example, total debits equaling credits says nothing about whether the right
customer, obligation or period was used. A balanced wrong-classification variant
must be rejected by Case J.

### Concrete sensitivity checks

Before running models, demonstrate that each of these wrong behaviors fails:

| Wrong behavior | Required distinguishing evidence |
|---|---|
| Recognize invoice display prices | Case A's zero-priced implementation earns allocated consideration |
| Recognize each daily rounded slice independently | Case B conserves the final cent across invocation schedules |
| Price each consumer separately | Case C finds changed pricing for the untouched consumer |
| Treat paid face as revenue | Case D releases consideration, including in the discounted bundle |
| Count the prepaid invoice and usage as two revenues | Case E reconciles one sale and its drawdown |
| Apply one amendment rule everywhere | Cases F/G differ in past and remaining revenue |
| Recognize a loss again on refund | Case H changes cash without another revenue reduction |
| Correct only the submitted record | Case I traces effects across funding, debtors and later consumption |
| Check only balanced journals or net revenue | Case J retains opposing classified effects |
| Treat queued export as acknowledged | Receiver state must show one actual accepted batch |
| Rename seven fixed accounts at export | Case K requires configured postings, splits and trial balances before export |
| Always use current chart or current catalog | Cases K/N retain the appropriate accounting and commercial versions |
| Multiply every charge by subscription quantity | Case L separates base fee, licensed quantity and measured usage |
| Collapse discounts into one percentage or duplicate a fixed budget | Case M distinguishes stacking and shared attribution |
| Bill new seats for the whole cycle | Case N has the known $45 incremental invoice |

These need not become a general mutation-testing framework. Targeted faulty
variants or controlled altered outputs are enough. The proof is a failing named
check for the intended reason, not a large count of manufactured mutants.

## Histories Without Huge Setup

Use twelve adjacent histories, two for each of six transitions, plus two lifetime
histories spanning releases 1-7 and 2-7. Each contains a small number of customers,
contracts and obligations with deliberately different dates and balances.

Historical state is created through the old application's public operations.
Persist its database, terminate the server, upgrade to the next snapshot and
continue through the public API. Never insert guessed candidate-specific SQL.
Retain saved documents, export identities and externally recorded expectations.

Observe separately: old-state setup, migration, first cold request, business
continuation and accounting reconciliation. If a migration fails, its later
accounting checks are unreached, not independently demonstrated accounting bugs.
Use separate clean-state semantic cases so the suite can still inspect those rules.

No 10,000-contract enrichment phase. A few dozen carefully chosen records can
expose wrong time, identity, allocation and correction semantics. Setup progress
and query times are recorded; investigate unexpectedly increasing setup costs
instead of waiting hours or silently relaxing the tested condition.

## Integration And Browser Coverage

Four execution checks: first retried mutation in a fresh server; competing
applications against one available balance; worker restart during export; lost
receiver acknowledgement followed by reconciliation. Include legitimate operations
that must succeed, and rejected operations whose balances must remain unchanged.
Do not make one transport defect the apparent cause of twenty independent
economic failures.

The seven browser tasks follow business work: configure a catalog/chart and sell
a multi-charge subscription; resolve and rate usage; discount/amend a subscription;
allocate a bundle and record acceptance; inspect shared funding and overage;
restructure/reclassify; correct and export settled history. Check observable
records, not visual resemblance to a
particular vendor. Customer visibility includes a sibling-data negative control.

## Ambiguity Review

Before a case is eligible for scoring, connect its first failing assertion to an
explicit requirement. Give a plausible alternative interpretation and show where
the requirement excludes it. If both readings remain reasonable, clarify the
request or accept both, rather than treating model disagreement as useful signal.

Review success cases too: could a no-op, empty result, company-wide net total or
hard-coded happy path pass? Use positive controls proving the setup reached the
intended state. A timeout, missing evidence or setup error has its own status.
Never infer successful downstream accounting from an exception caught as an
expected rejection.

## Calibration Decision

First screen one Astra low and one Astra xhigh trajectory. The point is task
selection, not estimating an effort ranking from two observations. Favor parallel
execution when resources permit; report contention and evaluator overhead apart
from active agent time.

After auditing unchanged snapshots, answer:

1. Are there genuine, independently specified economic failures, rather than
   ambiguity, setup errors or only one library-loading defect?
2. Which family of calculations defeated the implementation, and which successful
   trajectory shows a materially different correct approach?
3. Is there useful unsolved scope at the frontier, not merely more failures in
   Luna or a longer implementation?
4. Do the distinctions survive reasonable case variations and repeated runs?

Both Astra efforts passing everything is a saturation result. One isolated miss
is worth understanding, not an automatic license for a large campaign. Multiple
independent economic weaknesses or a consistent effort distinction justify
replication, but the screen alone does not establish consistency.

If the task is saturated, first check whether required behavior was actually
observed. Add justified diagnostic coverage to unchanged implementations. If
those also pass, revise the economic task or try another product domain; do not
remove self-testing, invent a shorter timeout, increase aggregation severity or
add thousands of similar records to manufacture a gap.
