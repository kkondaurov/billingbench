# Proposed Product Requirements

This is the economic contract for design review. A later implementation step must
turn these capabilities into exact request/response schemas. Hidden tests may
vary documented inputs and their combinations, not invent additional conventions.
The policies below are Billing Bench choices, not universal vendor behavior or
accounting advice. [Worked calculations and postings](ACCOUNTING.md).

Read the [charge and document lifecycle](LIFECYCLE.md) alongside these rules.
Billing, settlement and recognition are related branches over the same records,
not one status or a sequence in which payment must precede earning.

## ID: Identities And Ownership

Keep these concepts distinct in externally observable behavior. Storage tables
and module boundaries are the candidate's choice.

| Concept | Meaning |
|---|---|
| Tenant | One merchant using the platform, with its own configuration and isolated books |
| Product / rate plan | Tenant-defined catalog item and reusable combination of charges |
| Subscription | A customer's accepted selection of plans, quantities, terms and dated changes |
| Charge | One configured calculation, quantity source, trigger and billing schedule |
| Customer | A purchasing business; may have a parent |
| Consumer/project | The business or project using the service |
| Contract | Accepted commercial terms and their dated amendments |
| Pricing group | The exact set over which a metric and tariff are calculated |
| Funding grant | Paid or promotional rights with an owner and eligible consumers |
| Invoice payer | Customer liable for a particular charge |
| Revenue arrangement | The consideration-allocation boundary defined by a sale |
| Obligation | A distinct promise, or explicitly grouped indivisible promise |
| Source event | An identified fact, with revisions; not its import batch or invoice |
| Billing coverage | The part of a charge/window's economics represented by active posted billing results |
| Bill run | A tenant-scoped sweep that selects due work and generates billing documents |
| Billing result | Related documents and signed coverage changes produced for one complete calculation scope |
| Credit/debit memo | A separately posted reduction/increase, with item-level origin and purpose |
| Application | Use of an identified receipt or credit balance to settle an identified receivable |

An invoice can contain several arrangements. It does not merge them. A shared
grant belongs to its selling arrangement even when another customer's usage
consumes it. An import batch does not define consumer identity or pricing scope.

All money has a currency. Contracts, grants, payment applications and allocation
groups are single-currency. An operation crossing tenants or currencies is
rejected atomically. Version 0.1 has no currency conversion or intercompany ledger.

Business identities survive upgrades. Names can change without changing identity.
Candidate-generated opaque IDs are accepted; tests follow returned relationships
rather than guessing IDs or inspecting internal storage.

Any ID used to break an economic ordering tie below is an immutable,
caller-supplied business key, not a candidate-generated storage ID. Keys compare
lexicographically; version numbers compare numerically. The API must distinguish
these keys from opaque resource IDs.

## TIME: Effective, Recorded And Posted Time

- Service and eligibility windows are **start-inclusive, end-exclusive**. Use
  explicit `starts_on` and `ends_before`, never an ambiguous `expires_on` field.
- Daily accounting uses UTC dates and actual calendar days. Accounting months
  are calendar months; commercial billing periods follow configured anchors and
  need not align with accounting months. An end date is never a day of service.
- Usage timestamps and seat intervals are RFC 3339 UTC instants. Simultaneous
  interval ends are excluded before starts are counted. No local-time/DST policy.
- `effective_at` identifies when a fact or negotiated term applies. `recorded_at`
  is when the application accepted it. `posting_date` identifies the accounting
  period receiving an effect. These must not be substituted for one another.
- The benchmark supplies an explicit business date for posting and runs; it does
  not depend on today's real date. Posted dates must be in an open period.
- A newly negotiated amendment is effective no earlier than its acceptance date
  in 0.1. A correction can fix an earlier erroneous event or mapping. Calling a
  price renegotiation a correction is not supported.

Calendar comparisons must reflect calendar order. Tests span year and month
boundaries, but the domain is not designed around a particular language trap.

## MONEY: Precision And Rounding

Money in documents and journals is integer minor units. Quantities, unit prices
and SSP inputs use nonnegative decimal strings with up to six decimal places.
Intermediate calculations retain exact decimal/rational precision. Negative
effects arise through defined corrections, not negative source consumption.

Round a scalar monetary result to the nearest cent, ties away from zero. When
allocating an already rounded nonnegative total, use largest remainders: floor
each exact share, then assign remaining cents in descending fractional-remainder
order, breaking ties by stable business component ID. Compute a negative
allocation from the positive magnitude and negate it. Do not round every event
and then sum it. These are test conventions supplied to candidates, not unstated
expectations.

For straight-line revenue, cumulative earned amount is the rounded allocated
amount times elapsed eligible days divided by total eligible days. A day's release
is the difference between cumulative targets on successive days. Splitting a run
into daily or monthly invocations must not change cumulative recognized cents.

## CATALOG: A Platform For Merchant-Defined Products

