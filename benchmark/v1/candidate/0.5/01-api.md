# Public API

Observable resources, not a prescribed database or module design. No UI required.
Base /api/tenants/{tenant_id} unless absolute. JSON. GET /health returns 200
{status:"ok"} after database readiness. IDs are returned opaque strings. Supplied
keys are immutable printable ASCII (1-128), unique by tenant/resource kind.
Encode path components; keys may contain reserved URL characters.

## Protocol

D=Gregorian YYYY-MM-DD, T=UTC RFC3339 (Z or +00:00, up to six fractional digits),
I=returned ID, Q=nonnegative decimal string (at most six places), N=nonnegative
integer minor units, S=signed integer minor units; amounts bounded by absolute
9,000,000,000,000. Rates are major units. Attrs=string-to-string map.
Window={starts_on:D,ends_before:D}. Rational={numerator:string,denominator:string}
uses integer strings, nonnegative numerator/positive denominator; reduction optional.
Listed fields are required unless ?; ?=value declares default. Unknown input fields
are invalid except arbitrary attributes/dimensions. Response extensions are allowed.
Arrays of business-keyed objects reject duplicate keys.

Mutations require Idempotency-Key and X-Business-Time:T. Identity includes tenant,
route kind and path IDs. Equal typed payloads replay without another effect;
normalize decimal trailing zeros and UTC instants, object field order and declared
defaults, but not literal strings or array order. Retry wall-clock time does not
replace original recorded time. Authenticate/check visibility before replay;
replay before version/basis guards. Changed payload conflicts. Rejected input does
not consume identity. Held input does and has an explicit continuation path, or
may be reissued with the same business key and a fresh operation key when no named
retry exists. Other duplicate business-key creates return duplicate_key.

Resources have {id,key,version:int>=1,...fields}. Existing-resource actions/PUT
require If-Match; creation in a nested collection does not, unless explicitly noted.
Draft caller-authored resources permit full-body PUT; posted/published contents do
not. Generated documents are cancelled/regenerated, not manually rewritten.
No deletion of financial history. Versions change on transitions, not reads/replays.

Successful mutations may return HTTP 200 or 201, including creation. Both mean
the same thing; operation.status supplies completion semantics. Shape:
{data:resource|null,operation:{id,status:"completed"|"held"|"partial",issues:Issue[],effects:Ref[]}}.
Issue={code,scope_key,field:string|null,message}; Ref={kind,id}. Holds apply no
economic changes to their atomic scope. Partial lists independent completed/held
scopes, not partial acceptance of one scope. Reads omit operation. Previews require
business time but no idempotency/version header, return
{data:{basis_token,issues:Issue[],result:object}} and create no records/effects.
Human messages and generated identifier encodings are not prescribed.

Errors {error:{code,issues:Issue[]}}: 400 invalid_request; 401 unauthenticated;
403 forbidden; 404 not_found including foreign IDs; 409 idempotency_conflict,
stale_version, stale_basis, revision_conflict, stale_revision, already_final,
duplicate_key; 422 invalid_domain or prerequisite_failed. Missing configuration,
evidence or complete input is a successful held outcome (missing_configuration,
ambiguous_configuration, missing_evidence, incomplete_scope, invalid_proposal),
not fabricated zero or partly committed work.

Every persisted collection below has GET list/item. Lists return {data:[],next_cursor:
string|null}, stable (key,id) order, limit default50/range1..200, opaque cursor.
Common filters key/customer_id/status where applicable; additional filters specified
below. Unsupported filters invalid_request. Reads never change economics.

Scaffold authentication supplies tenant_id, role, customer_id. platform_admin may
create tenants, not bypass tenant permissions. admin does everything in its tenant;
commercial manages commercial/source terms; billing operates documents/cash; revenue
operates accounting/performance/close. Internal operators can read tenant records.
Customer role is read-only on its own customers, subscriptions, deals, documents
where it pays, and funds; other customer item reads 404, mutations403.
No internal SSP/allocation/context, GL/configuration, source payload or previews in
customer views. Omit protected fields rather than supplying misleading zeros.
Internal-only collections may reject customers with 403 forbidden or conceal them
with 404 not_found; neither response includes data, even an empty data array.

