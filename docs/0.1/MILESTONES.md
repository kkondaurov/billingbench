# Milestone Plan

Six successive releases of the same application. This is a design brief for the
future candidate requests, not an executable API specification. Candidates
receive the current release and retain earlier requirements, not the full
roadmap or evaluator design. Dates advance through business operations, not
wall-clock sleeps. Policy IDs refer to [requirements](REQUIREMENTS.md).

## 1. Sell And Account For Subscriptions

**Business request.** The vendor sells fixed-term access. Customers pay upfront
or in installments. Billing needs what is due; accounting needs what is earned.

Deliver customers, fixed-term contracts, flat recurring charges, installment
invoice schedules, immutable issued invoices, externally recorded payments,
explicit applications, daily recognition, journals, contract positions and
monthly close. One charge represents one stand-ready obligation. The operator
workspaces may initially be sections of one page. Customers read their invoices.

Signing, activation and billing dates are separate. An invoice does not activate
delayed service. An unpaid receivable does not stop recognition of delivered
service. Previewing or rerunning completed work must not duplicate effects.
Rules: ID, TIME, MONEY, DOC, SETTLE, REV, CLOSE.

**Acceptance anchors.** A $90 service over 90 days, paid upfront, earns $31 during
January in the specified non-leap-year example. Billing it later changes its
contract position, not earned revenue. Close January and retain the issued
invoice and posted entries.

**Carry forward:** partially recognized and not-yet-activated subscriptions;
an unpaid invoice; partially unapplied cash; a saved preview; a closed month.
The release-one application must create these records itself.

## 2. Negotiate Bundles, Not Just Invoice Lines

**Business request.** Sales negotiates a single price for platform access and
implementation. The invoice describes the deal; revenue tracks its promises.

Introduce versioned offerings expanded into contract components, performance
obligations, supplied standalone selling prices (SSPs), relative allocation,
ramped billing and delivery evidence. Recognize stand-ready service over time,
a distinct deliverable upon acceptance, and an indivisible implementation service
by approved cumulative progress. Missing evidence remains unknown, not complete.

**First pivot: one charge is no longer one obligation.** A displayed charge can
fund several obligations; several charges can share one allocation group. A
zero-priced implementation line can receive consideration. Old subscriptions
remain their original single-obligation arrangements, without reposting history.

Sales may replace an entirely unperformed bundle. Once service starts, changes
to its economic terms remain unavailable until release five. Catalog changes
apply to newly accepted terms only. This is an explicit capability boundary,
not a hidden expectation of future amendment behavior. Rules: CONTRACT, ALLOC, REV.

**Acceptance anchors.** Case A allocates a $10,000 sale into $8,000 of platform
and $2,000 of implementation consideration. Case B checks cent allocation. Two
contracts on one invoice remain separate arrangements. Changing installment
timing without changing service cannot change its recognition pattern.

**Carry forward:** partly satisfied bundles; missing acceptance; a progress
estimate; an issued ramp installment; future billings; all release-one history.

## 3. Bill Pooled Usage

**Business request.** Projects of one enterprise customer opt into a shared
compute tariff. Operations
supplies usage events, not pre-priced invoice lines. Correcting one project can
move the whole group into another volume band.

Add source-scoped event identities and revisions, dated project assignment,
metering definitions, pricing groups, flat/graduated/volume tariffs and attributed
invoice previews. Metering supports sum, distinct active identities and peak
concurrent seats from assignment intervals. No arbitrary SQL or custom language.

**Second pivot: a usage event is not independently billable.** Sum of individual
project peaks differs from peak simultaneous occupancy. Sum of distinct counts
differs from distinct count over the group. Pricing depends on records outside
the project being corrected.

In an unissued period, revised source facts replace their earlier revisions and
rerate the affected scope. Published-period correction remains explicitly
unavailable until release six. Ordinary later usage is still accepted. Callers
cannot supply an arithmetic invoice delta instead of the replacement fact.
Rules: USAGE, RATE, IMPACT.

**Acceptance anchors.** Case C changes charges by +$16 and -$22 after changing
only one consumer's usage. A second pair contrasts concurrent seat intervals
with equal per-project totals. An incomplete source prevents usage issuance; a
complete empty source produces zero usage.

**Carry forward:** revised events; duplicate identities; dated assignments; an
issued pooled invoice; an empty complete feed; an incomplete feed; prior bundles.

## 4. Sell Enterprise Commitments

**Business request.** A parent prepurchases compute for selected subsidiaries.
Other customers negotiate minimum spend instead. Some receive promotions.
Consumption, funding and payment responsibility must be tracked separately.