Tenants define products and versioned reusable rate plans containing multiple
charges and discounts. A subscription selects one or more plans and may override
permitted fields. Product IDs, charge IDs, merchant IDs and human names never
select built-in merchant behavior. Resolve explicit subscription overrides before
plan values before tenant defaults, retaining the chosen version and provenance.
Publishing a new default changes neither accepted subscriptions nor old previews.

Charge type and price model are separate. One-time charges support flat/per-unit
prices; recurring charges support flat/per-unit and, from release two,
graduated/volume prices on licensed quantities. Usage charges support per-unit,
included-unit overage, graduated/volume and a tier table with an overage tail.
These are implemented model families with tenant-supplied parameters, not supplied
answers. A plan can combine a base fee, seats and metered overage.

Charge configuration includes currency, quantity source and unit, rates/bands,
included units, optional minimum/maximum charge, cadence, trigger, effective
window and discount eligibility. Prices quote an explicit full billing period;
an annual price is not implicitly a monthly price multiplied by twelve. Optional
price lookup tables select parameter sets from declared product/customer
attributes with explicit priority and fallback, not arbitrary executable code.
Snapshot the selected commercial parameters when accepting the relevant version.

## SUB: Subscription Dates, Billing And Ordinary Amendments

Subscriptions may be termed or evergreen. Term boundaries do not imply billing
boundaries. A termed subscription has explicit renewal length and policy; an
evergreen subscription has no invented infinite transaction price. Forecasts
require a finite through-date. A business-date operation processes due renewals
idempotently; real-time scheduling is not required for the benchmark.

Each charge chooses its billing trigger: contract effective, service activation,
customer acceptance or a specified date. Missing trigger evidence holds that
charge, not silently supplies the signing date. Recognition uses its separate
service condition. Support monthly, quarterly and annual periods anchored to
service start, a chosen calendar day or month end. A short month clips the chosen
day for that occurrence, then restores the original anchor; January 31 does not
permanently become the 28th. Advance and arrears change invoice timing, not earned
service. Metered charges are billed in arrears after source completion.

Version 0.1 uses actual-day proration for recurring service. Within each full
anchored period, split at charge activation/end and quantity/price changes;
calculate each segment's full-period price times its active days divided by days
in that full period. Sum exact results before MONEY rounding. Do not reset the
denominator at an amendment. Usage charges separately select `none` or
`actual_day_amount` proration, resolved from the charge/tenant configuration and
retained in accepted terms. `none` charges the rated actual usage. The latter
multiplies the bounded rated amount for an effective segment by its active days
divided by days in the full anchored period, before discounts. It does not scale
source quantities. Allowance proration is a separate choice under ALLOW.

From release three, dated orders can add/remove plans, update charge quantity or
negotiated price, cancel and renew. A future change must not alter earlier service.
Changes to issued advance bills produce bill-run invoices or credit memos;
cancellation credits unused recurring service under the same price and discount
rules, not the latest catalog rate. One-time delivered charges are not refunded
by ordinary cancellation. A paid credit and an unpaid credit follow SETTLE, not
one cash rule.

Renewal explicitly retains negotiated pricing or adopts a selected catalog version
captured when renewal is accepted. Several actions in one order have an explicit
order and are atomic. Reject conflicting versions rather than partially applying
an order. A quantity amendment does not reset discount duration or allowances.
Ordinary subscription changes are available before multi-obligation revenue
restructuring; AMEND governs the latter once those arrangements exist.

## CONTRACT: Commercial Terms

An accepted contract retains its offering version, components, currency,
activation condition, service windows, installment schedule and allocation inputs.
Catalog changes never alter accepted terms by themselves. A draft has no financial
effect. Drafts can be changed before acceptance. SUB governs ordinary live
subscription changes from release three; multi-obligation restructuring uses
release-six AMEND rules.

Signing, activation and customer acceptance are separate facts. Scheduled billing
may occur before service activation; recognition follows the obligation's actual
service condition. Contract term and installment dates do not silently extend
when an activation is delayed: accepted terms explicitly give the service window.

Every invoice schedule amount represents consideration, not a second sale on top
of the contract. Fixed transaction price is the sum of accepted fixed charges
after commercial discounts, once, not the sum of its schedule plus its invoices.
Usage and minimum-spend charges add their separately determined consideration.
Ramped installments need not follow service effort. Before release four, each
stand-ready charge/cycle is its own revenue unit; finite bundled arrangements
then use ALLOC. Evergreen future renewals do not create infinite allocated revenue.

## ALLOW: Included Units And Rating Order

Included licensed units reduce the contracted quantity used in the recurring
price calculation: billable seats are `max(licensed - included, 0)` for each
effective segment. An included usage allowance instead belongs to an identified
charge/scope/window and is consumed by eligible actual events. It is not granted
again per import, invoice retry or subscription amendment.