## Sell

Period={months:1,anchor:"service_start"|"day",day:int[1,31]|null}; day nonnull
only for day anchor. Trigger={kind:"contract"|"activation"|"acceptance"|"date",
date:D|null}; date nonnull only for date kind.
Options={model:"flat"|"per_unit",price:Q,quantity:Q,included:Q,
minimum_minor:null,maximum_minor:null,period:Period|null,billing:"advance"|"arrears",
trigger:Trigger,recognition:"stand_ready"|"acceptance"}. Flat quantity1/included0.
One-time period null, recurring period required. The null minimum/maximum fields
are reserved and impose no bounds. Complete options are supplied on charges.
Charge={key,product_id,kind:"one_time"|"recurring",options:Options,
overridable:string[],lookup_key:null}. Plan={key,name,charges:Charge[]}.

| POST collection | Body / actions |
|---|---|
| /api/tenants | {key,name,defaults:{},grouping:"payer"} |
| /customers | {key,name,parent_id:I|null,attrs}; PUT {name,parent_id,attrs}; reject parent cycles; parent immutable after accepted sales |
| /products | {key,name,attrs}; PUT {name,attrs} affects future accepted contexts |
| /catalogs | {key,effective_from:D,defaults:{},plans:Plan[],price_lookups:[]}; /{id}/publish {} |
| /subscriptions | {key,customer_id,currency:"USD"|"EUR",starts_on:D,ends_before:D,renewal_months:null,plans:[{catalog_id,plan_key,overrides:{charge_key:Partial<Options>}}],attrs}; /{id}/accept {}; /{id}/evidence {key,charge_key,kind:"activation"|"acceptance",effective_on:D,period_starts_on?:D}; /{id}/forecast?through=D |

Empty defaults and price_lookups/null lookup_key/renewal_months are reserved; no
inheritance or renewal processing. Accept only effective published catalogs.
Retain body/status and resolved_charges:[{key,options,source_versions,context}].
Charge/plan keys must be unique in the accepted subscription. Evidence cannot
assert future performance or precede service; activation must precede term end.
One-time acceptance may equal the excluded delivery-window end. Duplicate matching
evidence is inert, conflicting accepted facts revision_conflict. Evidence lists at
/subscriptions/{id}/evidence retain IDs. Recurring acceptance needs period_starts_on.

Forecast/revenue-unit rows: {scope_key,subscription_id:I|null,charge_key:string|null,
product_id,customer_id,currency,window:Window|null,quantity:Q|null,gross_minor:N|null,
net_minor:N|null,billed_minor:S,earned_minor:S|null,unearned_minor:N|null,
position_minor:S|null,billable_on:D|null,due_minor:S|null,issues:Issue[]}.
Null means underivable with an issue, not known zero.
billed_minor is assigned billed consideration, net of memos and reversals.
GET /revenue-units filters
subscription_id/deal_id/through. Explicit through includes that day; default current
recorded horizon. Forecast data is rows or an object with rows. No fabricated window
for one-time acceptance. Group scopes are not extra rows double-counting promises.
A one-time stand-ready charge requires the subscription's finite service window;
its row uses that window. Computed revenue-unit views may return all matching rows
or paginated rows; they accept the documented filters without requiring a limit.

Promise={key,product_id,kind:"stand_ready"|"acceptance",ssp:Q|null,
window:Window|null,activation_on:D|null,approved_total:null,attrs}.
Stand-ready requires window and known activation or later evidence; acceptance
uses null or explicit delivery window and null activation. Group={key,price_minor:N,
promises:Promise[]}. Installment={key,billable_on:D,items:[{key,group_key,promise_key,
amount_minor:N}]}. Installments per group total price; display zeros allowed.
POST /deals {key,customer_id,currency,groups:Group[],installments:Installment[],attrs};
/{id}/accept {}. Reads add allocations:[{group_key,promise_key,scope_key,allocation_minor}]
and scope_keys:{groups:{key:opaque_scope},promises:{key:opaque_scope}}. Deal revenue
rows add deal_id,group_key,promise_key,allocation_minor with null subscription/charge
and quantity. /deals/{id}/forecast?through=D returns those rows.
POST /deals/{id}/performance {key,promise_key,kind:"activation"|"acceptance",
effective_on:D,completed:null}; GET nested collection and /deal-performance/{id}.
Evidence does not post recognition; kind must match promise and dates obey its window.
Accounting context adds arrangement.key/allocation_group.key/obligation.key,
obligation.kind/obligation.attrs.NAME.

