# Billing Bench 0.1: Proposal

13 September 2026. Proposed requirements, not an implemented or calibrated suite.

## Recommendation

Build a billing platform for a fictional SaaS vendor selling software access,
implementation services and metered compute. Its customers range from individual
businesses to enterprise groups purchasing negotiated bundles and shared usage
commitments. The platform manages their contracts, calculates charges, issues
invoices, allocates payments and credits, recognizes revenue and exports journals.

Use **six releases**. Introduce negotiated bundles in release two, pooled metering
in three, enterprise commitments in four, contract restructuring in five and
cross-period corrections in six. Basic revenue recognition and accounting close
exist in release one. Later releases therefore change a financial system with
real history, rather than add accounting to an otherwise finished product.

The central difficulty hypothesis is **maintaining several different economic
interpretations of the same transaction, and recomputing their consequences when
one input changes**. An invoice amount is not necessarily revenue. Spendable
credit is not necessarily cash or deferred revenue. An invoice payer is not
necessarily the consumer, the owner of a commitment or the grouping used for
revenue allocation. A correction to one consumer's usage can change another
consumer's price without changing that second consumer's usage at all, but only
under an explicit shared-pricing agreement. Unrelated customers are never pooled.

These distinctions are commercially motivated and produce exact, testable
answers. They are not evidence that Astra will fail. That question requires a
screen of Astra low and xhigh before a larger campaign.

## What The Documentation Contributes