An allowance may be fixed for a period or actual-day prorated for a partial active
period, as configured. Quantity allowances retain exact fractional quantities;
money rounding is not quantity rounding. Unused units expire at the window end;
unit rollover is excluded from 0.1. Mid-window allowance changes contribute their
configured day-weighted amounts rather than restart a full allowance. Corrected
usage reconstructs consumption in service-time/business-key order.

Apply included units before pricing the remainder. Graduated/volume bands use
that remaining billable quantity in 0.1. Apply optional charge min/max bounds
after rating, then any configured usage-amount proration, then commercial
discounts, then monetary funding, then postpaid minimum-spend residuals. A
configured minimum charge can apply to a complete zero
usage period for an active charge; without that minimum, zero usage costs zero.
For recurring quantities, compute the full-period bounded price before time
proration. These charge bounds are neither grant balances nor minimum commitments.
Usage-amount proration and allowance proration may both apply when configured;
neither is inferred merely from a partial service window. Keep the original
measured units, allowance units, rated amount and prorated amount observable.

## DISCOUNT: Scope, Basis And Duration

Discounts are reusable catalog/configuration records with explicit eligible
charge/product/plan/subscription/customer scope, currency, effective window and
priority. A discount can exclude setup or prepaid purchases while applying to
recurring charges or overage. It cannot cross tenants, currencies or unrelated
customer ownership simply because charges share a billing run.

Support percentage groups and fixed amounts. A percentage group selects either
sequential application to the remainder or additive percentages on the group's
common incoming basis, capped at that basis. Groups execute in explicit order.
Fixed discounts follow percentage groups and consume at most the eligible
remaining amount; they never make a charge negative. A fixed amount spanning
several eligible components is allocated in proportion to their remaining charges
using MONEY, not duplicated on every line. Preserve each discount's attribution.

Every fixed budget has its own explicit billing window, shared across all eligible
components in that window, not per API request or invoice ID. Resolve the complete
eligible scope before issuing affected discounted charges; mixed schedules with
unknown usage can therefore hold that scope until the inputs are complete.
Unused discount budget expires; it is not refundable customer funds or a grant.
Percentage windows select eligible service components; fixed-budget partial-window
proration is an explicit configured choice. Exact window boundaries are retained.

Introductory duration counts from the discount's original configured start/window,
not from the most recent amendment. Recompute retained discounts after a change
to price, quantity or scope; altering one charge can redistribute a fixed discount
on another. The resulting net consideration feeds billing and revenue allocation.
Account routing may display gross revenue and discount effects separately, but
their reconciled economic consideration is net, not two different sales.

## ALLOC: Allocate Consideration, Not Display Prices

A revenue arrangement contains allocation groups and their obligations. In 0.1,
each fixed-price group allocates its complete transaction price in proportion to
the supplied extended SSP of every eligible obligation. Extended SSP already
incorporates the purchased quantity and service term. No estimation or judgment
of SSP from market data is required.

A missing or nonpositive required SSP puts the proposed arrangement on hold;
it does not become zero. An explicitly free promotion is a separate zero-basis
grant, not an obligation with missing SSP. Invoice display prices cannot override
allocation. Multiple invoices for one arrangement do not repeat allocation.

All fixed consideration participates in its declared group. There are no selective
discount-allocation exceptions in 0.1. Metered on-demand consideration is allocated
directly to the corresponding usage obligation under the benchmark's explicit
policy. Paid capacity sold in a bundle is an obligation in the fixed allocation
group; its revenue basis is the resulting allocation, not its displayed price.

## REV: Recognition

Four recognition bases are supported:

| Basis | Recognition condition |
|---|---|
| Stand-ready | Ratable over activated service days in the fixed window |
| Acceptance | Entire allocation when the specified deliverable is accepted |
| Progress | Allocated amount times approved cumulative completed units / approved total units |
| Paid capacity | Allocated basis released by consumption of the grant's face value; unused nonrefundable basis released on expiry |

On-demand usage earns its rated, unfunded amount in the service period. Promotional
coverage earns zero. Usage funded by paid capacity earns the capacity basis, not
an additional on-demand amount. Do not recognize the same usage from both the
invoice and the drawdown ledger.

Progress observations distinguish unknown, explicit zero and a positive amount.
Each active progress obligation requires an approved observation as of month end
or its earlier completion date before that month's recognition can complete.
An unchanged cumulative amount must be explicitly confirmed; an older observation
is not evidence that no further work occurred. Completed units cannot exceed the
approved total, and a changed estimate follows AMEND rather than ordinary progress.
An acceptance awaiting evidence remains outstanding. An operator cannot declare
revenue earned merely by closing a period or paying an invoice. Recognition runs
produce posted effects and updated schedules; querying a schedule has no effects.
See the accounting document for configured postings and amendment calculations.

## USAGE: Interpret Source Facts

Use `(tenant, source, event_id)` as the identity and an increasing revision for
replacement. Retrying an identical revision is a no-op; sending a different
payload for that revision is a conflict. An accepted higher revision wholly
replaces the earlier fact for current economic calculations; a held proposal
does not replace it. Withdrawal is an explicit revised state. Identical IDs
from different sources remain different facts.

