# 3. Separate Consumption, Shared Pricing And Funding

An enterprise now shares prices and purchases prepaid rights. Extend existing
subscriptions and deals without moving old debt or merging independent identities.

## Shared Prices And Payers

Pricing-group versions may explicitly include consumers under different customers
of one enterprise root. Parentage alone does not add membership. Fixed discount
customer selection may now name multiple customers under that root. It is still
one shared budget, not one per invoice. Product, metric, currency, group, anchored
period and effective membership/tariff segment define a pricing bucket.

Tariffs add model:"volume": ordered bands with strictly increasing up_to:Q and
final up_to:null. Upper bounds are exclusive: exactly a threshold selects the
next band. Select the rate from complete pooled billable quantity, apply it to all
quantity, round once and allocate by contributions. No graduated/distinct/peak
models. Segment changes reset volume selection; they do not invent another
subscription period. Cross-customer attribution uses service date, source/event
business keys and consumer key, never generated IDs.

POST /payer-policies {key,consumer_customer_id,product_ids:I[],window,
payer_customer_id}; payer is self or ancestor in tenant. Empty product list means
all products. Reject intersecting policies for a consumer/product/time. Ordinary
policies are future-effective and do not rewrite issued debtor assignments. Keep
consumer, pricing-group owner, funding owner and invoice debtor distinct.

## Prepaid Rights

Price and discount usage first, then draw eligible face value; bill remaining
overage. Grants explicitly select consumers/products, independent of pricing-group
membership and payer policy. Nonempty eligibility must stay within owner's root.
Resolve eligible grants by ascending priority, earliest ends_before, then grant key.
Allocate service in ascending service date then stable bucket/component business
key order. A later draft cannot take face already required by earlier service.

GrantTerms={key,owner_customer_id,currency,face_minor:N,window,priority:int,
consumer_ids:I[],product_ids:I[]}; face positive. POST /grants paid body
{...GrantTerms,kind:"paid",product_id,price_minor:N,installments:[{key,billable_on,
amount_minor:N}],attrs}; schedule totals price. This creates one accepted capacity
sale; face is available according to access terms, not gated on cash collection.
Promotional body {...GrantTerms,kind:"promotional",attrs} has zero basis/no invoice.
POST /grants/{id}/retry {} continues a hold. No minimum-spend contracts required.

Paid accounting basis is consideration, not face. For original face F/basis A,
cumulative draw x earns round(A*x/F); incremental releases are target differences.
Promotional draws earn zero. Bill runs and recognition both finalize relevant
complete funding, reusing the same accepted draws. A preview neither commits draws
nor consumes rights. Billing posts purchase/overage debt, not service revenue;
recognition posts paid basis consumption and unfunded_usage separately. Related
scopes require complete inputs, but unrelated/future incomplete work cannot prevent
complete earlier work. Rebilling a purchase must not issue a second grant, and
rebilling usage must not consume it twice. Coverage guards include the purchase
and dependent funding scopes, not just overage invoices.

POST /grant-expirations {key,through:D,posting_date:D} expires available rights
once after complete input and recognition through the last eligible day. For
ends_before=D, access stops at D and expiry revenue has economic date D. Release
unused basis as capacity_expiry, not consumption; no invented consumer for expiry.

GET grants adds deal_id,scope_key,promise_key (generated capacity sale), original
terms, face_remaining_minor,basis_minor,basis_earned_minor,basis_unearned_minor,
basis_recognized_minor,status:"held"|"active"|"exhausted"|"expired"|"superseded"|
"terminated",predecessor_ids,successor_ids. GET item/list accepts through=D; default
latest committed funding horizon. Earned is economic target; recognized is posted.
GET /drawdowns filters grant_id/consumer_id/customer_id/group_id/through; rows
{id,key,grant_id,consumer_id:I|null,rated_charge_key,service_date,face_minor:N,
basis_minor:S,corrects_ids:I[]}. Distinguish current totals from historical adjustments.
Rated rows add funded_minor,overage_minor,drawdown_ids,payer_customer_id; unknown
monetary values remain null with issues.

Customer grant reads show owned commercial rights/face/remaining/eligibility and
purchase price, not internal basis/context. Owners see draws against their grants,
not unrelated sibling bills or raw source payloads. Parent payers see their whole
invoice with child attribution. Context adds consumer.customer.key,payer.key/attrs.NAME,
funding_owner.key/attrs.NAME,grant.key/kind. Receivable customer is debtor; usage
revenue customer is consumer owner; capacity revenue belongs to sold grant/product.
Function capacity_expiry_revenue is configured by the tenant. Effect kinds add
capacity_consumption and capacity_expiry; no netting those categories together.
