# 5. Correct History Without Undoing Decisions

Operators now correct facts after invoices, settlements, replacements, termination,
expiry and period close. Preserve all earlier behavior. This is correction of
recorded facts under retained agreements, not a secretly backdated new negotiation.

Commercial/admin may preview corrections and reclassifications. Revenue/admin may
accept and retry them. Customer credentials cannot access tenant-wide impact,
accounting addresses, correction records or reclassification records.

## Correction

Correction={key,reason,posting_date:D,change:Change}. Supported changes:
- {kind:"source",source_id,event:EventInput}, strictly higher revision including
  withdrawal or late first fact (unseen revision0).
- {kind:"assignment",assignment_id,replacement:{consumer_id,window}}.
- {kind:"recorded_term",resource:{kind:"subscription"|"subscription_order"|
  "deal_amendment"|"deal_performance",id},path:string[],replacement:scalar}.

Allowed paths: subscription ["starts_on"], ["ends_before"], ["charges",charge_key,
"quantity"|"price"]; order ["effective_on"] or ["actions",zero_based_index_string,
"quantity"|"price"] for an existing action; amendment ["effective_on"] or
["commercial","price_delta_minor"]; performance ["effective_on"]. Literal keys
in arrays, not dotted-path parsing. Value retains original type. No arbitrary
patches or journal edits. Correct accepted sale options, not its shared catalog.

POST /correction-previews Correction is read-only. Returns {data:{basis_token,
issues,result:{effects:ImpactRow[],affected:Ref[]}}}. POST /corrections same plus
basis_token atomically accepts facts and all derived documents/accounting. Token
binds change, posting date and relevant basis, not unrelated state. Missing token
invalid_request, relevant stale token stale_basis. Replay precedes token validation.
Impossible retained constraints/negative pools hold without any partial economics;
do not clamp or discard inconvenient components. GET retains input/old/new/source
versions/lineage/issued IDs. POST /corrections/{id}/retry {basis_token,posting_date?:D}
uses a fresh preview for same change, optionally new open month; changed retry input
requires fresh idempotency key. Earlier attempts/dates remain visible.

ImpactRow={key,kind,scope_key,customer_id:I|null,obligation_key:string|null,
old_minor:S,target_minor:S,delta_minor:S,old_addresses:AddressAmount[],
target_addresses:AddressAmount[],source_refs:Ref[],unchanged_reason:string|null}.
AddressAmount={account_key,segments:Attrs,debit_minor,credit_minor}.
Kinds rated,discount,grant_face,grant_basis,billing,recognition,position_transfer,
account_distribution. A zero amount difference may still change addresses.

Derive affected scopes from the pricing/funding/performance rules. Preserve negotiated
effective dates, fixed new price/face, eligibility and agreement identities unless
that input is itself selected for correction. Recompute derived carry, basis,
assigned billing and earnings through retained later agreements. This includes
their expiry/termination consequences; ended rights do not become spendable again.
Fixed commercial memos remain fixed adjustments until compensated.

Compare against latest accepted targets, not only the original invoice. Check
customer, obligation, document direction and accounting address separately, not
just global net change. Already billed adjustments create linked posted credit/debit
memos immediately; genuinely released unbilled service stays for normal bill runs.
A newly positive billable obligation needs its own debtor even when it previously
needed no invoice. Never borrow a sibling's document solely because pricing is
shared. Historical payer policy remains in force for that service. Preserve cash
receipts, real refunds and application/backing history. A second correction uses
the state after the first, including funds consumed since then.

Original ingestion still holds changes under active coverage; only this explicit
historical route accepts them with their consequences. Reversing coverage remains
the earlier alternative. Required propagation into dependent scopes must not
mutate unrelated tenants, pricing groups, consumers or later negotiated inputs.

## Reclassification And Reporting

POST /reclassification-previews and /reclassifications {key,scope:{currency,
scope_keys:string[]|null,effect_ids:I[]|null,economic_window:Window|null},
configuration_id,posting_date:D,basis_token?:string}. Exactly one scope selector
nonnull/nonempty. Preview forbids token; acceptance requires it. Published target
configuration must be effective/eligible by posting date. Same impact schema,
no change to price, billing, earnings or funds. Publication alone is not reclassification.

Original-policy corrections use the latest accepted routing baseline including
explicit reclassification. Current-policy corrections offset actual old addresses
and resolve new targets at correction posting date. Same-address deltas may net;
different addresses/categories must remain distinct even if global amount is zero.
Old entries and resolving configurations are immutable. Closed as-posted reports
remain fixed; adjustments post in an open month with economic dates retained.
Current reports reconcile revised economic targets without counting the same
correction both in its economic month and again as new economics in posting month.