Project aliases resolve through a source-scoped, effective-dated assignment.
An import's current owner is not a substitute for assignment at the event time.
An unresolved or multiply matched assignment is an exception, not silently
dropped usage. A manifest identifies required sources and period completion.
Invoice issuance requires completion through the period end and no unresolved
events in scope. A complete feed with zero events is valid. Revision of a
completed feed is supported; completion does not assert the data can never change.

Metrics are versioned selections of event type and declared dimensions, with
exact equality filters and one aggregation: sum, distinct identity count, or
peak simultaneous occupied seats from half-open assignment intervals. For peak,
count distinct seat identities across the group's union of intervals. Overlapping
observations of one seat do not create two seats. Its consumer attribution is
the seat's dated assignment. No arbitrary expressions, scripts or parser DSL.

Metric versions and dated assignments are retained. Ordinary edits affect future
windows; a correction to an erroneous historical assignment is a separately
identified operation with an old/new preview from release seven onward.

From release two, source revisions can replace unbilled usage, including usage
made billable again by explicit document reversal. Revisions intersecting active
posted coverage require the historical impact operation introduced in release
seven; until then return a specific hold and retain the active revision. This
does not prevent ordinary invoice-linked memos or reversal/rebilling. A document
reversal changes billing coverage, not the usage facts or their revision numbers.
Once released, that scope can be revised and billed at the corrected amount.
Recognition reconciles any resulting change to previously earned usage in an
open period, even if the original service period closed. Check the whole affected
scope for other active posted coverage, not only the submitted event's invoice.

## RATE: Group Before Pricing

Pooling is opt-in under accepted commercial terms, initially between projects
of one customer and, from release five, selected subsidiaries of an enterprise.
Parent ownership or shared funding alone does not pool prices. Without an
explicit shared-pricing agreement, one customer's usage cannot change another's
rate. All members must belong to the same enterprise customer group.

A pricing bucket is `(tenant, currency, pricing_group, metric_version, product,
tariff_version, billing_period, effective_segment)`. Segment boundaries are the
union of effective tariff and pricing-membership changes inside the period.
Tier counters reset at these boundaries. Funding availability does not split or
reset pricing buckets. The scope and counter-reset policy are explicit inputs.

Tariffs support per-unit, included-unit overage, graduated tiers (each slice at
its tier rate), volume tiers (one rate for all units), and a finite graduated
table followed by an explicit per-unit overage tail. Bands use exclusive upper
bounds; a quantity exactly at a boundary enters the next band. A zero quantity
costs zero before any configured minimum; fixed access fees are separate contract
components in 0.1, not undocumented band fees. RATE receives billable quantities
after ALLOW. DISCOUNT and FUND consume the resulting attributed charges in order.

Apply ALLOW before monetary attribution: consumed included units carry no rated
charge, and contributions below are the remaining billable quantities. For sum
metrics, each consumer/day contributes its quantity. For distinct metrics,
each identity contributes once, at its earliest retained observation in the
bucket, attributed to its consumer assignment then; conflicting simultaneous
assignments are exceptions. For peak metrics, attribute the seats present at the
earliest instant reaching the peak to that instant's consumers and service day.
Apply rating, bounds and the configured usage-amount proration to the bucket
before rounding its pre-discount amount once. Allocate that amount to consumer/day
contributions in proportion to their quantities using MONEY; ties use
`(consumer_id, service_date)`. Retain that attribution even when one payer receives
a consolidated document.

Revising one event requires rerating every affected bucket. Changing a volume
band can reduce total price or increase another customer's share. No monotonic
assumption and no pricing each removed unit at its original unit rate.

## FUND: Paid Rights And Promotions

Each grant has face value in currency minor units, a remaining face balance,
an owner, eligible consumers/products, an access window and an explicit integer
priority. A paid grant also has allocated consideration and released basis.
A promotion has zero consideration. Paid grants are available on their accepted
access schedule even if their invoice is unpaid; failed collection is not
revocation of sold rights. Payment-gated access is outside 0.1.

Apply eligible grants in ascending `(priority, ends_before, grant_id)` order.
This ordering applies across paid and promotional grants. It is not Metronome's
full prioritization scheme. Within a service day, process rounded charge
attributions in the lexicographic order of RATE's business-key bucket tuple,
then `consumer_id`. Do not order by generated database IDs.
Across days process service dates first. Eligibility uses the contribution's
service date from RATE, not ingestion, invoicing or correction date. Consequently
later usage can change an earlier day's allocated charge in a volume-priced
bucket, requiring its funding to be recalculated too.

One face cent covers one cent of rated charge. Split at grant exhaustion; the
rest is overage. Paid-basis release after cumulative consumption `x` of face `F`
is `round(allocated_basis * x / F)`. A drawdown releases the change in that
cumulative amount. At expiry release the remaining basis, without another
invoice or cash receipt. Promotions expire with no revenue posting.

