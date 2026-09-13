# From A Subscription Charge To Settled And Accounted History

Billing Bench follows the same commercial records through their entire life.
The lifecycle below organizes the requirements; it does not prescribe tables,
modules or a queue topology. Policy details belong in [requirements](REQUIREMENTS.md)
and numerical examples in [accounting](ACCOUNTING.md).

## The Forward Path And Its Branches

```text
Tenant catalog, defaults and accounting configuration
  -> customer subscription: accepted plans, charge versions and dates
  -> activation, licensed quantities, usage and delivery evidence
  -> service-period charge calculations
       allowance -> rating/bounds -> configured proration -> discounts
       -> funding -> minimum-spend residual
       |
       +-> billing eligibility -> bill run -> draft invoices / credit memos
       |     -> posting -> receivables and available credits
       |     -> payment/credit applications -> refunds where eligible
       |
       +-> arrangement consideration -> allocation to promises
             -> delivery/consumption -> recognition

Posted billing, settlement and recognition effects
  -> tenant-configured journals -> period close -> acknowledged GL export
```

The sequence shown is the usage path; recurring charges use their own price and
proration rules, and one-time fees need neither metering nor a recurring allowance.
The branches are not consecutive stages of one status field. Service can be
earned before billing. An invoice can be paid before service starts. A document
can be reversed while the subscription and its delivered service remain valid.
The prepaid purchase and the usage it funds are linked sales/consumption records,
not two copies of revenue. Issuing another document must not sell the rights again.

## Follow One Charge

| Stage | What creates or changes it | What it produces or enables | What must remain identifiable |
|---|---|---|---|
| Catalog charge | Merchant publishes a plan with prices, quantity source, triggers and calendar | Reusable commercial offer | Product, charge and catalog version |
| Subscribed charge | Operator accepts a plan and permitted overrides for a customer | Accepted terms and scheduled service/billing windows | Subscription charge identity, resolved values and their origins |
| Effective segments | Activation, acceptance, quantity change, renewal or cancellation | Applicable terms for each part of a service period | Original terms and dated changes; no replacement with only current values |
| Source evidence | Usage import/revision, delivery acceptance or approved progress | Measured quantities or evidence of performance | Source identity, revision, service date and completeness |
| Economic calculation | Applicable terms and complete evidence | Rated charge, discounts, grant consumption, overage and consideration | Calculation scope and basis, including other charges that affect it |
| Billing eligibility | Due date and economic amount compared with active billed coverage | Unbilled amounts or adjustments available to a bill run | Charge, service window, billed amount and the documents covering it |
| Bill run | Tenant-wide or selected-account sweep through a target date | Reviewed draft documents, held scopes and retryable outcomes | Run scope/dates and source-to-item relationships |
| Posted document | Operator posts a current draft | Invoice/debit receivable or credit-memo balance; billing coverage | Frozen items, basis, reason, payer and original/replacement links |
| Settlement | Receive, apply, unapply or refund | Open debt, available cash/credit and payment history | Individual receipt, memo and application identities |
| Recognition | Terms/allocation plus service, acceptance, progress or consumption | Earned amounts and remaining schedules | Arrangement/obligation, evidence and previous recognized amounts |
| Journal and close | Business effects routed by tenant rules; explicit month close | Posted entries, trial balance and frozen report | Economic date, posting date, actual accounts and configuration version |
| Export | Select posted entries, send, reconcile acknowledgement | Accepted external batch | Immutable membership and payload, including after retry |

One rated scope can generate several payer documents. One invoice can contain
several charges and arrangements. One source event can contribute to more than
one contracted metric. Therefore neither invoice ID nor a single global usage
`billed` flag can stand in for all of these relationships.

## State Belongs To The Right Object

- A subscription is accepted, active or ended according to its terms and triggers;
  an unpaid invoice does not silently cancel it.
- A calculation can be incomplete, ready, represented by a draft, or covered by
  posted documents. Reversing coverage does not delete its source evidence.
- A bill run records generation and posting outcomes separately. It may finish
  with some scopes held; retry does not regenerate successfully posted scopes.
- An invoice, credit memo or debit memo is draft, posted or cancelled. Only a
  draft can be cancelled. Reversal/compensation is recorded against a posted
  original, not a transition that erases it. There is no unposting in 0.1.
- Open, partly settled and fully settled are balances of a posted document,
  not replacements for its posting status.
- Recognition, period close and export acknowledgement each have their own
  progress. None is implied by successful billing or payment.

## Changes Travel Back Through Different Parts Of The Lifecycle

