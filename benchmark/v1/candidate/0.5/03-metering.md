# 3. Add Metered Service

Add usage charges to existing catalogs and subscriptions. Charge.kind now also
accepts "usage", with UsageOptions instead of Options; usage overrides are partial
UsageOptions. Existing fixed subscriptions, invoices, settlements and accounting
continue unchanged. The billing policy introduced in milestone 2 governs recurring
licensed charges only; it does not prorate usage quantities or usage prices.

Releasing all affected active billing coverage allows a retained usage revision
to be retried through its source route. Recompute with the new fact and preserve
old documents. Recognition adjusts the economic target in the open posting period.
Changed or unchanged rebilling must neither consume service twice nor recreate
accepted subscriptions. Shared discounts require complete usage for all eligible
members before fixing their allocation; unrelated scopes remain independent.

## Meter Linear Usage

Sources send keyed, revisioned usage facts. Assign source aliases to consumers in
effective windows. Match event type and dimension filters, sum exact quantities,
then price at the declared linear rate. Membership, assignment and service date
determine attribution, not the order events arrived. Each pricing group initially
contains consumers of a single customer. A monthly usage charge registers those
consumers/product/metric for arrears billing. Overlapping duplicate registrations
are invalid; the same raw event may legitimately feed different products.

Finalize only complete dependency windows. Each group/window declares its required
sources; each source explicitly certifies completion. No events with completion
means zero; no completion means unknown. Unresolved assignments hold affected work.
Incomplete usage must not block independent fixed service. Billing and recognition
require the full relevant bucket, even when a customer subset was requested.

Revision identity is tenant/source/event_key. Higher revisions replace the current
fact; same revision and same domain payload is inert, conflicting payload conflicts,
lower revision is stale. Input record keys are not source revision identity.
Withdrawals remove the fact without inventing a replacement quantity. Ordinary
ingestion of changes affecting active posted coverage holds a proposal; it cannot
rewrite billing history. Completion is monotone but does not suppress late facts.

## Usage

| POST collection | Body |
|---|---|
| /consumers | {key,customer_id,name,attrs}; immutable owner |
| /sources | {key,name} |
| /assignments | {key,source_id,alias,consumer_id,window}; no overlapping source/alias windows; PUT future intervals only |
| /metrics | {key,event_type,filters:Attrs,aggregation:"sum"}; immutable once referenced |
| /tariffs | {key,currency,model:"per_unit",bands:[{up_to:null,unit_price:Q}]} |
| /pricing-groups | {key,owner_customer_id,product_id,metric_id,versions:[{key,window,consumer_ids:I[],tariff_id}]}; disjoint windows; PUT only future intervals not intersecting accepted effects |
| /source-manifests | {key,pricing_group_id,window,source_ids:I[]}; nonempty unique sources and complete dependency-window coverage; PUT may revise the manifest before dependent usage has been finalized |

EventInput={key,event_key,revision:int>=1,state:"active",event_type,alias,occurred_at:T,
quantity:Q,identity:null,interval:null,dimensions:Attrs}; withdrawal instead exactly
{key,event_key,revision,state:"withdrawn"}. POST /sources/{id}/events; GET nested
collection filters event_key/state, includes current facts and held proposals.
POST /sources/{id}/complete {key,manifest_id,through_before:D}; source must belong
to manifest; cannot certify future days. Full window completion is required.
POST /sources/{id}/events/{event_key}/proposals/{revision}/retry {} rechecks a held
revision without replacing its proposed payload. Active billing hold issue is
active_billing. An unseen event has revision0; ingestion key is excluded from source
revision payload equality, but every domain field remains included.

UsageOptions={metric_id,pricing_group_id,consumer_ids:I[],period:Period,billing:"arrears",
minimum_minor:null,maximum_minor:null,usage_proration:"none",trigger:Trigger}.
No licensed price/quantity fields on usage. Nonempty consumers belong to the customer
and effective group, matching metric/product. Registrations for a shared bucket
use the same anchored periods; membership without an active registration is held,
not authority to bill someone else. No allowances or amount-proration required.
POST /rating-previews {pricing_group_id,window} exposes read-only totals, dependency
completion and rows. GET /rated-charges filters group_id/consumer_id/customer_id/
product_id/through. Rows {key,scope_key,group_id,metric_id,tariff_id,consumer_id,
customer_id,product_id,service_date,window,measured:Rational,included:Rational,
billable:Rational,rated_exact_minor:Rational|null,prorated_minor:N|null,net_minor:N|null,
billed_minor:S,source_refs:[{source_id,event_key,revision}],issues:Issue[]}.
included is zero here. Monetary row allocations conserve rounded bucket totals,
ordered by service date, source key, event key, consumer key for ties. Quantity
stays exact. No second consumption on read. Usage earning kind is unfunded_usage.
Context adds consumer.key/attrs.NAME,source.key,metric.key,pricing_group.key;
multi-source effects have no arbitrarily selected single source.key.