For revised economics, reconstruct consumption in the specified order across
all affected grants and subsequent uses. Freeing capacity can displace a later
overage or consumption of another grant. Original drawdowns remain historical;
net corrections are linked to them. Recomputed rights can never cross the
original access window merely because a correction was recorded later.

## MINIMUM: Postpaid Minimum Spend

A minimum-spend agreement specifies a window, eligible products and amount M.
Its qualifying spend S is the sum of eligible on-demand overage charges after
promotional and prepaid coverage, excluding fixed fees, prepaid purchases and
other true-ups. The residual charge is `max(0, M - S)` at the window end.

There is no spendable balance for a minimum commitment. Its residual earns revenue
at the window end under the explicit nonrefundable minimum policy. A revision
to S recalculates the residual as well as usage. Two countervailing changes must
not disappear merely because total revenue stays the same. Overlapping minimum
agreements on the same product/consumer/window are rejected in 0.1.

## OWNERSHIP: Separate Sharing From Payment

From release five, a parent can grant selected children access to its rights.
Children can retain individual overage liability or designate their parent as
payer. Pricing pools are specified separately and may cross those funding scopes.
Invoice consolidation is permitted only for one payer, currency and billing run,
within the tenant's configured grouping policy under BILL.
It preserves source child, contract and arrangement on every component.

New payer/access terms affect future effective segments only. An issued invoice
retains its debtor. A correction to a historical charge follows the payer policy
of that charge, not today's parent. A replacement contract does not inherit an
old receivable unless an explicit permitted settlement application links them;
0.1 does not include legal novation or automatic balance transfer between debtors.

## BILL: Bill Runs And Billing Coverage

An operator creates an ad hoc run for all accounts of one tenant or an explicit
account subset. A saved daily/weekly/monthly schedule creates the same operation
when processed against an explicit business date. No wall-clock waiting is needed.
The run retains its selection, target date, invoice date and posting date.
The target date includes charges whose `billable_on` date is at or before it;
it is not a substitute for service dates. Advance recurring amounts are billable
on period start; arrears on period end; one-time amounts on their resolved trigger;
scheduled installments on their schedule date. Usage also requires completed
sources. The invoice date labels the document; posting uses an open period.

Resolve accepted subscriptions, calendars and complete calculation scopes before
generating documents. A target inside an arrears period does not prematurely
bill that incomplete period. Tenant configuration groups invoices by payer or
by payer/subscription, always within one currency. Preserve source charges,
service periods, consumers and arrangements under either grouping. Scheduled
installments and metered results cannot create a second sale of prepaid rights.

Preview is read-only. Generation freezes a selection and creates drafts with
basis versions; it creates no receivable or journal. Posting revalidates the
relevant basis. Changed terms, source facts or competing posted coverage make
that draft stale; unrelated activity does not. Cancellation releases a draft's
reservation, if used. Reservations are not posted billing coverage.
Validate the required posting configuration before committing the billing result.
Its documents, coverage and billing journals are accepted atomically; an accounting
hold cannot leave half a result posted. Recognition remains a separate operation.

A run exposes eligible, held, drafted and posted scopes and their documents.
Independent scopes can succeed while another is held. Shared pricing/discount
calculations must include their whole required scope: a selected-account run
holds a scope requiring omitted accounts rather than silently billing those
accounts or computing a partial shared discount. Related positive/negative
documents form one atomic billing result. Retry completes held/unfinished work
within the saved selection, not work already posted; newly discovered charges
outside that selection require a new run. Resolving evidence for an already held
charge is a continuation within the original selection. Implementations need not
use parallel workers.

Billing coverage identifies charge, service/calculation scope and the signed
amount already documented, with links to every contributing result. A retry
with a new run ID must still find already billed work. Usage is not consumed
again by issuing a new document: preserve event/metric/charge attribution rather
than a global event-level billed flag. A completed zero-priced scope is covered
without requiring a nonzero invoice; zero net does not hide opposing components.

For ordinary bill runs, positive new amounts and positive amendment differences
generate invoice items; negative amendment differences generate credit memo
items linked to the earlier billed components. Keep positive and negative
documents separate even when their combined total is zero. Release-seven impact
corrections instead use linked debit/credit memos for changes to already billed
components. Their origin differs; both update the same coverage accounting.

## DOC: Invoices, Credit Memos And Debit Memos

Each document has its own identity, date, payer, currency, status, item breakdown
and origin. Credit/debit memo items link to the affected original items and
commercial components. Amounts are nonnegative magnitudes with direction supplied
by document kind. Billing-result and reversal links survive aggregation and
rounding. A document is draft, posted or cancelled; only drafts can be cancelled.
Issuing means posting. Posted contents never change, even in an open period;
settlement balance and reversal/compensation flags are separate from that status.

