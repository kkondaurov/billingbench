# Evaluator R4 Audit

The five-release requirements, scaffold and submitted implementations are
unchanged. R4 corrects evaluator assumptions exposed by the Sol 6.1 submissions
and checks those repairs against the other OpenAI and Claude Code submissions.
All diagnosis and scoring use disposable copies; no feedback repairs a candidate.

## False Negatives

**Covered billing links are not new invoices.** The [public API](candidate/0.5/01-api.md)
permits document links on covered scopes. The [foundation](candidate/0.5/01-foundation.md)
requires already-issued work to remain covered instead of being charged again.
The old fixture returned every linked document, then compared that collection
with the expected *new* invoices or credits. An implementation retaining links
to historical documents could fail despite creating the correct new documents.

R4 compares before/after document IDs and keeps existing drafts acted on by the
run. It rejects hidden new documents, dangling links, deleted old documents,
duplicate IDs and changed historical face facts. Mutable settlement balances
and extra response fields are not mistaken for immutable face values. Controls
also establish that a genuinely new duplicate charge still fails.

**Accounting projections may have a null customer.** The
[history contract](candidate/0.5/05-history.md) explicitly allows nullable
`ImpactRow.customer_id`. Sol 6.1 #3 uses null for aggregate account projections
and gives the correct debtor on billing rows. R4 permits null on aggregate and
recognition rows, rejects a wrong nonnull customer, and still requires the debtor
on billing rows. Its independent closed-sale expectations remain 10,000 old and
8,000 target minor units on receivable/revenue addresses.

## False-Positive Controls

- Document totals and item amounts must be integers. Python booleans and floats
  that compare equal to expected integers are no longer accepted as money.
- Billing/recognition economic preview rows, when present, must sum to the
  independent expected old/target amounts, even when their own deltas are
  internally consistent and their separate accounting-address rows look valid.
- Corrupt-response controls distinguish wrong debtors, wrong amounts, hidden
  invoices and rewritten history from valid response-layout differences.

These are demonstrated gaps under deliberate controls, not a claim that an
observed candidate previously earned points from every such gap.

## Qualification

The frozen evaluator passes 73 regression tests, including nine new tests with
positive and negative subcases. Recorded responses from all 13 final API suites
were considered for replay: 1,101 pass, 464 still fail, 21 require continuation
beyond the old failure, and 13 require real concurrent execution. Every previously
passing replayable case still passes. Replay does not replace live restart,
concurrency or retained-history evaluation.

All 65 submitted snapshot trees and 5,681 prior evidence-file hashes are checked
against frozen provenance receipts. The full live comparison uses the same R4
evaluator for five API snapshots and the final retained-history suite per run.
Raw evidence is retained privately; the release publishes per-case outcomes,
summary/source hashes, per-release measurements and sanitized application sources.

## Observed Final API Changes

Sol 6.1 #3 improves from 97 to 110 of 123. Twelve formerly failing scenarios
were blocked by historical document links; `closed-current-reconciliation` was
blocked by the nullable aggregate customer. Each now passes the complete live
scenario, including assertions after its former stopping point.

Luna #1 improves from 42 to 43 via `payer-policy-old-debt`. The other eleven
final API scores are unchanged. These corrections reduce measured implementation
variation for Sol 6.1 to 109-111; they are not candidate improvements.

The completed rescore covers 78 jobs and 5,018 scenario outcomes, without
evaluator exceptions. In earlier snapshots, Sol 6.1 #3 gains four R2 passes,
six R3 passes and nine R4 passes. Luna #1 gains one R3 and one R4 pass.
Retained histories improve from 6 to 16 of 20 for Sol 6.1 #3 and from 4 to 7
for Luna #1. All these changes trace to covered historical document links;
the complete live histories now pass beyond their old stopping points.
Other history totals are unchanged, and no previously passing scenario loses
its pass in the 78-job comparison. Original outputs remain preserved.

Four known ID-sensitive checks retain eight fresh-tenant repetitions, with any
failure making the scenario fail. Observed repeat counts can change between
rescoring batches: Sol 6 #2's successor-agreement check passes 2/8 now versus
6/8 before, but fails the scenario in both batches. Neither a lucky first
trial nor the best repetition is used as the score.

## Remaining Limits

The two previously disputed scenarios retain their original strict expectations:
offsetting documents for a zero-net termination, and rejection versus holding of
a correction into a closed month. Every run also has a /121 diagnostic excluding
both checks uniformly. No candidate gets a private interpretation exemption.

Missing required commercial response fields, wrong carried amounts, invalid
migrations, and invalid grouping of invoices by payer/currency remain failures.
The audit does not establish exhaustive economic validation of every preview or
the absence of undiscovered evaluator defects. Scenario pass counts measure
complete delivered workflows, not numbers of independent bugs.
