# Documentation And API Research

Reviewed 13 September 2026. This is a targeted primary-documentation review of
commercial terms, pricing, commitments, settlement and revenue accounting, not
an audit of every endpoint or a hands-on trial of paid vendor tenants. Product
facts are separated below from Billing Bench's proposed rules.

## Main Findings

### The target is a configurable platform, not one merchant's engine

Zuora's product catalog distinguishes charge type from charge model and exposes
flat, per-unit, overage, volume, tiered and discount models. Its subscription
documentation separately defines term/renewal settings and several billing trigger
dates. These should be first-class configuration in Billing Bench, not choices
made once for a fictional merchant and embedded in code.
[Charge models](https://docs.zuora.com/en/zuora-billing/set-up-zuora-billing/billing-settings-configuration/product-catalog-settings/charge-types-and-charge-models-enablement),
[dates](https://docs.zuora.com/en/zuora-billing/manage-accounts-subscriptions-and-non-subscriptions/manage-subscription-transactions/common-subscription-information/order-subscription-and-amendment-dates),
[terms](https://docs.zuora.com/en/zuora-billing/manage-accounts-subscriptions-and-non-subscriptions/manage-subscription-transactions/subscribe-and-amend/create-subscriptions/basic-information-for-subscriptions).

Its accounting configuration similarly supports user-defined segments and
transaction-derived values. Billing Bench adopts configurable charts, dimensions
and routing, including several accounts per economic function. The benchmark's
economic vocabulary is not a prescribed tenant chart.
[Account segments](https://docs.zuora.com/en/zuora-revenue/getting-started/system-management/configure-accounting-structure/create-account-segments),
[segment sources](https://docs.zuora.com/en/accounts-receivable/finance/zuora-finance-settings/configure-segments).

### Billing and revenue recognition are different product responsibilities

Zuora exposes billing operations for orders, subscriptions and settlement, and a
separate Revenue API for inbound transactions/events and outbound accounting.
Its revenue product supports allocation and different modification treatments.
Billing Bench should therefore model both commercial obligations and revenue
obligations, rather than treating a revenue report as another invoice query.
[Z01](https://developer.zuora.com/v1-api-reference/api/orders/post_order),
[Z05](https://developer.zuora.com/other-api/revenue/tag/Inbound/),
[Z08](https://docs.zuora.com/en/zuora-revenue/advanced-revenue-operations/contract-modifications/accounting-treatments).

Metronome supplies usage, contract, invoice and credit/commit data for accounting;
its revenue documentation explicitly says it does not generate revenue journal
entries. The separate ASC 606 guide also distinguishes product/SKU configuration
from the judgment of what constitutes an obligation. Billing Bench adds a bounded
allocation and recognition engine, with that judgment supplied as input.
[M09](https://docs.metronome.com/guides/reporting-insights/financial-reporting/revenue-recognition),
[M10](https://docs.metronome.com/guides/reporting-insights/financial-reporting/asc-606-revenue-recognition).

Stripe completed the Metronome acquisition on **14 January 2026**. This does not
establish that every Metronome feature is now a Stripe Billing endpoint, or vice
versa. The proposal uses their documented surfaces separately.
[S01](https://stripe.com/newsroom/news/stripe-completes-metronome-acquisition).

### Commercial objects should not be collapsed into accounting objects

The API review found concrete representations of the distinctions the benchmark
needs: separate invoice/subscription ownership, independent commitment access and
invoice schedules, dated overrides, invoice-linked credit memo items and a
separate journal-transfer lifecycle. These are better starting points than a
generic feature checklist.

| API inspected | Relevant contract | Proposal consequence |
|---|---|---|
| Zuora `POST /v1/orders` | Can create or change subscriptions and non-subscription items; has invoice/subscription owner overrides and dated actions | Separate ownership, service and billing facts; do not copy the enormous endpoint |
| Zuora `POST /v1/credit-memos/invoice/{invoiceKey}` | Memo items can reference invoice items; effective date, reason and posting behavior are distinct fields | Link commercial corrections to original documents; settlement is another operation |
| Revenue `POST /api/integration/v1/csv/upload` and upload status | Transaction/event/bundle inputs go through template-based staged ingestion | Facts/evidence are inputs to recognition; a successful upload is not completed accounting |
| Revenue `GET /api/integration/v1/journal/list` and `/journal/batch/{batchid}/{pagenum}` | Accounting batches have a separate outbound integration lifecycle | Export acknowledgement must not be confused with posting or recognition |
| Metronome `POST /v1/ingest` | Source usage carries transaction identity, customer, type, timestamp and properties | Distinguish source facts from calculated quantities and invoice items |
| Metronome `POST /v1/contracts/create` | Contract combines pricing with commitments, schedules and overrides | A coherent sale can have several commercial components |
| Metronome `POST /v2/contracts/edit` | Typed additions/updates include overrides, scheduled charges and commitments | Amendments are structured operations over existing accepted terms |

Sources: [order schema](https://developer.zuora.com/v1-api-reference/api/orders/post_order),
[credit-memo schema](https://developer.zuora.com/v1-api-reference/api/credit-memos/post_creditmemofrominvoice),
[Revenue inbound](https://developer.zuora.com/other-api/revenue/tag/Inbound/),
[Revenue transfer](https://developer.zuora.com/other-api/revenue/transfer-accounting),
[usage ingest](https://docs.metronome.com/api-reference/usage/ingest-events),
[contract creation](https://docs.metronome.com/api-reference/contracts/create-a-contract),
[contract editing](https://docs.metronome.com/api-reference/contracts/edit-a-contract).

The retrieved Zuora order reference identified version **2026-09-11**; the
Revenue reference identifies **2025-08-06**. Metronome mixes v1 and v2 operations.
These are source reference versions, not a proposed Billing Bench compatibility
target. Some Zuora product pages redirected the automated reader to a browser
upgrade page; their official indexed article text was used. The order schema was
also retrieved directly in Markdown. No behavior was verified against a live
vendor tenant.

## Selected Sources And Design Implications

### Zuora

| ID / primary source | Documented behavior relevant here | Adopt or deliberately bound |
|---|---|---|
| [Z01: Create an order](https://developer.zuora.com/v1-api-reference/api/orders/post_order) | Subscription changes, ownership overrides, non-subscription items and dated actions share an order workflow | Adopt a smaller commercial lifecycle; omit vendor-specific options and bundled payment/tax rollback semantics |
| [Z02: Volume pricing](https://docs.zuora.com/en/zuora-billing/set-up-zuora-billing/build-product-and-prices/charge-models---configure-any-pricing/volume-pricing) | Total quantity chooses a per-unit price band | Adopt all-units volume as distinct from graduated tiers; pooling is explicit benchmark contract scope |
| [Z03: Advanced charge models](https://docs.zuora.com/en/basics/quick-start-tutorials/zuora-quick-start-tutorials/billing/advanced-charge-models) | Recurring, one-time, usage, volume, tiered and overage concepts are distinct | Select a small subset; do not implement a full pricing catalog |
| [Z04: Credit memo from invoice](https://developer.zuora.com/v1-api-reference/api/credit-memos/post_creditmemofrominvoice) | Credit memo and original invoice items retain links | Adopt traceable correction; define our own receivable-first application policy |
| [Z05: Revenue inbound](https://developer.zuora.com/other-api/revenue/tag/Inbound/) | Upload, staging and processing status are separate | Preserve known/incomplete/error distinctions, without rebuilding enterprise staging tooling |
| [Z06: Transfer accounting](https://developer.zuora.com/other-api/revenue/transfer-accounting) | List/download batches and update transfer status | Use a small local idempotent receiver, not a real ERP |
| [Z07: SSP setup](https://docs.zuora.com/en/zuora-revenue/day-to-day-operation/ssp-setup) | SSP can be supplied or estimated through configured methods | Supply approved SSP; estimate neither market value nor accounting judgment |
| [Z08: Accounting treatments](https://docs.zuora.com/en/zuora-revenue/advanced-revenue-operations/contract-modifications/accounting-treatments) | Modification rules can produce prospective, cumulative and other treatments | Select separate/prospective/cumulative cases; omit combined retro-prospective requests |
| [Z09: Ramp allocation](https://docs.zuora.com/en/zuora-revenue/day-to-day-operation/ramp-deals/ramp-allocation-in-zuora-advanced-revenue) | Ramped charges have allocation behavior distinct from simple invoice amounts; product editions differ | Test ramped billing versus actual service pattern, not every Zuora ramp algorithm |
| [Z10: Rip-and-replace scenarios](https://docs.zuora.com/en/zuora-revenue/advanced-revenue-operations/rip-and-replace/choose-the-correct-rip-and-replace-scenario) | Replacing a contract can leave balances standalone or legally carry them forward, depending on negotiation | Do not infer balance transfer from the word replacement; legal novation is excluded from 0.1 |
| [Z11: Close dashboard](https://docs.zuora.com/en/zuora-revenue/month-end-process/close-process-dashboard) | Holds, missing SSP and transaction exceptions affect close operations | Small explicit exception rules, not an enterprise close-management application |
| [Z12: Rating processor](https://docs.zuora.com/en/zuora-platform/extensibility/mediation/meter-components/processors/rating-processor) | Grouped cumulative quantities matter; mediation and billing do not automatically synchronize every price change | Test correct grouping and revised source effects; do not copy cache timing or early-availability behavior |

Z08's treatment names do not settle the accounting for any arbitrary contract.
The proposed [accounting policy](ACCOUNTING.md) defines the facts and restricted
cases explicitly. Contract control is explanatory shorthand for a net economic
position, not Zuora's chart of accounts or a required Billing Bench account.

### Additional platform configuration sources

| Primary source | Documented distinction | Billing Bench choice |
|---|---|---|
| [Charge types/models](https://docs.zuora.com/en/zuora-billing/set-up-zuora-billing/billing-settings-configuration/product-catalog-settings/charge-types-and-charge-models-enablement) | A charge's timing/type is separate from its pricing model | Reusable multi-charge plans with a defined supported model matrix |
| [Overage](https://docs.zuora.com/en/zuora-billing/set-up-zuora-billing/build-product-and-prices/charge-models---configure-any-pricing/overage-pricing) | Included usage and per-unit overage coexist with a separate recurring fee | Separate included licensed units, usage allowance and monetary funding |
| [Discount combinations](https://docs.zuora.com/en/zuora-cpq/manage-subscriptions/advanced-cpq-x-functionalities/nested-discount-rows-in-cpq-x) | Additive common-basis percentages differ from sequential discounts | Explicit mathematical modes, not assumed meanings for stacked/unstacked |
| [Subscription/amendment dates](https://docs.zuora.com/en/zuora-billing/manage-accounts-subscriptions-and-non-subscriptions/manage-subscription-transactions/common-subscription-information/order-subscription-and-amendment-dates) | Contract/service/acceptance triggers differ from term and billing dates | Charge-specific triggers and retained effective segments |
| [Termed/evergreen subscriptions](https://docs.zuora.com/en/zuora-billing/manage-accounts-subscriptions-and-non-subscriptions/manage-subscription-transactions/subscribe-and-amend/create-subscriptions/basic-information-for-subscriptions) | Finite terms, evergreen service and automatic renewal are distinct | Both term styles; explicit business-date renewal and finite forecast horizons |
| [Proration rules](https://docs.zuora.com/en/zuora-billing/set-up-zuora-billing/billing-settings-configuration/general-billing-settings/define-billing-rules/billing-rules---proration) | Day-count and discount-credit conventions are configurable vendor policies | Actual-calendar-day convention for 0.1; configurable anchors, periods and timing; no implicit 30/360 |
| [Charge caps](https://docs.zuora.com/en/zuora-billing/set-up-zuora-billing/build-product-and-prices/dynamic-pricing/use-cases/charge-level-minmax-rules-for-per-unit-pricing) | Charge bounds can accompany parameter lookup by attributes | Explicit min/max stage, separate from minimum-spend commitments |
| [Account segments](https://docs.zuora.com/en/zuora-revenue/getting-started/system-management/configure-accounting-structure/create-account-segments) | Segment structure and constant/transaction sources are configured | Tenant-owned dimensions, required values and derivation |
| [Segment sources](https://docs.zuora.com/en/accounts-receivable/finance/zuora-finance-settings/configure-segments) | Invoice/revenue segmentation can use different owner sources | Explicit consumer/payer/funder attributes, never implicit hierarchy inheritance |
| [Accounting code usage](https://docs.zuora.com/en/zuora-billing/set-up-zuora-billing/billing-settings-configuration/finance-settings/define-your-chart-of-accounts/accounting-codes-usage-in-zuora-billing) | Different transaction types derive configured GL codes from different sources | Actual configured postings, not names applied only at export |

These sources motivate the platform surface, not every test convention. For
example, the reviewed basic overage page disallows prorating included units;
Billing Bench explicitly offers fixed and actual-day-prorated allowance policies.
Our fixed-discount allocation, correction routing and reclassification rules are
also synthetic stated contracts, not claims of exact Zuora compatibility.

### Metronome

| ID / primary source | Documented behavior relevant here | Adopt or deliberately bound |
|---|---|---|
| [M01: First invoice walkthrough](https://docs.metronome.com/guides/get-started/metronome-dashboard-quickstart) | Events feed metrics, products, rates, contracts and invoices; pricing and presentation groups differ | Retain those semantic distinctions without copying navigation or onboarding |
| [M02: Ingest events](https://docs.metronome.com/api-reference/usage/ingest-events) | Transaction identity, timestamp and customer drive metering; duplicate detection has a documented window | Use source-scoped identity/revisions retained for the run; do not copy the 34-day limitation |
| [M03: Create contract](https://docs.metronome.com/api-reference/contracts/create-a-contract) | Contract terms include rates, schedules and financial instruments | Synthetic smaller schema; business consequences remain application-owned |
| [M04: Edit contract](https://docs.metronome.com/api-reference/contracts/edit-a-contract) | Dedicated v2 editing operations coexist with v1 contract creation | Use explicit changes, not wholesale replacement of every financial record |
| [M05: Discounting commitments](https://docs.metronome.com/guides/pricing-packaging/apply-credits-and-commits/discounting-on-commits) | Commit face/access amount can differ from billed cost basis; rate-based discounts are another mechanism | Adopt face versus basis. Omit commit-specific rates to avoid a second discount engine in 0.1 |
| [M06: Prioritization](https://docs.metronome.com/guides/pricing-packaging/apply-credits-and-commits/prioritization-rules) | Financial instruments and line items have explicit consumption order | Supply one short deterministic priority rule, not an undocumented assumed ordering |
| [M07: Hierarchies](https://docs.metronome.com/guides/pricing-packaging/billing-model-guides/model-hierarchical-customer-relationships) | Children can share parent commitments yet pay overages themselves; consolidated and child statements coexist | Adopt separate consumer/funder/payer. Do not count both statements as new receivables |
| [M08: Non-monotonic metrics](https://docs.metronome.com/guides/implement-metronome/core-concepts/non-monotonically-increasing-metrics) | Decreasing metric values, effective rates and credits can produce non-obvious negative lines | Specify exact recalculation semantics; do not assume every usage correction is a local negative event |
| [M09: Revenue data](https://docs.metronome.com/guides/reporting-insights/financial-reporting/revenue-recognition) | Revenue-related data spans invoices and commit ledgers; journals are downstream | Require basis/provenance and avoid double counting; implement a separate bounded recognition layer |
| [M10: ASC 606 guide](https://docs.metronome.com/guides/reporting-insights/financial-reporting/asc-606-revenue-recognition) | SKUs do not automatically determine distinct obligations; usage data supports downstream allocation | Supply obligation judgments; test the software's application of them |
| [M11: Invoice lifecycle](https://docs.metronome.com/guides/implement-metronome/core-concepts/how-invoicing-works) | Draft/final/void distinctions and scheduled versus usage invoices | Explicit issue and adjustment lifecycle; no wall-clock grace-period waiting |

An important limit in M07: the reviewed hierarchy feature **rates child usage
separately**; it does not automatically combine children for parent-level tiers.
Billing Bench's opt-in enterprise pricing pool is a synthetic commercial policy,
not a claim that the Metronome hierarchy API provides pooled tier rating.

Likewise M08 documents incremental negative quantities at then-effective rates
and order-sensitive credit application. Billing Bench instead corrects the source
fact and recalculates its documented bucket/funding scope. This is a deliberate
different contract, not a more accurate implementation of Metronome's contract.

### Stripe And Accounting Context

| ID / primary source | Relevant finding | Implication |
|---|---|---|
| [S01: Acquisition completion](https://stripe.com/newsroom/news/stripe-completes-metronome-acquisition) | Completion announced 14 January 2026 | Treat ownership as verified, not API unification |
| [S02: Pricing models](https://docs.stripe.com/products-prices/pricing-models) | Usage pricing distinguishes all-units volume and graduated tiers | Keep tariff types explicit |
| [S03: Prorations](https://docs.stripe.com/billing/subscriptions/prorations) | Proration can credit unpaid time; classic/flexible behavior differs | Do not assume a universal meaning of credit or use current price without a defined basis |
| [S04: Recognition methodology](https://docs.stripe.com/revenue-recognition/methodology) | Double-entry roles distinguish receivables, deferred/earned amounts and adjustments | Require a ledger rather than a revenue-only report |
| [S05: Refunds and disputes](https://docs.stripe.com/revenue-recognition/methodology/refunds-and-disputes) | Refund effects distinguish previously recognized and deferred amounts | Define concession and cash settlement separately; do not inherit all Stripe recovery policies |
| [A01: IFRS 15 overview](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/) | Revenue concerns consideration allocated to promises and their satisfaction | Basis for terminology, not a claim of full standards compliance |

## Requirements Chosen Rather Than Inferred

No vendor decides Billing Bench's hidden expected answer. The proposal fixes
half-open windows, UTC calendar days, minor-unit rounding, opt-in shared pricing,
grant priority, receivable-first credits, supplied accounting judgments and
current-open-period corrections. A conflicting external default does not change
those rules. Candidate requests must state them before they are tested.

The most useful synthesis is not feature parity. It is a chain of distinct
calculations: **source facts -> metered quantity -> group price -> funding ->
documented consideration -> revenue obligation -> accounting effect**. Later
events can require recomputing several links while retaining what happened
historically. [Proposal](PROPOSAL.md), [design review](DESIGN_REVIEW.md).
