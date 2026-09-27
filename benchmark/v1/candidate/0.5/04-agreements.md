# 4. Replace Rights And Finish Agreements

Customers renegotiate remaining service and prepaid rights, then sometimes end
those agreements. Preserve existing sales, invoices, grants and performance.
Use one prospective replacement policy, not a general classification engine.

## Prospective Change

An accepted agreement records negotiated inputs, not an already executed transfer.
Apply on/after its effective date, after complete performance/input and recognition
through the preceding day. An early apply is held or returns 422 invalid_domain;
it must not create rights or financial effects. Missing prerequisites hold the whole application;
they must remain possible to complete without the future agreement blocking them.
Dependent changes apply in effective-date order, then acceptance order on equal dates.
Retry keeps agreement identity. Unrelated changes do not invalidate the basis.

Preserve earned predecessor consideration. Carry its unearned consideration into
the successor pool plus negotiated new price. Allocate to successor promises by
SSP. Transfer only positive billed-less-earned position (bounded by actual assigned
billing); predecessor unbilled earned value remains there. Incoming/outgoing
transfers retain source-item ownership, not a new sale or cash transaction.
Old remaining service ceases, but old performed service and posted history survive.

Change={key,scope_key,effective_on:D,kind:"modify"|"concession",commercial:object,
billing:{future_installments:Installment[]|null}}. Null retains unissued schedule;
array replaces all affected unissued installments. Retain posted keys/coverage,
including reversed coverage eligible for rebilling. Past-due never-posted installments
are unissued, not reversed. Derive immediate document delta D-(Fnew-Fold), where
D is negotiated price change, F is unissued billing. Positive becomes new billable
amount, negative credits assigned coverage; hold if it exceeds that coverage.
Bill runs issue differences once. New prices/schedules are inputs; the delta is not.

POST /deals/{id}/amendment-preview Change;
POST /deals/{id}/amendments Change requires that deal's If-Match.
GET /amendments filters deal_id; fields retained input,scheduled|held|applied|cancelled,
issues,targets,old/new future totals and derived billing delta. POST
/amendments/{id}/apply {posting_date:D}, date at/after effective date; /cancel {}
only before applied. New operation key retries held application; replay/fresh-key
duplicate of applied agreement cannot apply twice (return existing or already_final).
Ordinary new effective dates cannot precede recorded dates.

Generic modify commercial={price_delta_minor:S,new_services_only:false,
new_services_distinct:true,remaining_distinct:true,changes_ongoing_progress:false,
successor_promises:Promise[],revised_group:null}. These fixed flags describe the
supported prospective policy; no separate-addition or cumulative-progress branches.
Full-sale concession commercial={amount_minor:N,scope:"full_sale"} with positive
amount reduces original group price/retained relative SSP, remeasuring through the
recognized horizon. It is not another remaining-service replacement.

For single paid capacity, alternative modify commercial={carry:"all_remaining",
price_delta_minor:N,new_face_minor:N,replacement_promise:{key,product_id,ssp:Q,attrs},
replacement_grant:GrantTerms without face_minor}. Successor face is remaining face
plus fixed new_face; basis is unearned basis plus fixed new price. Combined ratio
applies uniformly; retain accepted new access/eligibility/priority. Positive total
face required, new_face may be zero. Superseded predecessor rights are unavailable
and cannot expire again. Owner/currency remain unchanged. The successor can itself
be used, replaced, expired or terminated.

Deal Promise also supports paid_capacity with grant:GrantTerms, positive SSP,
window=grant.window, null activation/approved_total; owner/currency match deal.
Allocate group consideration as usual; create its grant once on deal acceptance,
not once per invoice. Promise's sold product and grant's eligible usage products
are different roles. Customer reads show bundle price, not a fabricated standalone
grant price or internal SSP/basis.

GET /position-transfers rows {key,predecessor_scope_key,successor_scope_key,
effective_on,consideration_carry_minor,billed_transfer_minor,source_items:
[{document_id,item_key,assigned_minor}],corrects_ids}. Allocate billed group position
cumulatively by SSP, then apply transfers; display amounts cannot decide ownership.
Reversing/rebilling a source invoice updates assigned billing without repeating
the commercial transfer or changing accepted allocation. Effect kind position_transfer
uses agreement effective date and position/asset/deferred functions.

## Terminate

POST /deals/{id}/termination-preview and POST /deals/{id}/terminations body {key,scope_key,
effective_on:D,retained_price_minor:N,termination_fee:null}; nested termination creation
requires deal If-Match. Apply/cancel/read/filter rules match amendments, at
/terminations/{id}/apply {posting_date:D} and /cancel {}. No extra fee feature.

The scope_key may be a group key from the deal's scope_keys.groups or a promise
key from scope_keys.promises, a grant's published scope_key, or a previous
position-transfer's successor_scope_key. A group selects the group; a promise
selects that promise's active remainder. A single-capacity agreement accepts the
published capacity promise/grant scope, not an invented internal group identifier.
The containing deal ID is the deal publishing that scope (including successor
deals). Published successor scopes remain usable by these same agreement APIs.

Stop future service and unissued billing for the active scope. Allocate final
retained price over performed SSP weights: original extended SSP times performed
fraction (activated days/window, accepted delivery 0/1, paid-capacity consumed face/F).
Positive retained price without performed weight is held; zero price is valid.
Post recognition catch-up, derive billing against net assigned billed amount,
not original invoice total. A lower final sale price can still require a positive
invoice if previously billed coverage is smaller. A negative delta credits actual
assigned source items, latest-issued first (posting date, document/item business
keys), capped by their remaining assigned coverage. Preserve unrelated scopes,
prior earned service and genuine cash/refunds. Retained old source links can cross
several replacements; termination does not erase predecessor history.