| Operation | What it changes | What it does not do |
|---|---|---|
| Cancel a draft | Discards an unposted proposal; releases its draft reservation | Create AR, a credit memo, a refund or revenue |
| Credit/debit memo for a commercial adjustment | Records a linked decrease/increase in consideration and billing, with the corresponding recognition treatment | Reverse the original invoice or make its usage unbilled |
| Reverse an invoice | Posts a full offsetting credit memo, marks the original reversed and releases its billing coverage | Cancel the subscription, delete usage, refund cash or undo earned service |
| Reverse a bill-run credit result | Posts the opposite debit and releases the signed billing adjustment for regeneration | Undo the cancellation or amendment that originally caused the credit |
| Compensate an operator-issued memo | Offsets that memo and its stated commercial adjustment | Reopen the original charge's usage for billing |
| Rebill | Generates new documents for released coverage under applicable accepted facts | Resurrect the old invoice or grant another allowance/prepaid entitlement |
| Amend/cancel a subscription | Changes future service segments and produces the appropriate prorated charges or credits | Rewrite earlier delivered service or automatically return cash |
| Revise source facts | Changes the economic calculation and all affected later consequences | Treat the whole old invoice as wrong or necessarily require full reversal |
| Refund | Returns an eligible available balance as cash | Create another concession or recognize the same reduction again |
| Reclassify accounting | Moves the accepted balance to configured accounts/segments | Change the price, payer, service, payment or source usage |

Billing-result reversal and commercial correction are deliberately separate.
Rebilling unchanged facts should recreate the same economic charge. A concession
should leave that charge's service covered and its net consideration reduced.
The [BILL, DOC, REVERSE and SETTLE rules](REQUIREMENTS.md#bill-bill-runs-and-billing-coverage)
specify settlement prerequisites and the boundary of a related document group.

## End-To-End Histories

These histories are small enough to inspect without bulk load setup. Each checks
the documents and the other branch of the lifecycle, not only the last balance.

### A paid usage invoice is reversed and billed again

Ten actual units at $10 produce a $100 invoice through a bill run. The merchant
receives and applies $100; the service earns $100 and its month closes. In the
next open month, unapply the payment and reverse the invoice. Its linked $100
credit memo clears it, while the receipt remains available and the usage becomes
eligible for billing again. Earned service remains $100. Until rebilling, that
earned amount is unbilled. A new bill run creates a new $100 invoice; applying
the existing receipt clears it. No new cash, usage, entitlement or revenue appears.
[Worked case O](ACCOUNTING.md#o-memos-reversal-and-rebilling-have-different-effects).

### A concession uses a memo without unbilling the service

On a separate $100 invoice, grant a $20 full-service concession. Its credit memo
reduces the unpaid receivable to $80, or leaves $20 of credit if the invoice was
already paid. The original stays posted and not reversed. The charge remains
billed; running billing again does not reclaim the concession. Recognition uses
the revised $80 consideration under the service's completion rule. Refund and
memo compensation remain separate operations.

### A cancellation creates a negative bill-run result

A $100 April advance charge is posted. Cancellation effective April 16 leaves
15 of 30 service days, so the next bill run produces a $50 credit memo. The
original April invoice remains posted. Reversing that generated credit produces
an offsetting debit memo and releases the $50 adjustment, not the whole $100
charge. Rerunning billing with the cancellation still present generates a new
$50 credit memo. April's final consideration and earned service remain $50.

### A corrected fact reaches several documents

Use the pooled usage, shared grant and separate payers in Case I. A revision
changes price for both consumers, funding, overage and earned basis. Accepting
the impact creates the required linked credit/debit memos and current-period
journals, without reversing unaffected invoices or changing recorded cash.
Repeat after one memo is settled and the accounting configuration has changed.
The next adjustment is relative to accepted history, not the initial invoice.

## Milestone Placement

Release one delivers the complete basic path: subscription, bill run, documents,
ordinary memos, reversal/rebilling, settlement, recognition and close. Release
two carries usage through those operations and adds configurable usage proration.
Release three makes amendments and discounts generate billing adjustments.

Releases four through six change allocation, rights and contract/accounting
treatments over the same records. Release seven adds automatic historical impact
discovery across those scopes and the GL export receiver. It does not introduce
credit/debit memos or basic correction handling for the first time.

For every later requirement, review its entry into this lifecycle, the records
it reads, the outputs it changes and its effect on existing posted/settled history.
If an output has no creating operation, or a reversal has no defined continuation,
the requirement is incomplete. This is a design review method, not a requirement
to implement every neighboring feature of a commercial billing suite.
