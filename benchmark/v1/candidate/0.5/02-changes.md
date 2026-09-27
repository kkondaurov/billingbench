# 2. Change Already-Billed Service

Customers now change subscriptions after billing. Extend the same system, retaining
existing drafts, paid documents, source histories and closed books. An earlier
bill covers the amount previously accepted, not every future amount for that scope.

## Tenant Billing Policy

Tenants now choose the partial-period convention for new subscription sales.
POST /billing-policies {key,effective_from:D,proration:"anchored_month"|"daily_365"}
creates a draft; POST /billing-policies/{id}/publish {} publishes it. These are
commercial/admin operations. GET list/item retains the input and status. Published
policies are immutable; no two published policies may share an effective date.
Publication may take effect today or later, not before its recorded business date.

A subscription selects the latest published policy effective on its acceptance
date, not its creation date or service start. Before any policy exists the existing
anchored_month convention applies. Publication never changes accepted subscriptions.
The policy governs recurring flat/per-unit subscription charges, not one-time
charges, deals, discount budgets or other kinds of consideration.

An order action {kind:"policy_migration",policy_id:I} binds the subscription to that
published policy from the order's effective date. It must be eligible by that date.
An unpublished or not-yet-effective policy is invalid_domain (422); reject the
whole order without accepting its other actions.
The accepted action retains that policy even if another policy is published later.
New plans in a subscription inherit its binding for their service dates.

For a partial service segment, anchored_month uses the segment's days divided by
the original full anchored month's days. daily_365 instead uses 12 times the
segment's days divided by 365, including in leap years. Multiply this fraction by
the full-period charge amount (flat price or per-unit price times billable quantity).
A complete anchored period with unchanged charge terms and proration convention charges the
full-period amount. Otherwise split at term boundaries, effective charge changes
and policy migrations, sum exact segment amounts for that period and round once.
An inert action does not create a segment. Discounting and recognition then use
the resulting consideration under their existing rules.

Each service date retains its accepted policy binding. An accepted policy migration
remains fixed unless that migration's effective date is itself corrected.
Subscription reads expose policy_segments:[{starts_on:D,policy_id:I|null,
proration:"anchored_month"|"daily_365"}]; null identifies the original convention.

## Orders And A Shared Discount

Accept atomic effective-dated quantity/price changes, plan additions/removals,
discount attachment/detachment and cancellation. New effective dates cannot precede
recorded date. Keep earlier segments; a change does not restart the anchored month's
denominator. A future accepted order does not post future performance early.
Cancellation ends service before its effective date, not on the following day.

Support fixed discounts with one budget shared by the explicitly eligible customer
scope, across its charges/subscriptions. At this release customer selection has
exactly one member. Apply to positive gross consideration in overlapping service
intervals, proportionally, conserving cents; no negative line. Fixed window policy
uses the whole budget, actual_day policy prorates by the union of eligible active
days over its window, not the sum of overlapping charge durations. Cap total
discount at eligible consideration. Multiple budgets order by priority then key,
each acting on remaining net amounts. An attached budget is shared, not repeated
for every attachment. Changes to one charge can redistribute another's discount.
No percentage groups or renewal are required.

POST /discounts {key,currency,window,priority:int,scope:{customer_ids:I[],
subscription_ids:I[],plan_keys:string[],product_ids:I[],charge_keys:string[]},
kind:"fixed",percentage_group:null,budget_minor:N,partial_window:"fixed"|"actual_day"}.
Selectors intersect; empty non-customer axes unrestricted. Defining does not attach.
POST /subscriptions/{id}/order-preview and /orders share
{key,effective_on:D,actions:Action[],posting_date:D}. /orders requires subscription
If-Match. Actions:
- {kind:"quantity",charge_key,quantity:Q} or {kind:"price",charge_key,price:Q}
- {kind:"add_plan",plan:{catalog_id,plan_key,overrides}} or {kind:"remove_plan",plan_key}
- {kind:"attach_discount"|"detach_discount",discount_id}
- {kind:"policy_migration",policy_id}
- {kind:"cancel"}

Validate the whole ordered action list before accepting. No duplicated active
plan/charge keys. Cancellation cannot precede an action requiring active service
at that boundary. Reattaching while active/detaching while inactive is inert;
a real later reattachment has a new effective interval inside the discount window.
Hold incomplete proposals without partial acceptance; POST /orders/{id}/retry {}
rechecks them. GET /orders filters subscription_id and retains input/segments.
Preview changes nothing. Orders do not immediately issue ordinary billing changes;
bill runs issue differences, recognition-runs post earnings differences.

Rows add pre_discount_minor, discounts:[{discount_id,group_key,amount_minor}],
net_minor. Unknown amounts remain null with issues. Positive and negative component
differences produce invoice/credit documents in one atomic result, even if the
total is zero. Retain signed coverage by component and original document/item links.

## Release Billing Coverage

POST /billing-results/{id}/reversal-preview {posting_date:D} lists prerequisites
and predicted documents/effects. POST /{id}/reverse {key,posting_date:D} reverses
the whole related result. The operator must first unapply active settlements and
neutralize dependent adjustments in reverse dependency order; the reversal endpoint
does not perform those prerequisites automatically. Otherwise prerequisite_failed with no
partial reversal. Invoices get matching posted credits clearing them; generated
credits get matching debits cleared by those credits. Original documents stay
posted and flagged reversed. Release corresponding signed coverage, not the sale,
accepted order, delivered service, source fact or earned revenue. An earned but
unbilled unit becomes an asset. Rebilling uses retained accepted terms and lineage.

POST /documents/{id}/compensate {key,posting_date:D} neutralizes a commercial memo
using a linked opposite memo, undoing its fixed consideration adjustment, not
releasing service for rebilling. The operator must first unapply its allocations;
compensation does not unapply them automatically. A credit must have
its entire unrefunded balance available. A refunded required balance prevents
compensation. Clear a compensating debit using the original credit; restore backing
dependency links so the original cash application becomes unappliable again.
The operator must first neutralize dependent adjustments. Repeated reversal/compensation cannot
repeat financial effects. New effect kinds billing_reversal/commercial_compensation.

Allocated-deal full-sale memos follow the same settlement and reversal rules;
invoice display prices still do not determine allocated consideration.