Ordinary invoice-linked credit and debit memos exist from release one. An
operator-issued memo records an explicit signed commercial adjustment and reason
against selected charge/service components, without reversing the invoice. On a
single revenue unit this changes its consideration and recognition target under
REV; later bundles use AMEND's full-sale or remaining-only treatment. The memo
and its commercial adjustment are accepted together. They must not be counted
again as an unbilled price difference by the next bill run. A credit cannot reduce
the affected consideration below zero. Debit memos create additional receivables.

Generated memos carry a different purpose: an amendment/source correction
documents an already accepted economic change, whereas a billing reversal only
undoes document coverage. Neither creates a second commercial adjustment. An
arbitrary reason string does not select accounting treatment; the operation type
and structured commercial facts do. Bad-debt write-offs and standalone memos
unrelated to a subscription charge are outside 0.1.

The original invoice stays posted after a partial or full ordinary credit memo.
Its service remains billed, and its raw usage is not returned to pending billing.
A full credit is therefore not synonymous with invoice reversal. Gross attribution
must survive a zero net correction across items, debtors or arrangements.

## REVERSE: Document Reversal And Rebilling

Reversal previews the complete related billing result and settlement prerequisites.
For an invoice-only result it generates a full matching credit memo, applies that
credit to clear the invoice and marks the original posted invoice reversed.
Release the result's billing coverage so a later run can bill it again. For a
bill-run credit memo, generate the opposite debit memo, apply the credit to it
and release that signed adjustment for regeneration. If one billing result
contains both positive and negative documents, reverse them together; do not
leave half of a shared calculation covered. This is a bounded Billing Bench
policy, not all of Zuora's invoice/memo reversal restrictions.

Unapply existing payment/credit applications before reversal; an operation with
unresolved applications is rejected without partial changes. Available credit
must cover a credit memo being reversed: a refunded balance cannot be silently
recreated. Active later adjustment documents referencing a result must be
neutralized first, in reverse dependency order. Preview identifies those documents;
it does not silently refund money or reverse unrelated account history.

An operator-issued commercial memo is neutralized by a linked opposite memo,
undoing its stated commercial adjustment, not by releasing usage for rebilling.
This compensation is distinct from reversing a bill-generated credit result.
It also requires existing applications removed and an unrefunded credit balance.
Record the opposite documents' settlement and the compensated original explicitly.
An already reversed/compensated effect cannot be applied a second time.

Rebill creates new documents linked to released coverage and the reversed result.
It uses the applicable accepted facts, including permitted corrections, not
today's catalog defaults. With unchanged economics, it recreates the same net
charge. With a cancellation still present, reversing its generated credit memo
and rerunning produces a new credit memo, not a new full-period charge.

Pure billing reversal changes net billed amounts and the corresponding contract
position, but not contracted consideration, delivery, source usage, allowance or
grant consumption, or cumulative earned revenue. Rebilling does not issue another
grant or recognize the same service again. A separate source correction or
amendment can change those economic quantities through its own rules.

Original documents and closed journals remain. Reversal posts on a supplied open
date and offsets the result's accepted accounting distribution under ACCT; it
does not reverse unrelated recognition entries. Subsequent rebilling has its own
posting/configuration provenance. No reopening or unposting is required.

## SETTLE: Cash, Credit Applications And Refunds

Cash receipts and credit memo balances are separate sources, even if a customer
statement combines them. Record applications against invoices or debit memos
with source identity, item attribution, amount and date. Receive/apply/unapply
operations never rewrite the original receipt or document. Do not substitute
prepaid service rights for settlement credit.

For 0.1, posting an invoice-linked credit memo applies it to that invoice's open
receivable first; excess becomes available customer credit. A fully paid invoice
leaves the whole credit available. Generated reversal memos instead use the exact
offsetting application required by REVERSE. These applications remain observable
even when posting and application are one transaction.

Record actual cash separately from its applications. Operators select further
applications of available cash/credit to an eligible receivable; there is no
optimal matching problem. Reject overapplication, cross-debtor and cross-currency
applications. Unapplication restores the original source balance and receivable;
it is not a cash refund or cancellation of a concession.

Refund only available cash-backed funds. A credit offsetting unpaid service is
not refundable merely because its application was undone: it retains that
restriction and can settle debt, not create withdrawable cash. Track the paid
and unpaid portions of invoice-linked credits and their subsequent applications;
refunds consume eligible balances once. Reject reversal/compensation of a memo
whose required balance has already been refunded. Actual refunds are not erased
to make a document operation succeed. Refund reduces cash and the available
balance without another consideration or recognition adjustment.

## AMEND: Change Accepted Terms

Classify each amendment from structured commercial facts using this precedence:

1. **Separate addition:** only new distinct services are added, no old promise is
   changed, and their incremental price equals supplied extended SSP. Create a
   separate arrangement; original allocation and recognition remain unchanged.