## Documents, Settlement And Reads

RunInput={key,customer_ids:I[]|null,target_date:D,invoice_date:D,posting_date:D}.
POST /bill-runs/preview RunInput; POST /bill-runs RunInput generates;
The preview's result includes documents:[{kind,customer_id,currency,total_minor,
items:[{scope_key,amount_minor}]}], the proposed invoice/credit amounts before
posting, alongside any implementation-specific detail. It creates no documents.
/{id}/post {result_keys:string[]|null}; /{id}/retry {mode:"generate"|"post",posting_date?:D}.
Retry preserves target/invoice dates and selection, permits a new open posting date
for unposted work with revalidated accounting; completed work retains original dates.
POST /documents/{id}/post {posting_date:D}; /{id}/cancel {} cancels whole related
draft result. GET collections bill-runs/billing-results/documents/receipts/applications/refunds.
Results retain input/basis and scopes:[{scope_key,status:"not_due"|"held"|"draft"|
"posted"|"covered"|"cancelled",document_ids:I[],issues:Issue[]}], signed coverage_minor
per scope. Result status draft/held/partial/posted/cancelled.
Bill-run reads expose result_ids:I[] linking to these billing results. Inline scopes
are also permitted instead of links. Every generated document is linked by the
corresponding scope's document_ids, including drafts and credits.

POST /memos {key,kind:"credit"|"debit",customer_id,currency,invoice_date,
posting_date,items:[{key,document_id,item_key,amount_minor:N,reason,
allocation_scope_key?:string,concession_scope?:"full_sale"}]} creates draft.
The last two fields are required for allocated-deal adjustments.
The memo response's data is either the draft document itself or a resource with
document_id:I linking to it. Post that document ID; memo and document IDs need not
match. Both forms are accepted by clients.
POST /receipts {key,customer_id,currency,amount_minor:N,payment_method,posting_date};
POST /applications {key,source:{kind:"receipt"|"credit",id},allocations:
[{document_id,item_key,amount_minor:N}],posting_date};
POST /applications/{id}/unapply {allocations:[{document_id,item_key,amount_minor:N}],posting_date};
POST /refunds {key,source:{kind:"receipt"|"credit",id},amount_minor:N,posting_date}.
All these monetary inputs are strictly positive and bounded by available rights.
Competing applications must conserve funds and debt. A losing request may return
409 stale_version or 422 invalid_domain/prerequisite_failed; exactly the valid
funded subset commits. A race cannot make otherwise available remainder unusable.

Document fields {kind:"invoice"|"credit"|"debit",origin:"bill_run"|"commercial"|
"reversal"|"compensation"|"amendment",status,customer_id,currency,invoice_date,
posting_date,result_id:I|null,items:[{key,scope_key,subscription_id:I|null,
charge_key:string|null,product_id,service_window:Window|null,amount_minor:N,
origin_document_id:I|null,origin_item_key:string|null}],total_minor:N,open_minor:N,
available_backed_minor:N,available_restricted_minor:N,reversed:bool,compensated:bool,
related_ids:I[]}. Irrelevant amounts zero. Source references remain nonnull when
there is an originating document; new debt need not invent one.
Cash sources expose original/available/applied/refunded/backing_released amounts
and source links. Application allocations expose original_minor,unapplied_minor,
backing_released_minor,currently_applied_minor,unappliable_minor.
Currently applied is original minus unapplied; backing released remains applied.
unappliable_minor is the amount currently available to unapply, excluding backing
locked by active dependent credits. It is not the amount forbidden to unapply.
GET /customers/{id}/statement returns documents/funds and per-currency integer
ar_minor,available_backed_minor,available_restricted_minor,cash_received_minor,
cash_refunded_minor, with contributing IDs. Currency arrays or keyed maps are valid.

