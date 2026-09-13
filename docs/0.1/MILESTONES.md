# Milestone Plan

Seven releases of one configurable billing platform. The platform's customers
are merchants, each with its own catalog, subscribers, commercial policies and
accounting configuration. The evaluator configures the product through public
operations. It does not supply pre-priced bills or merchant-specific code.

Candidates receive the current release and retain earlier requests, not the
roadmap or evaluator. Business dates are explicit; no wall-clock sleeps.
Policy IDs refer to [requirements](REQUIREMENTS.md).

## 1. Configure Merchants And Sell Subscriptions

**Business request.** Different merchants sell combinations of access, licensed
seats and setup. They need a reusable catalog, not one hard-coded subscription fee.

Deliver tenants, products, versioned rate plans and multiple charges per plan.
A subscription can contain several plans. Support one-time and recurring
flat/per-unit charges, including configured included licensed units. Quantities
belong to their charges, not one subscription-wide number.

Support fixed-term and evergreen subscriptions, monthly/quarterly/annual cycles,
advance or arrears billing, and charge starts triggered by contract effectiveness,
service activation, acceptance or a specified date. Billing anchors are separate
from term boundaries. Retain resolved defaults/overrides in accepted terms;
publishing a catalog version does not reprice existing subscribers.

Create invoice previews, issued documents, cash receipts, payment applications,
per-charge stand-ready recognition, one-time acceptance recognition, journals
and monthly close. Configure tenant charts and required segments from the start.
Price period, service period and accounting month are not one universal date.

**Acceptance anchors.** Case L combines a platform fee with seats beyond an
included quantity. A 31st-day anchor reaches February's last day and returns to
the 31st in March. Advance and arrears produce the same earned service but
different receivables. Two tenants use different configured accounts.
Rules: CATALOG, SUB, TIME, MONEY, ACCT, DOC, SETTLE.

**Carry forward:** multi-charge subscriptions, different anchors and triggers,
an unactivated charge, an unpaid bill, unapplied cash, a closed month, old catalog
versions and two charts. The old application creates the state, not evaluator SQL.

## 2. Meter And Rate Consumption

**Business request.** Merchants sell requests, storage and concurrent seats.
Included usage and nonlinear pricing matter even for one customer with no pool.

Add revisioned raw events, source completion, dated consumer mappings and reusable
sum/distinct/peak metrics. Charges select per-unit, included units plus overage,
graduated tiers, all-units volume, or a tier table with an overage tail. Optional
charge minimum/maximum amounts are distinct from later commitment minimum spend.
Support graduated/volume pricing for licensed recurring quantities too.

**Pivot: contracted, observed and billable quantities differ.** Monthly included
requests are neither free licensed seats nor a money wallet. Repeated imports
cannot grant another allowance. A peak is not a sum of seats seen in a month.

Initially rate each customer's scopes, optionally combining its projects.
Cross-customer pools arrive in release five. Revise unissued facts and rerate
previews; post-issuance source corrections arrive in release seven. Missing feeds
prevent issuance; complete zero usage is valid.

**Acceptance anchors.** Case L contrasts graduated and volume prices after an
allowance. Compare disjoint versus simultaneous intervals with the same
per-project totals. Include a charge cap. Rules: USAGE, RATE, ALLOW, CATALOG.

**Carry forward:** allowance consumption, mixed recurring/usage subscriptions,
different tariffs, incomplete feeds, an issued usage bill and old metrics.

## 3. Discount And Amend Live Subscriptions

**Business request.** Sales offers introductory promotions and negotiated prices.
Subscribers add seats, change plans, cancel or renew while billing continues.

Add percentage and fixed discounts with scope, effective windows, duration and
stacking. Support sequential percentages and additive percentages against a
common basis, followed by scoped fixed discounts. Allocate a fixed discount
across eligible charges; changing one can affect another without pooled usage.

Add orders to add/remove plans, change quantity/price, cancel and renew. Preserve
dated segments and previews of proration, new charges and credits. Prospective
changes already affect issued advance bills. Renewal pricing can retain terms
or adopt a specified catalog version. An amendment does not restart a promotion.

**Pivot: one current plan and one net discount cannot reconstruct the deal.**
Basis, scope and time of each change survive. Commercial discounts are not cash
deposits. Ordinary subscription changes do not wait until the later revenue
restructuring milestone.

**Acceptance anchors.** $100 less sequential 10% and 20% leaves $72; additive leaves
$70. Case M reallocates a fixed discount; Case N changes seats mid-cycle. Include
paid/unpaid cancellation, discount expiry, renewal price selection and stale
previews. Rules: DISCOUNT, SUB, CONTRACT, DOC, SETTLE.

**Carry forward:** discounted bills, dated amendments, cancelled charges,
upcoming renewals, expired discounts and retained catalog versions.

## 4. Allocate Revenue Across Promises

**Business request.** Merchants negotiate bundle prices and invoice in ramps while
delivering several promises. An invoice line is no longer a revenue unit.