Zuora Billing supplies the commercial lifecycle: subscriptions, dated order
actions, separate subscription and invoice ownership, settlement and credit
memos. Zuora Revenue supplies a different layer: performance obligations,
standalone selling prices, allocation, modification treatments and journal
transfer. These are related products, not interchangeable APIs.
[Order API](https://developer.zuora.com/v1-api-reference/api/orders/post_order),
[revenue treatments](https://docs.zuora.com/en/zuora-revenue/advanced-revenue-operations/contract-modifications/accounting-treatments),
[journal transfer](https://developer.zuora.com/other-api/revenue/transfer-accounting).

Metronome separates metering, rating, commitment consumption and invoicing. Its
documented discounts distinguish spendable face value from what the customer
pays. Its hierarchy model separates access to a shared commitment from
responsibility for overages.
[Commit discounts](https://docs.metronome.com/guides/pricing-packaging/apply-credits-and-commits/discounting-on-commits),
[account hierarchies](https://docs.metronome.com/guides/pricing-packaging/billing-model-guides/model-hierarchical-customer-relationships).

Metronome explicitly does **not** create revenue journal entries; its data supports
downstream accounting. Billing Bench's revenue engine is a deliberate addition,
not an assumed Metronome feature. Stripe completed its acquisition of Metronome
on 14 January 2026, but the reviewed documentation still exposes distinct product
and API surfaces.
[Revenue data](https://docs.metronome.com/guides/reporting-insights/financial-reporting/revenue-recognition),
[acquisition announcement](https://stripe.com/newsroom/news/stripe-completes-metronome-acquisition).

The [research notes](RESEARCH.md) distinguish vendor behavior from the proposed
synthetic rules. Billing Bench does not copy every vendor default for proration,
credit ordering, corrections or revenue recovery.

## The Product People Use

The fictional vendor sells access to an analytics platform, metered compute and
implementation services. Enterprise sales can bundle them, discount them,
pre-sell compute rights and change the deal after service starts.

Three operator workspaces share the same business records:

- **Commercial operations:** customers, contracts, amendments and an impact
  preview showing what changes in billing and revenue.
- **Billing operations:** usage exceptions, invoice previews, issued documents,
  payments, available customer funds, credit notes and refunds.
- **Revenue accounting:** obligations, allocation and recognition schedules,
  posted journals, contract positions, period close and export status.

A customer read view shows issued invoices and the customer's own usage and
credits. It must not expose sibling usage simply because invoices share a payer.
These are working views, not a marketing site, general CRM or full ERP. Most
evaluation exercises the public API; selected browser workflows establish that
the same operations are usable through the product.

## Six Releases

| Release | Business change | Earlier shortcut it invalidates |
|---|---|---|
| 1. Sell and account for subscriptions | Fixed terms, installments, payments, daily recognition and close | Cash received, billed amount and earned revenue cannot be one balance |
| 2. Negotiate bundles | One price buys multiple obligations; ramped billing, acceptance and progress-based services | An invoice line cannot be the universal unit of revenue |
| 3. Bill pooled usage | Raw events, shared tier scopes, volume pricing and revised usage | Independently pricing each event or consumer no longer gives the answer |
| 4. Sell enterprise commitments | Paid and promotional rights, minimum spend, selective sharing and separate payers | Face value, consideration, consumption, ownership and invoicing no longer coincide |
| 5. Restructure live contracts | Separate additions, prospective replacement and cumulative catch-up | Neither freezing all old allocations nor rerating the whole past is always correct |
| 6. Correct settled history | Late source corrections, settlement consequences, accounting and acknowledged exports | A local adjustment to the changed record or net balance is insufficient |

Each release has a commercial story, a change in calculation, surviving old
records and observable consequences. [Full milestone plan](MILESTONES.md).

## Where The Extra Difficulty Comes From

### Calculations change other calculations

Two subsidiaries have agreed to pool usage for an enterprise volume discount;
each pays its attributed charge. They use 80 and 40 units. At 120 total units a volume tariff
charges $0.80 for every unit: $64 and $32. A correction reduces the second
consumer to 10 units. At 90 total units the price is $1: charges become $80 and
$10. The first consumer owes **$16 more despite no change to its usage**. The
group's bill falls only $6, not the $24 obtained by pricing removed units at the
old rate.

This is all-units volume pricing, not graduated tiers: crossing the threshold
changes the rate for every unit in the pool. Separate customer tariffs would
not create this cross-customer effect.

Now let those charges consume a shared discounted commitment, with overages
invoiced to individual consumers. The correction also changes who used the
commitment, which customer needs a debit or credit and how much consideration
was earned from the paid rights. Closed journals and received money remain facts;
they cannot be overwritten to match a newly calculated state.
[Worked cases C and I](ACCOUNTING.md).

### The grouping changes with the question

Usage is grouped for pricing. Rights are grouped for funding. Invoices are grouped
by payer. Consideration is allocated within a revenue arrangement. None of these
groupings implicitly defines another. A consolidated invoice can contain several
arrangements; a shared paid right can fund several consumers while its revenue
remains attributable to the arrangement that sold the right.

This is more specific than increasing relationships in a schema. Tests must
include facts for which using the wrong grouping changes the answer. Creating
five IDs that always refer to the same group would add no useful pressure.

### Similar changes require different treatment

Adding independently priced distinct service leaves the original allocation
alone. Replacing remaining distinct services reallocates only the remaining
consideration. Changing an ongoing indivisible implementation obligation
remeasures cumulative earned revenue and may require a negative catch-up.
The application derives the treatment from explicit commercial facts and
benchmark policy, not from an accountant-provided journal entry.

The engineering task is not interpreting accounting law. Standalone selling
prices, whether services are distinct and approved progress estimates are inputs.
Calculation, affected-record discovery, version selection and postings are the
application's work. [Accounting policy](ACCOUNTING.md).

## Why This Is Not Yet A Difficulty Result

Astra already handled nested definitions, shared funding, selective corrections,
transactions and immutable history in Sweat Bench. The Service Packages screen
passed **183/183 business cases and 14/14 histories at both low and xhigh**.
Those strengths remain relevant here. Event histories, decimals, locks and
recomputation are legitimate solutions, not loopholes to prohibit.

The new hypothesis is that different grouping scopes, nonlinear rating,
consideration allocation and remeasurement create enough coupled semantic cases
to expose mistakes after the agent's own testing. An implementation can still
solve all of them with a clear economic model. If Astra low does that, this
design has failed to establish frontier headroom, however professional the
resulting application looks.

The [design review](DESIGN_REVIEW.md) maps each bet to prior evidence, attacks
shallow implementations and identifies the parts likely to remain easy. Domain
terminology and the number of accounting concepts are not difficulty evidence.

## Scope And Boundaries

Use Elixir, Phoenix, PostgreSQL, Ecto, Decimal and Oban in an infrastructure-only
skeleton. Include a supported HTTP client and working runtime configuration.
Candidates choose business modules, storage and abstractions. Standard libraries
are encouraged; do not ask models to rebuild queues, decimals or CSV parsers.
No vendor SDK supplies the business implementation, and no live vendor account
is needed.

Version 0.1 includes fixed and ramped fees, bounded metering and tariffs,
negotiated terms, paid and promotional rights, minimum-spend true-ups, revenue
allocation, three amendment treatments, settlement, corrections and a subledger.
It excludes taxation, FX, intercompany accounting, commissions, arbitrary pricing
code, SSP estimation, statutory disclosures, collections optimization and
bank-network integration.

Multiple tenants and separate currencies are isolation boundaries; amounts never
move across them. Each tenant represents one seller. Enterprise customer groups
are not multiple seller legal entities. These exclusions keep the work centered
on economic semantics rather than every feature a commercial suite offers.

There is no 10,000-order historical setup or performance score in 0.1. Measure
ordinary evaluation setup and query times so an accidental quadratic fixture is
visible, without turning measurement infrastructure into another benchmark.

## Implementation And Calibration Proposal

1. Agree on this design, especially its bounded accounting policy. Then produce
   six candidate requests and exact API schemas. Neither is implemented here.
2. Implement the economic checks and infrastructure for those requests. Validate
   worked examples independently and show that concrete wrong implementations
   fail for the intended reason. Do not build a second complete enterprise
   application merely to serve as an oracle.
3. Run one complete six-release trajectory each for **Astra low and Astra xhigh**,
   in parallel. Preserve self-testing, final review and earlier requirements.
   Do not return private evaluator feedback to candidates.
4. Audit failures and sampled successes on unchanged snapshots. Repair defective
   tests and reevaluate both. A substantive requirement change needs a fresh
   affected development attempt, not retroactive scoring of the old one.
5. If useful semantic headroom appears, add two runs per effort and then Sol
   xhigh and Luna xhigh. If saturated, distinguish missing test coverage from
   insufficient requirements before buying more samples.

There is no runtime forecast from endpoint counts. Record active agent time,
inference usage including delegated sessions if enabled, evaluator time and setup
time separately. Scope is bounded; unhealthy execution can be stopped and
diagnosed rather than called a functional failure because ten minutes elapsed.

Promotion to version 1.0 requires stable requirements, a verified evaluator and
repeatable useful measurement. A 0.1 screen is an experiment in task selection.

## Decision

Proceed with six releases, not a feature-complete Zuora clone. The most important
tests combine **group repricing, paid-right consideration and revenue remeasurement
after settlement**. Calibrate those demands before adding adjacent enterprise
features. A larger platform is justified only if its extra rules create
distinctions the smaller one cannot measure.
