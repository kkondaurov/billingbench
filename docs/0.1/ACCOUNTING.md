# Accounting Semantics, Configuration And Worked Cases

All rules and numbers here are proposed Billing Bench policy. They form a
deterministic contract for software, not accounting advice or a representation of
complete ASC 606/IFRS 15 compliance. The general separation of consideration,
performance obligations and recognition is grounded in
[IFRS 15's overview](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/).
The restricted treatments below deliberately leave professional judgment as
supplied input.

## A Revenue Subledger, Not Just Revenue Reports

Persist double-entry effects with tenant, currency, business source, economic
date, posting date, arrangement and relevant obligation/consumer dimensions.
An entry has a stable identity. A later correction links to what it corrects;
queries cannot silently recalculate the posted ledger from today's contract.

The customer of the billing platform, called a **tenant**, configures its own
chart of accounts. This is separate from the businesses receiving its invoices.
There is no mandatory seven-account chart. Codes, names, hierarchies, posting
accounts, dimensions and derivation rules are tenant-owned business data, not
candidate constants or an export-time renaming of fixed accounts.

The following table names economic meanings used in the examples. It is **not a
required list of GL accounts**. A meaning can be represented by many accounts;
several meanings can share an account while retaining their business provenance.
For example, one tenant separates platform, implementation and consumption
revenue; another uses one revenue account with product and department segments.

| Economic meaning / example shorthand | Normal presentation | Meaning |
|---|---|---|
| Cash | Debit asset | Actual received cash less actual refunds |
| Accounts receivable | Debit asset | Issued amounts still collectible |
| Customer funds | Credit liability | Unapplied receipts and refundable credits |
| Contract control | Signed clearing position, per arrangement | Net billed consideration less net earned revenue |
| Service revenue | Credit income | Earned fixed-service or usage consideration |
| Capacity-expiry revenue | Credit income | Unused nonrefundable paid basis earned on expiry |
| Revenue adjustments | Signed income adjustment | Explicit reductions or increases to previously earned consideration |

In particular, **contract control is shorthand for a calculated position**, not
a required account or storage design. For each arrangement, net billed less net
earned is a deferred position when positive and an unbilled contract asset when
negative under the benchmark's stipulated contracts. A tenant can configure
separate deferred-revenue and contract-asset accounts, further divided by product
and segment. Another configuration can use a clearing account with report
classification. Neither may net unrelated arrangements out of the economic
reports. In 0.1, unconditional collection rights arise only upon invoice issuance;
separate unbilled receivables are excluded.

Two schedules are distinct: future contractual billings, and allocated but
unearned revenue. Neither is the calculated net contract position. An entirely
unbilled and unperformed contract has both future schedules but no journal entry.
An allocation plan itself does not recognize revenue.

### Illustrative posting patterns

These patterns use a simple clearing-account configuration to keep the worked
arithmetic readable. They do not prescribe the tenant's actual journal layout.
The configured chart, account derivation and segment/split rules determine that
layout. A candidate must support the separate-asset/liability configuration too.

| Event | Debit | Credit |
|---|---|---|
| Issue an invoice | Accounts receivable | Contract control |
| Receive cash | Cash | Customer funds |
| Apply customer funds | Customer funds | Accounts receivable |
| Earn consideration | Contract control | Service revenue |
| Earn unused paid basis on expiry | Contract control | Capacity-expiry revenue |
| Credit an unpaid amount | Contract control | Accounts receivable |
| Credit an already paid amount | Contract control | Customer funds |
| Reduce previously earned consideration | Revenue adjustments | Contract control |
| Increase previously earned consideration | Contract control | Revenue adjustments |
| Refund available customer funds | Customer funds | Cash |

Each invoice component retains its arrangement. Credit application splits at the
original invoice's open receivable, not its initial amount. Revenue remeasurement
is computed separately, so issuing a credit against already earned service also
requires the applicable revenue adjustment. Refunding those funds does not
repeat it. Payment unapplication reverses the application, not cash receipt.

An accounting run may batch entries, but must expose their constituent business
effects. Exact arbitrary grouping of journal lines is not scored. The evaluator
checks both economic consequences and the actual accounts, segments and splits
selected by the tenant's configuration. It cannot collapse every chart back to
the table above and ignore a wrong account selection. Balanced journals with
incorrect configured accounts, periods or arrangements must fail.

## A. One Invoice, Two Promises

A contract sells a 100-day platform service and distinct implementation for
$10,000. Their extended SSPs are $12,000 and $3,000. The invoice displays platform
$10,000 and implementation $0. Both are in one allocation group.

| Obligation | SSP share | Allocated consideration | Earned after 20 platform days, implementation accepted |
|---|---:|---:|---:|
| Platform | 80% | $8,000 | $1,600 |
| Implementation | 20% | $2,000 | $2,000 |
| Total | 100% | $10,000 | $3,600 |

Issue the invoice: Dr AR $10,000 / Cr contract control $10,000. Receive and apply
$10,000: cash rises and AR clears. Recognize service: Dr contract control $3,600 /
Cr service revenue $3,600, with the two obligation amounts separately observable.
Contract control ends at $6,400 credit, all attributable to future platform service.

Without implementation acceptance, recognition is $1,600, not $3,600. With an
unpaid invoice, recognition is still the appropriate $1,600 or $3,600 and AR
remains open. The same sale invoiced only after service has begun creates an
unbilled contract asset until issuance, not zero revenue.

**Distinguishes:** invoice price from allocated revenue; cash from performance;
missing acceptance from a zero-priced deliverable that needs no work.

## B. Cents Belong To A Scope

Allocate $1.00 among obligations A, B and C with equal SSP. Largest remainders
produce A=$0.34, B=$0.33, C=$0.33. Permuting the request array does not move the
extra cent because ties use the stable component ID, not array position.

A $1.00 stand-ready obligation over three days earns cumulative amounts $0.33,
$0.67 and $1.00, hence daily releases $0.33, $0.34 and $0.33. Running recognition
once after three days or once each day gives the same dollar.

For a real calendar boundary, the $90 service `[2027-01-01, 2027-04-01)` has 90
days. It earns $31 in January, $28 in February and $31 in March. An invoice date
or installment split does not change those service days.

**Distinguishes:** deterministic residual allocation and cumulative rounding from
rounding each slice independently. It is a correctness boundary, not the main
frontier-difficulty bet.

## C. One Consumer's Correction Reprices Another

Two subsidiaries explicitly agree to pool usage for an enterprise discount while
paying their own attributed charges. They are not unrelated customers. One
sum-metric bucket has consumers A=80 and B=40 units. A volume tariff charges
$1/unit below 100 units and $0.80/unit from 100 units upward, across all units.
No grants apply in this case.

This is **all-units volume pricing**, not graduated tiers. The same calculation
works between projects of a single customer in release two; separate subsidiary
payers arrive in release five. Without this shared-pricing agreement, B's usage
correction would not change A's bill.

| State | Total quantity | Unit price | A charge | B charge | Total |
|---|---:|---:|---:|---:|---:|
| Original | 120 | $0.80 | $64 | $32 | $96 |
| B corrected to 10 | 90 | $1.00 | $80 | $10 | $90 |
| Difference | -30 | | +$16 | -$22 | -$6 |

After issuance, these changes require a $16 debit for A and a $22 credit for B.
Neither a $24 credit computed at the old rate nor a $6 credit only to B is correct.
If the original documents are paid, B's credit becomes customer funds and A has
a new receivable. A shared parent statement does not erase the source consumers.

**Distinguishes:** group rating from per-record arithmetic; affected-record
discovery from editing only the input's named customer.

## D. Spending Capacity Is Not Its Revenue Basis

A standalone paid grant sells $100 of face value for $80. Its single paid-capacity
obligation receives all $80 consideration. Issue and collect $80. Consuming $50
face leaves $50 face available and earns $40. The remaining deferred position is
$40, not $50. Expiry of the unused half earns that $40 as capacity-expiry revenue,
without a new $50 invoice.

Now sell a bundle for $240 with platform SSP=$200 and capacity SSP=$100. Allocation
gives platform $160 and capacity $80. Even if the invoice displays platform $200
and capacity $40, consuming half of the $100 capacity still earns $40, not $20.

A $100 promotional grant has no paid basis. Consuming or expiring it earns zero.
These policies are inspired by the distinction in
[Metronome's discounted commits](https://docs.metronome.com/guides/pricing-packaging/apply-credits-and-commits/discounting-on-commits),
but the bundle allocation is a Billing Bench rule.

**Distinguishes:** face balance, displayed charge and allocated consideration.

## E. Coverage, Overage And Minimum Spend

A charge of $120 is eligible for a $10 promotion first, then a paid grant with
$100 face and $80 allocated basis. The result is promotion $10, paid drawdown
$100, overage $10. Revenue is $80 from capacity plus $10 from overage: **$90**.
The promotion contributes neither an invoice receivable nor another $10 revenue.
The original prepaid purchase invoice is not invoiced or recognized a second time.

In a separate postpaid minimum agreement, M=$100 and qualifying overage S=$70.
The true-up is $30. Correcting S to $60 creates a $10 usage credit and increases
the true-up by $10. The total remains $100, but both economic changes must remain
visible. Do not count a prepaid purchase toward S or reduce S by cash payments.

**Distinguishes:** minimum spend from a wallet, funding from settlement, and gross
effects from an unchanged total.

## F. More Contract Value, Less Earned Revenue

An indivisible implementation obligation has $1,000 allocated price and approved
total effort of 100 units. Forty units are complete, so $400 has been earned.
The customer changes its scope: price becomes $1,200, approved total effort
becomes 200 units, and completed work is still 40.

The updated completion fraction is 20%. Cumulative earned revenue is $240.
The current-period catch-up is **-$160**: Dr revenue adjustments $160 / Cr
contract control $160. Remaining allocated revenue is $960.

If $1,000 was already invoiced and a $200 amendment invoice is issued, net billed
consideration is $1,200 and the deferred position is $960. Collection of that
invoice changes receivables and cash, not the $240 earned target. Closed earlier
postings remain; the reduction is a current-period effect with earlier economic
attribution. The principle of current-period catch-up after closed postings is
also documented by
[Zuora Revenue](https://docs.zuora.com/en/zuora-revenue/advanced-revenue-operations/contract-modifications/accounting-treatments).

**Distinguishes:** remeasurement from recognizing only newly added value or
retaining the old progress denominator.

## G. The Prospective Case Must Not Behave Like F

A distinct-service arrangement has $1,000 consideration and $600 already earned.
Sales replaces the remaining promises and adds $300 consideration. The replacement
promises have remaining SSPs of $500 and $200.

Carry $400 unearned, add $300 and allocate $700: $500 to the first remaining
promise and $200 to the second. Previously earned $600 stays earned. Allocating
the entire $1,300 again or using unpaid AR as the carry amount is wrong.

In the separate-addition control, sell new distinct service for $200 equal to its
SSP without changing the original promise. That $200 forms a new arrangement;
the original $400 remaining allocation is not blended into it.

**Distinguishes:** three treatment paths for superficially similar amendments.

## H. A Credit Is Not A Second Refund Loss

A $1,000, 100-day service was invoiced and paid. At day 40, $400 has been earned
and $600 remains deferred. Sales grants a $250 concession on the entire service,
reducing consideration to $750 without changing the service period.

The earned target is now $300 and future revenue $450. Issue the credit:
Dr contract control $250 / Cr customer funds $250. Correct earned revenue:
Dr revenue adjustments $100 / Cr contract control $100. Contract control now
has $450 credit; cash is still $1,000, and $250 is owed to the customer.

Refund $150: Dr customer funds $150 / Cr cash $150. Remaining customer funds are
$100. Net earned revenue remains $300. Refunding the credit cannot reduce revenue
again. On an unpaid original invoice, the $250 credit reduces AR instead of
creating refundable funds; it is not free money the customer can withdraw.

For the bundle in Case A, a $1,250 full-sale concession reduces its $10,000 price
to $8,750. The same 80/20 SSP split gives platform $7,000 and implementation $1,750.
At 20 platform days with implementation accepted, earned revenue becomes
$1,400 + $1,750 = $3,150, a $450 reduction from $3,600. Future revenue becomes
$5,600, an $800 reduction. A $1,250 credit therefore produces a $450 earned
adjustment and an $800 deferred reduction, even if the invoice displays the
discount entirely against platform access.

**Distinguishes:** consideration adjustment, recognition adjustment and settlement;
commercial discount attribution from relative allocation across promises.

## I. A Coupled Correction After Payment And Close

Use Case C's two consumers and volume tariff. Both contributions are on the same
service date; A precedes B in the documented funding order. The parent owns a
shared grant of $60 face sold for $48. Children pay their own overages.

| State | A/B rated | A/B paid face | A/B overage | Earned capacity | Earned overage |
|---|---|---|---|---:|---:|
| Original A=80, B=40 | $64 / $32 | $60 / $0 | $4 / $32 | $48 | $36 |
| Correct B to 10 | $80 / $10 | $60 / $0 | $20 / $10 | $48 | $30 |

The parent already paid $48; A paid $4 and B paid $32. The service period closed.
The correction creates A's new $16 receivable and B's $22 customer funds. Capacity
revenue remains $48, overage revenue decreases $6 through two attributed effects,
and the original documents, cash and closed period remain unchanged.

Now make another correction: A=20, B=10, still in the same bucket. Both are rated
at $1. Total face consumption becomes $30, paid-basis earnings become $24 and
overage becomes zero. Relative to the preceding corrected state, release $30
face, reduce earned paid basis by $24, and credit the remaining $20 and $10
overages. If the grant is still usable, that face can fund later eligible usage;
if already expired, its unused basis belongs in expiry revenue, not a newly
spendable current wallet. Use both continuations in separate fixtures.

The arithmetic in the second step is relative to the accepted first correction,
not the original invoice alone. Later uses of freed face must be recomputed in
the declared order, and can change a third consumer's overage. The caller submits
event revisions, not any of these derived allocations or credit amounts.

**Distinguishes:** a genuinely coupled calculation from three independent ledgers
that each happen to have plausible totals.

## J. Zero Net Does Not Mean No Accounting

Two obligations in the same arrangement need current-period corrections of
+$20 and -$20 to earned revenue. Company-level revenue and contract position do
not change. The obligation histories and adjustment effects must still show both.
Likewise, after an expired paid grant's earlier usage is corrected downward,
service revenue can fall while capacity-expiry revenue rises by the same amount.
That is a reclassification, not permission to omit the operation.

This requirement comes directly from a useful Sweat Bench observation: two Astra
xhigh implementations could finish with the same net balance while only one
preserved both offsetting classifications. It does not imply all xhigh runs or
all financial operations share that defect. [Evidence review](DESIGN_REVIEW.md).

## K. Same Economics, Different Configured Ledgers

Two tenants each earn $100 of invoiced platform service. Their business result is
the same, but the supplied accounting configurations are different:

| Tenant configuration | Debit | Credit |
|---|---|---|
| Simple chart | $100 to account `2300` | $100 to account `4100` |
| Segmented chart, 70/30 reporting split | $100 to `DEF`, business line `PLATFORM` | $70 to `REV-PLATFORM`, department `ENG`, region `EU`; $30 to `REV-PLATFORM`, department `OPS`, region `EU` |

The account codes, segment names, lookup from service region to `EU` and 70/30
weights are configuration inputs. They are not recognizable fixtures built into
the candidate. Another valid configuration can split into several natural
accounts instead of departments. Both configurations must preserve the same $100
earned amount. Their trial balances and exports must nevertheless differ exactly
as configured. An aggregate `Revenue` answer would miss that requirement.

Now close the simple tenant's month after crediting $100 to `4100`. Its next
configuration uses `4200` for the same service. Correct the earlier earned amount
to $80 in an open month:

- Under **original-configuration** routing, debit `4100` $20 and credit the
  original deferred account $20. The old revenue account's net is $80.
- Under **current-configuration** routing, debit `4100` $100, credit `4200` $80
  and credit the unchanged deferred account $20. The old classification is removed
  and the corrected amount receives the new classification.

These are two separately configured tests, not two accepted answers to the same
input. Neither changes the closed $100 entry. No correction has occurred merely
because a configuration was published. If the tenant explicitly reclassifies
the $100 first, a subsequent correction uses that accepted distribution as its
starting point, not the original $100 still appearing in the audit history.

A second control avoids requiring any clearing account: a tenant configures
contract asset `1450` and deferred liability `2350`. With nothing billed and $40
earned, post Dr `1450` $40 / Cr configured revenue $40. Billing $100 then posts
Dr configured AR $100 / Cr `1450` $40 / Cr `2350` $60. A fixed pair of
`AR / contract_control` lines would not honor this configuration.

**Distinguishes:** genuine configurable accounting from renaming a fixed chart;
current configuration from recorded accounting; a balanced total from correct
account/segment distribution. [Configuration requirements](REQUIREMENTS.md#acct-tenant-configured-accounting).

## L. Several Charge Models On One Subscription

A merchant configures a monthly plan with a $100 base fee and $2 per licensed
seat beyond five included seats. At 20 licensed seats the recurring bill is
$100 + (20 - 5) * $2 = **$130**. The base fee is not multiplied by seat count.
The five included seats are not a $5 credit and are not monthly usage events.

Another charge has 150 measured units, 50 included units and therefore 100
billable units. With the first 50 billable units at $2 and the rest at $1,
graduated pricing produces **$150**. A volume table charging $2 below 100 billable
units and $1 from 100 upward instead produces **$100**. A configured $140 maximum
charge reduces the graduated result to $140 but leaves the volume result at $100.
No customer hierarchy, shared money or pooled enterprise tariff is involved.

The same valid configurations must work under other merchant IDs and product
names. Renaming a merchant is not selecting a different calculation branch.

## M. Discount Rules Change The Result And Its Attribution

On a $100 charge, sequential 10% then 20% discounts leave $72. Applying both
percentages to the original $100 leaves $70. A subsequent $10 fixed discount
leaves $62 or $60 respectively. The merchant chooses the percentage policy;
neither behavior is an evaluator assumption about the word stacked.

A separate $60 fixed discount covers two eligible $100 charges. Each receives
$30, leaving $70 and $70. Increase only the first charge to $200: the discount
allocations become $40 and $20, leaving **$160 and $80**. The unchanged second
charge now costs $10 more because it receives less of the shared discount.
An excluded setup fee receives none. Applying the full $60 to every charge,
retaining the old 50/50 allocation, or discounting setup are different errors.

After issuance, adjustment documents must preserve both changed attributions.
A cancelled unpaid charge does not create freely withdrawable cash just because
recalculation issues a credit. Discounts also change the consideration allocated
to a bundle, not its relative SSP weights or cash-receipt history.

## N. A Mid-Cycle Change Is Not A New Full-Cycle Price

An April 1-May 1 subscription has 10 seats at $10 per seat per month and a 10%
discount. The $90 advance invoice is issued. Effective April 16, the customer
increases to 20 seats. April has 30 days, with 15 under each quantity.

The corrected gross charge is $100 * 15/30 + $200 * 15/30 = $150. The retained
discount makes it **$135**, so the additional invoice is **$45**, not $90 or $180.
The change does not restart the discount's duration or grant another included
allowance. May uses its own full period and effective quantity.

If the catalog later quotes $14 per seat, this accepted April amendment still
uses $10. A renewal configured to retain negotiated terms keeps $10; a renewal
explicitly adopting that newer catalog uses $14. Account configuration changes
where these amounts post, not their commercial price. Correcting a recorded
effective date later requires recomputing the service slices, discount, documents
and earned/unearned amounts together.

## Accounting Judgments Supplied, Not Guessed

The contract supplies SSPs, the allocation boundary, distinctness, service windows,
approved progress and whether unused paid rights are nonrefundable. The application
derives amounts, timing and treatment under the published rules. Collectibility
assessment, variable-consideration estimation, financing components, breakage
estimation, taxes and statutory reporting remain outside 0.1.

Use at least one example where each pair differs: billed/paid/earned;
face/basis; consumer/payer/funder; prospective/cumulative; current economics/
posted history. Tests in which all values coincide cannot establish these rules.
