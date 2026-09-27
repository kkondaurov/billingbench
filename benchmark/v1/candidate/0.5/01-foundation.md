# 1. Bill, Settle And Recognize

Build a multi-tenant SaaS billing application on the supplied Elixir, Phoenix,
PostgreSQL and Oban infrastructure. A tenant is a selling merchant; its customers
buy subscriptions and negotiated bundles. Implement the public API, migrations
and your own tests. No operator UI is required. Choose your own storage and domain
architecture. This is a bounded product policy, not statutory accounting advice.
Taxes, FX, banks, dunning and intercompany accounting are outside scope.

## Dates, Identity And Money

Isolate tenants, including when their business keys match. Customers, products,
invoice debtors have explicit identities; a parent link
alone changes neither ownership nor permission. USD and EUR have 100 minor units.
No cross-currency settlement. Dates are UTC; windows include starts_on and exclude
ends_before. A through date includes that day. Recorded time, service date,
invoice label date and posting date are distinct. Use supplied business time,
not waits for the wall clock. Posted entries require an open posting month.

Use exact decimal rates and quantities. Round scalar money to nearest minor unit,
ties away from zero. Allocate a rounded total by flooring nonnegative exact
shares, then assigning remaining cents by descending remainder, ties by source
business key, not generated IDs or insertion order. Distribute negatives by
negating the positive allocation. Recognition posts differences of rounded
cumulative targets, so processing frequency cannot change total earnings.

## Sell Service

Publish reusable catalogs with explicitly priced charges. Subscription overrides
are limited to fields marked overridable. Acceptance retains the selected options,
attributes and catalog version. Later catalog/profile changes do not renegotiate
accepted service or invalidate unrelated drafts. No price-lookup hierarchy,
automatic renewal or evergreen contract is required.

Subscriptions have finite terms and monthly periods anchored at service start or
an explicit day of month. Clip a nonexistent day for that month and restore the
chosen anchor next month. Recurring charges are flat or per-unit, the latter
charging max(quantity-included,0). Sum exact segment amounts before rounding.
Partial first/last periods use contracted days divided by the original full
anchored month's days. One-time charges are also supported. No charge caps or
minimums are required. Rates may be zero.

Advance charges are scheduled at the start of their service period, arrears at
its exclusive end. The actual billable date is the later of that date and the
charge's resolved trigger (contract start, activation, acceptance or explicit
date). A missing trigger holds the charge. A one-time charge uses its trigger
directly. Stand-ready service earns only for activated days, using the contracted
window denominator; missing days do not extend its end. Acceptance service earns
only upon recorded acceptance, not on invoice or payment. A recurring acceptance
fact identifies its particular period. A one-time acceptance deliverable may have
no service window. Missing future acceptance does not itself prevent month close.

Also accept negotiated deals: finite allocation groups with fixed consideration,
stand-ready or acceptance promises, positive extended standalone selling prices
(SSP), and installments. Allocate group price by relative SSP. Missing SSP or an
incomplete schedule holds acceptance. Zero consideration is valid. Invoice display
items and installment proportions do not determine allocation. Allocate cumulative
net billed consideration by the same SSP weights; post changes between cumulative
targets, not independently rounded installments. Performance, cash, billing and
allocation are separate facts. Groups remain independent even on one invoice.

## Bill And Settle

Bill-run preview changes nothing. Generation freezes selected customers/scopes and
creates drafts, not AR, coverage or journal entries. Empty selection means nobody;
null means current tenant customers. Group by payer/currency. Posting revalidates
relevant versions and competing coverage. Unrelated activity leaves the draft
valid. Cancellation releases draft reservations. Work already posted elsewhere
is covered, not billed twice. Zero-priced complete work gets coverage without a
nonzero document. Related results commit atomically; independent scopes can finish
while another is held. Retry retains the frozen selection and completed work,
without silently adding new customers. A new run ID does not create new service.

Posted documents are immutable; settlement and reversed/compensated status remain
separate. Invoice/debit increases debt, credit decreases it. Each item retains
component and source attribution. An operator memo is a fixed signed change to
that component's consideration, not release of its coverage or a permanent change
to future recurring periods. It cannot make consideration negative. Posting also
remeasures earnings through the existing recognition horizon. The memo is not
generated again by the next bill run. For allocated deals a full-sale memo adjusts
the named group's price using its retained SSP weights.

Receipts are cash, not revenue. Applications explicitly allocate a receipt or
credit to same-customer/currency invoice or debit items. Reject overapplication.
Unapplication restores the source and AR, not the original cash receipt. New funds
do not automatically pay unrelated debt. Credits first reduce referenced open AR;
excess is available customer credit. Track restricted and cash-backed portions.
The automatic AR reduction is an application from the credit, listed under
/applications and unapplied like any other application.
An unpaid credit cannot produce refundable cash. Release backing from remaining
settlements in reverse application posting-date/key order, transferring rather
than copying it to the credit. The original settlement remains applied; its
backing-released portion cannot be unapplied while the dependent credit is active.
An attempt to unapply that locked portion returns 422 prerequisite_failed without
partial changes. Insufficient otherwise-unlocked funds remain invalid_domain.

When applying mixed credit, consume restricted before backed, and oldest provenance
first within each category (originating posting date, then business key). Partial
unapplication restores its consumed portions newest first. Refunds use only
available backed funds, oldest first, and change neither consideration nor revenue.
Retain original/applied/unapplied/refunded/backing-release histories. A backing
release is not an extra balance added to available/applied funds.

## Tenant Accounting

The tenant configures account codes, hierarchy, posting eligibility, segments,
lookups and distribution rules. Codes have no built-in economic meaning. Resolve
rules by function, context and ascending priority; missing selected values or
conflicting best-priority addresses hold the whole effect. Identical tied outputs
are allowed, retaining the lexicographically smallest ASCII rule key. Array order
does not break ties. Do not silently fall through or invent
a suspense account. Split weights must be positive and total 100. Allocate cents
conservingly. Parent accounts roll up without duplicate postings.

In clearing notation: billing debits receivable and credits contract position;
cash debits cash and credits customer funds; application debits customer funds and
credits AR; earnings debit position and credit revenue; refunds debit customer
funds and credit cash. Credits reduce billed position and AR or establish available
funds. In separate mode, track asset=max(earned-billed,0),
deferred=max(billed-earned,0), per revenue unit, not netted across the customer.

Recognize cumulatively using accepted terms and actual performance. Reads do not
post. Earlier through requests cannot reverse a later recognized horizon. Effects
retain source, economic date, posting date, accepted context, resolving configuration
and actual account/segment addresses. Ordinary billing/cash economic date is its
posting date; recognition uses service dates. Expose logical daily target differences
even if journals batch them. New effects use posting-date configuration. Publication
alone moves no balance. Corrections under original policy retain accepted routing;
current policy offsets actual old addresses and resolves target addresses under the
current configuration. Historical offset legs may use retired original accounts.

Close freezes the complete month's as-posted journal population and financial report
content. Additional rows with all monetary fields zero do not change financial
content; changes to nonzero per-unit values or gross debit/credit movements do. It
requires due recognition and required input, not cancellation of every draft.
Adjustments post in an open month with original economic dates retained. Current
reports show latest economic targets; as-posted reports show posting-date movements.
Opening plus movement equals closing. Each unit's position is billed minus earned.
Retain data and operation replay across real server restarts and code upgrades.