## Accounting

Value={constant:string}|{field:string}|{lookup:{table_key,field}}.
Predicate={eq:{field,value:string}}|{in:{field,values:string[]}}|{all:Predicate[]}|
{any:Predicate[]}; empty all true/any false. Fields: effect.kind/function/currency,
product.key/attrs.NAME,customer.key/attrs.NAME,contract.key/attrs.NAME,payment.method,
obligation.kind, and additions specified above. Suffix after .attrs. is a literal
attribute key, including periods. Absent predicate values do not match. Absent
selected account/segment values hold; unknown paths invalid_request.

POST /accounting-configurations {key,effective_from,position_mode:"clearing"|"separate",
correction_routing:"original"|"current",revenue_presentation?:"net"= "net",
accounts:[{key,name,class:"asset"|"liability"|"equity"|"revenue"|"expense",
parent_key:string|null,posting:bool,starts_on:D,ends_before:D|null,required_segments:string[]}],
segments:[{key,values:[{key,parent_key:string|null}]}],lookups:[{key,values:{input:string}}],
rules:[{key,function,priority:int,when:Predicate,distribution:[{key,weight:Q,
account:Value,segments:{segment_key:Value}}]}]}; /{id}/publish {}.
Functions cash,receivable,customer_funds,service_revenue and contract_position
(clearing) or contract_asset/deferred (separate). Configs with equal effective dates
conflict; publication cannot retroactively change selected effects. Posting parents,
cycles, invalid references/weights are invalid. Best tied rules compare resolved
distributions, not merely rule text. No gross-discount presentation required.

POST /recognition-runs {key,through:D,posting_date:D}; no future through.
POST /period-closes {key,month:"YYYY-MM"}; recorded date at/after next-month start;
completed repeated close returns existing close. Persist readable records for both.
GET /effects filters scope_key/customer_id/economic_from/economic_before/posting_from/
posting_before. Fields {id,key,kind,source:Ref,currency,scope_key,economic_date,
posting_date,amount_minor:S,configuration_id,context,corrects_ids:I[],legs:
[{function,configuration_id,account_key,segments:Attrs,debit_minor:N,credit_minor:N,
rule_key,split_key}]}. Leg has at most one positive side. Kinds billing,
commercial_adjustment,cash_receipt,funds_application,funds_unapplication,refund,
recognition; retain corrected kind with corrects/source references.
GET /journal-entries retains effect IDs and resolved addresses; batching is free
if logical effects remain reconstructible. Leg configuration can differ from
effect configuration for a historical offset.
For a position-transfer pair, one effect may carry both sides' balanced journal
and the opposite effect may have empty legs. Both effects must identify the same
source agreement, dates, currency and correction ancestry, distinct public scopes,
and exactly opposite amounts. In this representation each leg adds scope_key:I,
the public revenue scope whose position it moves (not a database ID). For each
member the sum of debit minus credit on its scoped position legs is the negative
of that member's amount_minor. This documented scope_key is required only for a
joint journal, not for ordinary individually journaled effects. Private fields
are neither required nor read by clients. Other nonzero effects require balanced legs.

GET /accounting-reports?month=YYYY-MM&view=as_posted|current returns per currency
accounts:[{account_key,segments,debit_minor,credit_minor,net_debit_minor,
opening_net_debit_minor,closing_net_debit_minor}], rollups:[same], units:
[{scope_key,billed_minor,earned_minor,position_minor,asset_minor,deferred_minor}],
closed:bool,unresolved:Issue[]. Accounts are monthly movements, opening/closing
balances; units are cumulative through month end. Rollups count each posting
address once. Current view uses latest accepted economic targets/distributions,
not relabelled posting-date movements. Currency wrappers are flexible.