2. **Prospective replacement:** remaining services are distinct from delivered
   services and no indivisible ongoing obligation is changed. Carry unearned
   consideration plus the signed price change into replacement obligations,
   allocating by their supplied remaining extended SSP. Previously earned revenue
   remains. Outstanding invoices and actual cash do not define the carry amount.
3. **Cumulative catch-up:** the changed allocation group contains one existing
   indivisible progress obligation. Recompute its price and progress with the approved new
   total units; the difference from cumulative earned revenue is posted now.

Mixed amendments requiring more than one treatment in the same request are
rejected in 0.1 and can be represented as explicitly ordered separate amendments.
Missing distinctness/SSP/progress facts produce a hold. No guessed legal judgment.
The allowed order matters; amendments are not assumed to commute.

A prospective replacement of unused paid rights carries only their unearned
allocated basis and their remaining face rights. Sold new face rights must be
explicit in the amendment. It cannot recreate the original full face balance.
A price-only concession identifies an allocation group and either its full sale
or remaining promises. A full-sale concession reduces that group's consideration
and reallocates it using the original relative SSPs; recompute each obligation's
earned target at its own completion fraction. A discount displayed on one invoice
line is not a selective revenue-allocation exception. A remaining-only concession
reduces the unearned pool and follows prospective allocation, preserving earned
revenue. Neither the revised total nor the remaining pool may be negative.
The concession also identifies the commercial components whose billed or future
charges change; this billing attribution does not override group allocation.

## IMPACT: Discover Consequences

An impact preview accepts a source revision, mapping correction, proposed terms
or concession, not the expected affected invoices or journal amounts. Return the
affected pricing buckets, consumers, grants, documents, arrangements, obligations
and signed changes. Recheck its relevant basis when accepting it. This late
operation discovers effects across settled history; it extends the existing
bill-run, memo and reversal lifecycles rather than replacing them.

Reconstruct current economic targets using effective facts, then compare with
already accepted documents and posted effects by business dimension. Do not diff
only company-wide totals or only records named in the input. Repeating the same
accepted revision has no additional effect. An old revision cannot undo a newer
accepted correction.

## ACCT: Tenant-Configured Accounting

The tenant is the billing platform's customer, not an invoice recipient. Each
tenant owns a chart, its reporting hierarchy, segment definitions and accounting
rules. Configuration is supplied through the product, not source edits or an
enumeration of supported customer charts.

### Chart and dimensions

- Define account codes, names, classifications, parent groups, posting eligibility
  and effective status. Codes carry no implicit meaning from their spelling.
  Group accounts roll up their descendants; they are not additional postings.
- Define a variable set of named dimensions, their allowed values and hierarchies,
  and which dimensions are required for each posting account. An address is an
  account plus its segment values, not a fixed three-part string.
- Allow many accounts for one economic function and one account for several
  functions. Product, department, region and business line may be account
  distinctions or segments. Economic provenance survives either representation.
- No fixed chart size, hierarchy depth or dimension names form part of the
  business model. Published execution limits may bound a test, but must not
  restrict tenants to built-in layouts. Cyclic hierarchies and invalid referenced
  values are rejected. One seller per tenant remains the 0.1 boundary.

### Derive postings from configuration

Rules select accounts and segments from the kind of economic effect and its
declared context: product, obligation kind, contract attributes, payment method,
and explicitly named consumer, payer or funding-owner attributes. A parent being
the payer does not silently supply every dimension of a child's earned revenue.
Resolve constants, context fields and tenant-maintained lookup tables. Conditions
use structured equality/membership and all/any combinations; ordered priorities
make precedence explicit. A fallback exists only if configured.

A selected rule may distribute a posting leg across multiple account/segment
addresses using supplied percentage weights totaling 100%. Split the already
computed amount with MONEY, with ties by immutable split-component key. Both
sides must retain equal totals. Reporting splits do not change SSP allocation,
customer balances, grant consumption or the amount earned. These are different
calculations even if a particular example uses the same percentages.

The rule vocabulary must cover the economic effects in this proposal, including
cash, receivables, held customer funds, recognition and corrections. It also
supports separate contract-asset and deferred-revenue postings from the changes
in `max(earned - billed, 0)` and `max(billed - earned, 0)` per arrangement, as well
as a configured net-position clearing account. There is no compulsory
`contract_control` GL account. The amount/sign semantics stay explicit; customers
configure their accounting destinations and distribution, not whether money was
received or a service earned. Exact context fields and selectors belong in the
public API specification; unavailable fields cannot be guessed by hidden tests.

Missing required data, unmatched rules, equal-priority conflicting matches,
invalid splits or an unavailable new-posting account put the affected accounting
operation on hold with a traceable explanation. Do not post a partial unbalanced
result or silently use a generic revenue/suspense account. Rule traces identify
the context, matched rule, lookup and split that selected each address.

### Configuration and historical changes