Add arrangements, allocation groups, SSPs, obligation templates and relative
allocation. Several charges can fund one group; one charge can fund several
obligations. Commercial discounts change consideration, not the supplied SSP.
A zero-priced implementation line can receive allocated consideration.

Recognize stand-ready service over time, deliverables on acceptance and projects
by approved progress. Missing SSP/progress is not zero. Tenant accounting rules
derive accounts and segments from obligation attributes and split posting legs.
Reporting splits are independent of SSP allocation.

**Pivot: commercial charge structure and accounting structure diverge.** Old
single-obligation arrangements keep their economics and history. New bundles can
be sold now; modifying their allocation requires release-six treatments rather
than a guessed early implementation.

**Acceptance anchors.** Cases A/B and K. Discounted bundle sales use the allocation
arithmetic in H; subsequent concessions wait for release six.
Rules: ALLOC, REV, ACCT.

**Carry forward:** partly performed bundles, acceptance/progress evidence,
ramped billings, old single-charge arrangements and configured posting splits.

## 5. Sell Enterprise Commitments

**Business request.** Some merchants sell prepaid rights, negotiate minimum spend
or share terms across subsidiaries. These are optional configurations.

Add paid grants with face value and allocated basis, zero-basis promotions,
eligibility, priority and windows. A parent can fund selected children while they
pay overages. Introduce pricing pools separately from funding access and invoice
consolidation. Add postpaid minimum-spend true-ups.

**Pivot: unit allowance, monetary discount, prepaid right and minimum commitment
are different.** Rate billable units, apply commercial discounts, draw funds and
compute minimum spend in the declared order. Paid capacity in a bundle earns
allocated basis, not face value or invoice display price.

**Acceptance anchors.** Cases C/D/E/I, plus single-customer controls. Combine a
recurring fee, included usage and overage-only discount before shared funding.
Account dimensions follow the configured consumer/funder/payer source.
Rules: FUND, MINIMUM, OWNERSHIP, RATE, DISCOUNT, ALLOC, ACCT.

**Carry forward:** partial/expired grants, minimum windows, parent/child bills,
discounted overage and earlier non-enterprise subscriptions that still work.

## 6. Restructure Revenue Contracts And Accounting Configuration

**Business request.** Deals change after delivery, and finance changes its
classification rules. These are different operations over related history.

Derive separate-addition, prospective-replacement and cumulative-catch-up treatment
from commercial facts. Preserve earned distinct service where required; remeasure
an indivisible project where required. Carry only unused rights and unearned basis.
Concessions specify full-sale or remaining scope; refunds remain separate.

Publish accounting configurations and explicitly reclassify selected scopes.
A configuration change alone moves no balances. Corrections retain their selected
routing policy; reversals reference the actual accepted account distribution.

**Pivot: subscription amendment, revenue modification and GL reclassification
cannot be one generic overwrite or replay under current settings.**

**Acceptance anchors.** Cases F/G/H/K. Reclassify, amend, then correct an obligation:
do not reverse an already superseded classification. Rules: AMEND, ACCT, IMPACT.

**Carry forward:** repeated amendments, reclassifications, partial refunds,
remaining rights, old receivables and original journals/configurations.

## 7. Correct Settled History And Export Accounting

**Business request.** Usage or recorded commercial facts were wrong after invoices
were paid and periods closed. Correct the economics without erasing the history.

Permit historical source revisions and corrections to erroneous mappings or
recorded subscription facts. Distinguish these from a newly negotiated deal.
Recompute price, allowance, discount, funding and recognition scopes; derive
signed documents and configured journals. Discover affected records from the
fact revision, not an input list of expected invoice deltas.

Add an idempotent local GL receiver and acknowledged export batches using Oban.
A lost response requires reconciliation, not duplication or remapping a frozen
batch under today's chart. This is one integration, not an ERP implementation.

**Acceptance anchors.** Cases I/J/K plus M/N after payment and close. Changing one
charge redistributes another's discount; correcting an allowance changes overage
and funding; chart versions change replacement addresses. Observe gross effects.
Rules: IMPACT, CLOSE, EXPORT, ACCT.

**Final histories:** twelve adjacent histories, two per transition, plus lifetime
databases spanning releases 1-7 and 2-7. Configure several merchants on the same
implementation and introduce additional valid configurations after the build.

## Sequencing And Scope Review

The first three releases establish multiple charge models, calendars, discounts
and real subscription changes. Complexity does not wait for enterprise pools.
Revenue and funding then cross those existing distinctions.

Configuration is data, not an arbitrary programming language. Exclude tax
jurisdictions, FX, intercompany consolidation, statutory disclosures, arbitrary
pricing code and real bank integrations. Preserve the platform's commercial
breadth inside that boundary.

The seven-release platform has no three-hour runtime promise. Calibrate Astra
low and xhigh first. Judge genuine failed combinations,
not catalog size, runtime or generated lines. This is design, not a run launch.