Add paid rights with face value, allocated consideration and access windows;
promotional rights with no paid basis; eligibility and priority; parent-funded
usage with child overages; and postpaid minimum-spend true-ups. Introduce dated
payer and access policies without changing old document ownership. Pricing-pool
membership is separate from funding eligibility. A consolidated statement is not
another sale or receivable.

**Third pivot: spending capacity is not revenue.** A bundle may allocate more
consideration to compute rights than the invoice labels as their charge. Consuming
the rights releases their allocated basis, not their face amount or display price.

Nonrefundable paid rights earn revenue through consumption, with unused basis
recognized at the end of availability. Promotional expiry earns nothing.
Minimum spend produces a residual charge, not a prepaid wallet. No rollover,
intercompany transfers or FX. Rules: FUND, MINIMUM, OWNERSHIP, ALLOC, REV.

**Acceptance anchors.** Case D sells $100 face for $80 and earns $40 when half
is used. Case E combines promotion, paid rights and overage. Case I has a shared
funding owner but two overage payers. Another bundle displays a $40 credit charge
while allocating $80 to it, preventing use of invoice price as cost basis.

**Carry forward:** partial consumption and recognized basis; expired rights;
unpaid prepayment invoices; parent/child invoices; an open minimum-spend period.
Include earlier-version customers, not only newly created hierarchical records.

## 5. Restructure Live Contracts

**Business request.** Deals change after billing and delivery. Some changes buy
independent service; some replace what remains; others change the scope and price
of one unfinished implementation project.

Add dated amendments, derived accounting treatment and impact previews. Support
separate additions at SSP, prospective replacement of remaining distinct promises
and cumulative remeasurement of a single ongoing promise. Policy determines
remaining consideration, remaining SSP and revised progress.

Add price concessions with explicit commercial scope: remaining promises or
the full sale in an allocation group. The amount and scope are inputs; journal
entries are not. A discount displayed on one line still affects the group's
relative revenue allocation.
The application derives debit/credit documents, future billings and recognition
effects. A cash refund remains a separate settlement operation.

**Fourth pivot: an old allocation is sometimes retained, sometimes replaced
prospectively and sometimes remeasured cumulatively.** One freeze-everything or
recalculate-everything rule cannot serve all three. Rules: AMEND, IMPACT, SETTLE,
CLOSE.

**Acceptance anchors.** Case F reduces revenue from $400 to $240 despite a higher
contract price. Case G preserves $600 earned and reallocates $700 of remaining
consideration. Case H distinguishes earned and unearned credits without another
revenue loss when cash is refunded. Amend a bundle containing paid rights: an
amendment cannot grant back already consumed rights.

**Carry forward:** multiple amendments; a proposal saved after an earlier
amendment; partial refunds; old receivables; a progress remeasurement; original
journals. A harmless serialization change cannot make an unchanged proposal stale.

## 6. Correct Settled History And Export Accounting

**Business request.** A usage provider corrects last month after customers pay
and finance closes. Operators need corrected bills and accounting, without losing
the historical record of what was issued, paid, earned and exported.

Permit historical usage revisions, withdrawals and corrections to erroneous
source assignment. Reconstruct affected rating and funding scopes under policies
effective for the service dates. Find every affected consumer and arrangement,
not just the customer on the changed source record. Derive adjustment documents
and current-period journal entries while preserving issued and posted history.

Expose traceability from source revision to charge, right drawdown, invoice item,
obligation and journal effect. Distinguish correction of an erroneous fact from a
newly negotiated amendment; they have different effective meaning. Both original
history and current corrected economics must be inspectable.

Add a deterministic local general-ledger receiver and acknowledged export batches.
Use Oban for delivery. Retries must not duplicate receiver acceptance. A timeout
is not a verdict: reconcile by stable batch identity. This is one integration,
not a bank or ERP implementation. Rules: IMPACT, CLOSE, EXPORT.

**Acceptance anchors.** Reuse Case I after payment and close, checking positive
and negative documents and earned paid basis. Zero-net changes must remain
visible by customer, obligation and category. Lose an export response, retry and
verify one receiver acceptance and unchanged financial records.

**Final histories:** adjacent upgrades plus databases spanning releases 1-6 and
2-6, preserving original documents and partly performed obligations throughout.
A final clean-database pass cannot replace the observed upgrade result.

## Sequencing Review

Pivots arrive in releases two, three and four, not one late conversion of an
object into several. Each changes which earlier concepts can be treated as
equivalent. Releases five and six apply different changes after effects exist.

The release count is not the hardness mechanism. Removing a screen would not
remove group repricing or recognition. Adding four administration releases would
not make those calculations deeper. [Evaluation plan](EVALUATION.md).