Published configurations are immutable versions with effective dates. Normal
new effects use the version effective on their posting date. Store the selected
version and resolved addresses with each effect; a current lookup must not
rewrite old journals, closed reports or exported batches.

Tenants explicitly select a correction-routing policy: use the original effect's
configuration, or the configuration effective on the correction's posting date.
In either case, compute the corrected economic amount and compare its configured
distribution with the last accepted distribution. Reverse removed amounts at
their actual old addresses and post replacement amounts at the resolved target
addresses. A linked delta is sufficient where old and new addresses coincide.
Reversal of an old posting remains possible after its account is retired; new
activity must use an eligible account. Original-configuration correction targets
remain eligible for that historical scope, not for unrelated new activity.

Changing configuration alone does not move existing balances. An explicit
reclassification selects an existing economic scope and target configuration,
previews the account/segment differences, and posts them in an open period without
changing billing or earned amounts. Later corrections compare with this latest
accepted distribution; they cannot reverse a stale pre-reclassification balance.
Reclassification makes its target configuration the scope's retained routing
baseline for subsequent original-configuration corrections. It does not alter
the literal configuration provenance recorded on older journal entries.
The selected correction policy and configuration versions are retained as evidence.

Trial balances and account rollups use the tenant's chart. Economic reconciliation
uses the underlying business effects; journal/export checks use the actual
configured accounts and segments. Supporting a complex chart only in display or
export does not satisfy configured posting and reporting.

## CLOSE And EXPORT: Accounting History

Posted entries are immutable even in an open period; repairs append linked
reversals or adjustments. Closing a month freezes its journal population and
report. Closing requires recognition completed through month end and no known
unresolved source/evidence or accounting-configuration exception affecting
required postings. Every accepted billing and settlement effect dated in the
month must be accounted for. Future
unsatisfied obligations do not prevent closing an earlier month.

A missing progress report required for that period is an exception; an explicitly
approved zero is valid. A not-yet-accepted point-in-time deliverable remains
outstanding but does not itself block period close. This distinction must be
publicly specified, not inferred by the evaluator.

Later corrections post on the supplied current open business date, recording
their original economic dates separately. No reopening in 0.1. This is benchmark
policy, not a universal accounting prohibition. Closed results and current
corrected economics are separate views.

Exports select posted entries not already assigned to a batch. Membership and
payload are immutable; each entry belongs to at most one batch. A local receiver
accepts `(tenant, batch_id, payload_digest)` idempotently. Acceptance with a lost
response is recovered by lookup, not a new batch. Later corrections enter later
batches. Receiver acknowledgement does not create or recognize revenue.
Exports retain the posted account codes, segment values and configuration
provenance. They are not remapped using whatever chart is current on retry.

## Proposed API Capabilities

This is a capability inventory, not a mandate to implement vendor endpoint names.

| Surface | Mutations | Required reads |
|---|---|---|
| Tenant catalog | Define products, plans, charges, price tables, discounts and defaults; publish versions | Effective catalog; configuration provenance; supported parameter schema |
| Subscriptions | Accept selected plans/overrides; add/remove/change/cancel/renew | Dated charge segments; price/discount breakdown; billing forecast; order impact |
| Commercial | Accept contract; record activation/acceptance/progress; preview/accept amendment | Terms and history; obligations; allocation; impact |
| Sources | Ingest revisions; complete source window; define dated assignment | Exceptions; source revisions; affected consumers |
| Pricing/funding | Publish future tariff; accept grant and eligibility terms | Metered quantities; attributed charges; grant face/basis history |
| Bill runs | Define/process schedule; preview, generate, post, cancel drafts and retry account sweeps | Selection and dates; held/completed scopes; documents; charge-level billing coverage |
| Documents | Create/post invoice-linked credit/debit memo; compensate memo; preview/reverse billing result; rebill | Frozen originals/items; reasons; related results; reversal/replacement chains; receivables |
| Historical corrections | Preview/accept source or recorded-term correction | Affected charge/discount/funding/recognition scopes; resulting memos and journals |
| Settlement | Record cash; apply/unapply cash or memo credit; refund | Applications by source/destination; refundable versus restricted balances; cash history |
| Accounting configuration | Define accounts, hierarchies and segments; publish routing/split rules; preview/accept reclassification | Versioned chart; rule traces; account/segment impact; holds |
| Accounting | Run recognition; close; request/reconcile export | Schedules; journal; trial balance; contract positions; export status |

Mutations use stable idempotency identities and atomic validation. Proposed roles
are commercial operator, billing operator, revenue operator and customer reader,
with an explicit operation matrix in the later API specification. Authentication
plumbing is scaffolded; account and data visibility remain application work.

## Before Candidate Requests Are Frozen

The next implementation step must specify endpoint paths, exact schemas, error
codes, pagination, limits, role permissions and the public local-receiver protocol.
Those are intentionally not invented test expectations in this proposal. Economic
policy changes during that step must update the examples and requirements
together. Candidates see only the policies applicable to their current release.
