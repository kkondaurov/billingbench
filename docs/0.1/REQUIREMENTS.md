# Proposed Product Requirements

This is the economic contract for design review. A later implementation step must
turn these capabilities into exact request/response schemas. Hidden tests may
vary documented inputs and their combinations, not invent additional conventions.
The policies below are Billing Bench choices, not universal vendor behavior or
accounting advice. [Worked calculations and postings](ACCOUNTING.md).

## ID: Identities And Ownership

Keep these concepts distinct in externally observable behavior. Storage tables
and module boundaries are the candidate's choice.

| Concept | Meaning |
|---|---|
| Tenant | One SaaS seller and its isolated books |
| Customer | A purchasing business; may have a parent |
| Consumer/project | The business or project using the service |
| Contract | Accepted commercial terms and their dated amendments |
| Pricing group | The exact set over which a metric and tariff are calculated |
| Funding grant | Paid or promotional rights with an owner and eligible consumers |
| Invoice payer | Customer liable for a particular charge |
| Revenue arrangement | The consideration-allocation boundary defined by a sale |
| Obligation | A distinct promise, or explicitly grouped indivisible promise |
| Source event | An identified fact, with revisions; not its import batch or invoice |

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
- Daily accounting uses UTC dates and actual calendar days. Monthly periods
  are calendar months. A service end date is never a day of service.
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

## CONTRACT: Commercial Terms

An accepted contract retains its offering version, components, currency,
activation condition, service windows, installment schedule and allocation inputs.
Catalog changes never alter accepted terms by themselves. A draft has no financial
effect. An entirely unperformed draft/replacement can be changed freely before
acceptance under release two; performed arrangements require release-five rules.

Signing, activation and customer acceptance are separate facts. Scheduled billing
may occur before service activation; recognition follows the obligation's actual
service condition. Contract term and installment dates do not silently extend
when an activation is delayed: accepted terms explicitly give the service window.

Every invoice schedule amount is a part of the accepted transaction price, not
another consideration amount. Fixed transaction price equals the sum of its
installment charges. Usage and minimum-spend charges add the amounts determined
by their separate rules. Ramped installment amounts need not follow service effort.

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
See the accounting document for control accounts and amendment calculations.

## USAGE: Interpret Source Facts

Use `(tenant, source, event_id)` as the identity and an increasing revision for
replacement. Retrying an identical revision is a no-op; sending a different
payload for that revision is a conflict. A higher revision wholly replaces the
earlier fact for current economic calculations. Withdrawal is an explicit revised
state. Identical IDs from different sources remain different facts.

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
identified operation with an old/new preview from release six onward.

## RATE: Group Before Pricing

Pooling is opt-in under accepted commercial terms, initially between projects
of one customer and, from release four, selected subsidiaries of an enterprise.
Parent ownership or shared funding alone does not pool prices. Without an
explicit shared-pricing agreement, one customer's usage cannot change another's
rate. All members must belong to the same enterprise customer group.

A pricing bucket is `(tenant, currency, pricing_group, metric_version, product,
tariff_version, billing_period, effective_segment)`. Segment boundaries are the
union of effective tariff and pricing-membership changes inside the period.
Tier counters reset at these boundaries. Funding availability does not split or
reset pricing buckets. The scope and counter-reset policy are explicit inputs.

Tariffs support flat per-unit, graduated tiers (each slice at its tier rate), and
volume tiers (one selected rate for all units). Bands use declared exclusive upper
bounds; a quantity exactly at a boundary enters the next band. A zero quantity
costs zero even when a band includes a fixed fee; fixed access fees are separate
contract components in 0.1.

For sum metrics, each consumer/day contributes its quantity. For distinct metrics,
each identity contributes once, at its earliest retained observation in the
bucket, attributed to its consumer assignment then; conflicting simultaneous
assignments are exceptions. For peak metrics, attribute the seats present at the
earliest instant reaching the peak to that instant's consumers and service day.
The bucket total is priced first, rounded once, then allocated to consumer/day
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

From release four, a parent can grant selected children access to its rights.
Children can retain individual overage liability or designate their parent as
payer. Pricing pools are specified separately and may cross those funding scopes.
Invoice consolidation is permitted only for one payer, currency and billing run.
It preserves source child, contract and arrangement on every component.

New payer/access terms affect future effective segments only. An issued invoice
retains its debtor. A correction to a historical charge follows the payer policy
of that charge, not today's parent. A replacement contract does not inherit an
old receivable unless an explicit permitted settlement application links them;
0.1 does not include legal novation or automatic balance transfer between debtors.

## DOC And SETTLE: Invoices, Credits And Cash

Preview is read-only. Issuing an invoice freezes its content and creates a
receivable. An issue request based on changed relevant terms is rejected as stale
with a new preview available. Unrelated customer activity does not invalidate it.
Posted invoices are not edited or silently regenerated.

A correction emits signed component differences: positive debit items and
negative credit items, each linked to original documents or unbilled commercial
components. Gross attribution must survive a zero net total. A credit against
an unpaid invoice reduces its receivable first. Excess over its open receivable
becomes customer funds; a fully paid invoice's credit becomes customer funds.

Record actual cash separately from where it is applied. Receipt increases cash
and customer funds. Applying available funds reduces funds and an eligible
receivable. Operators specify payment applications; there is no optimal matching
problem. Reject overapplication, cross-debtor and cross-currency applications.
Refund only available customer funds, reducing cash and funds without a second
revenue adjustment. Commercial concessions and cash refunds are not synonyms.

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
and signed changes. Recheck its relevant basis when accepting it.

Reconstruct current economic targets using effective facts, then compare with
already accepted documents and posted effects by business dimension. Do not diff
only company-wide totals or only records named in the input. Repeating the same
accepted revision has no additional effect. An old revision cannot undo a newer
accepted correction.

## CLOSE And EXPORT: Accounting History

Posted entries are immutable even in an open period; repairs append linked
reversals or adjustments. Closing a month freezes its journal population and
report. Closing requires recognition completed through month end and no known
unresolved source/evidence exception affecting required recognition. Future
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

## Proposed API Capabilities

This is a capability inventory, not a mandate to implement vendor endpoint names.

| Surface | Mutations | Required reads |
|---|---|---|
| Commercial | Accept contract; record activation/acceptance/progress; preview/accept amendment | Terms and history; obligations; allocation; impact |
| Sources | Ingest revisions; complete source window; define dated assignment | Exceptions; source revisions; affected consumers |
| Pricing/funding | Publish future tariff; accept grant and eligibility terms | Metered quantities; attributed charges; grant face/basis history |
| Billing | Preview/issue run; accept correction | Original invoices; debit/credit items; current receivables |
| Settlement | Record cash; apply/unapply; refund | Applications; available funds; cash history |
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
