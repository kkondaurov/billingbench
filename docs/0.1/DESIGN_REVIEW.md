# Design Review: Is This More Than A Larger Application?

## Verdict

Billing Bench 0.1 targets a configurable platform, not a merchant-specific
billing application. Its demand combines several price models, subscription
calendars and amendments, scoped discounts, revenue allocation and tenant-defined
accounting. Its frontier difficulty is unproven. Billing's reputation, a long
feature list or seven releases would not establish hardness for Astra.

Treat the proposal as a candidate task for calibration. Do not build a large
campaign around the domain's reputation. Strong models can solve a coherent
financial model with good tests; that would be a valid result, not suspicious
behavior to punish by restricting their architecture or development loop.

## What Prior Experiments Actually Established

These iterations have different denominators and protocols. They are not points
on one numerical difficulty scale. Most v7 configurations have one trajectory,
not enough to estimate an effort effect. Evidence paths and hashes are below.

| Evidence | Observed result | Constraint on this proposal |
|---|---|---|
| V6 Astra audit | All 12 Astra final snapshots passed the 83 ordinary API cases. Scored losses came from old-data decoding and cold-server saved-response handling. | Do not assume v6 already challenged Astra's financial semantics or manufacture difficulty from Elixir-specific traps. |
| Four-release Rebuild | Both Astra efforts reached 26/27; the shared remaining item involved ambiguous naming. | An early pivot does not establish genuine headroom by itself. |
| Nine-release Evolution | Both Astra efforts reached 63/64 Product; shared miss was ambiguous. Luna reached 26/64 after 10h 51m; one missing provider continuation blocked 31 checks. | More work can hurt Luna without producing useful frontier difficulty. Correlated integration failure is not many independent semantic failures. |
| Shared Commitments | Both Astra efforts passed 36/36 business outcomes and 14/14 histories after evaluator repair. | Joint constraints and selective corrections are already demonstrated strengths in that form. |
| Service Packages | Both Astra efforts passed all 183 business cases and 14 histories. Sol passed 182 cases; Luna 163 and 7 histories. | Nested definitions and richer object graphs are not enough. The new calculation needs a different failure opportunity. |

Evolution's Astra vectors combine saved results with unchanged-snapshot no-load
diagnostics after interrupted final evaluation; they are not complete accepted
90-check results. The expensive abandoned load setup contributes no capability
score. Service Packages is the more direct recent saturation observation.

### Successes matter as much as failures

Astra used transactional mutation boundaries, persistent identities, separate
facts and plans, immutable issued records and explicit corrections. Later features
could reuse those decisions. Its own tests found and repaired real bugs. That is
successful engineering, not something the successor should forbid.

Service Packages already derived work from nested definitions; not all its inputs
were caller-provided answers. Its shared-funding corrections required validation
of the final combined state. Luna also passed those corrections, despite other
failures. Billing Bench cannot claim that simply introducing derivation or two
interacting balances is new.

The difference proposed here is a change of calculation: a pooled total selects
a price for other records; that price changes consumption of rights with a
different consideration basis; contract modification changes how remaining or
cumulative revenue is derived. Keeping old records safe is necessary but does
not itself compute these new targets.

### Specific weaknesses worth retaining

| Observation | Requirement derived from it | What would be overclaiming |
|---|---|---|
| An unscored v6 probe found one Astra xhigh implementation omitted two offsetting classifications while another retained them | Observe gross effects, account roles and obligations, not just final net balances | Claiming Astra generally cannot do accounting |
| Sol's Service Packages shortcut lost a pending obligation after an accepted inspection with no finding | Keep unknown acceptance/progress/source completion visible through accepted and cached paths | Treating a missing value as an intentionally obscure edge case |
| Luna reused old prices for newly quoted work and missed backfills for older identities | Test effective terms through actual old-version records and subsequent operations | Claiming every failed history reveals a different migration bug |
| Luna's supplier tests bypassed a failing HTTP path | Test receiver effects, not merely queue contents or fabricated database rows | Making a queue-loading defect the primary difficulty strategy |
| V6 reporting errors confused daily activity, cumulative balances and original funding provenance | Require dated movements, opening/closing positions and source attribution | Inferring the same cause merely from a shared failed test label |

Across the published v6 family review, Opus handled the late-credit reporting
correction in both runs, while Grok repeatedly missed it; Qwen had both a nearly
complete run and a run with linked accounting failures. Some GLM and Sol runs
also handled it. That argues for several independent financial distinctions, not
an entire successor built around the one late-expiry case.
[Published family findings](https://kkondaurov.github.io/sweatbench/#findings).

The expiry-date disagreement is evidence about specification quality, not useful
hardness. This proposal uses explicit half-open windows and supplies its rounding,
recognition and modification conventions.

## What The Slop Detour Contributes

The inspected panel contained eleven tasks and three configurations, not the
entire public benchmark. Of Sol high's 207 final failures, 39 had unsupported
expectations, 83 involved ambiguity or defective setup, eight had verified
implementation causes, and 77 remained unadjudicated. Those counts do not yield
a corrected score; fixing an early invalid assertion can expose a later defect.

Verified mistakes included reading an alternative-answer field from the wrong
object, assigning source row identities incorrectly and treating a price-book
container as the physical location of all its contents. They were genuine missed
contracts, not proof that numerical optimization or recursion caused the wider
failure rate. Both benchmarks allowed testing and revision; Slop was not simply
one-shot generation. The saved comparison and
[SlopCodeBench protocol](https://arxiv.org/html/2603.24755v2) distinguish those facts.

Billing Bench incorporates the useful lesson through **non-equivalent identities
and transformations**: source versus import, consumer versus payer, invoice
versus arrangement, face versus consideration. Each distinction has a case where
conflating it returns a different business result. It does not reproduce an ETL
language, a payment optimizer or Slop's raw failure rate.

One advantage cannot be imported into a single product: Slop samples many task
domains. Billing Bench can still happen to fit Astra unusually well. If repeated
economic redesigns remain saturated, sampling other products is more defensible
than adding every adjacent enterprise feature to billing.

## Attack The Proposal With Strong, Simple Implementations

| Proposed implementation shortcut | Would it work? | Design consequence |
|---|---|---|
| Store all business state in JSONB and use a tenant lock | Potentially yes | Allowed. Storage style and serialization are not the scoring target. |
| Preserve source events and recompute all affected groups on correction | Potentially yes, and probably a strong solution | Allowed. Correct scope, historical policy and accounting differences still need implementation. |
| Use PostgreSQL for grouping and a decimal library for arithmetic | Yes | Encouraged; do not turn ordinary tools into forbidden advantages. |
| Generic journal helper that posts balanced pairs | Useful but insufficient | Wrong accounts, obligations or periods must still fail. |
| One invoice line is one revenue obligation | No | Case A and the bundled-capacity control distinguish it. |
| Subtract removed usage at its original rate | No | Case C changes another consumer's charge. |
| One wallet stores both paid and promotional credits | Only if it preserves their separate bases and provenance | Cases D/E/I prevent a merely correct face total from passing. |
| Freeze all earned revenue after close | No | Case F needs a present-period correction without editing closed history. |
| Reallocate all historical consideration on every amendment | No | Case G preserves earned service under prospective treatment. |
| Refund is just negative revenue | No | Case H separates consideration change from cash movement. |
| Any credit memo reverses the invoice and unbills its usage | No | Case O requires ordinary credits to retain coverage and reversals to release it. |
| Document reversal cancels the sale and its earned revenue | No | Case O exposes an unbilled earned asset before rebilling. |
| One invoice ID or one usage-billed flag identifies every calculation | No | Rebilling, multiple contracted metrics and related positive/negative documents require the correct charge/scope lineage. |
| A new run ID authorizes another invoice for the same period | No | Case Q checks active coverage across runs, not only retry keys. |
| Return a reconciled company-wide net balance | No | Case J and arrangement-level asset/liability views observe missing gross effects. |
| One scalar price and quantity per subscription | No | Case L combines independently configured charges and quantity sources. |
| Collapse discounts into a single percentage or keep their original split | No | Case M changes both total and per-charge attribution under different configurations. |
| Always use the latest price or configuration | No | Cases K/N require retained versions and explicit changes. |
| Translate a fixed chart into customer account names only when exporting | No | Case K checks tenant-specific splits, postings, trial balances and history. |
| Build generic, composable charge and accounting interpreters | Potentially yes | Allowed and desirable. The suite tests whether composition and historical scope are correct, not whether generic code was used. |

The first three rows are important: the benchmark must survive correct use of
the strongest known approaches. It would be misguided to force microservices,
disallow recomputation or demand more modules merely to make the code harder.

## Concrete Differences That Justify The Pivots

| Pivot | Previously sufficient representation | New fact that makes it insufficient | Cheap discriminating case |
|---|---|---|---|
| Single service to bundle | Charge price and service schedule | A zero-priced line carries an accepted distinct promise | Case A |
| Individual usage to shared tariff | Per-project quantity and price | Another member changes the whole group's unit price | Case C |
| Usage charges to enterprise rights | One amount owed per consumer | Another party sells paid face at a distinct basis | Cases D/I |
| Fixed terms to restructuring | One allocation retained forever | Remaining-only and cumulative treatments require different targets | Cases F/G |
| Current records to corrected history | Latest invoice and current wallet | One fact revision changes prior funding and later consumption while cash remains real | Cases H/I/J |
| Scalar subscription to merchant-configured plans | One fee and renewal date | A base charge, licensed units and measured usage have different calculations and triggers | Cases L/N |
| Single discount to scoped discount policies | One net price | Ordering and redistribution change another charge even for one customer | Case M |
| Uniform ledger to tenant accounting | Seven renamed accounts | Account/segment splits and versions change actual journals without changing economics | Case K |

Group pricing is opt-in under an explicit enterprise agreement. It never pools
unrelated customers merely because they use the same product. The all-units
volume tariff in Case C is distinct from graduated tiers. It has a discount
threshold; this is a real pricing shape, not a universal billing default.
[Zuora volume pricing](https://docs.zuora.com/en/zuora-billing/set-up-zuora-billing/build-product-and-prices/charge-models---configure-any-pricing/volume-pricing).

## Risks Still Present

**A feature inventory can miss the product's lifecycle.** A price calculation
needs a bill-run selection rule, a document-producing operation, settlement and
an accounting consequence. Each correction needs a defined continuation. The
[lifecycle review](LIFECYCLE.md) follows those dependencies and records what must
not change on other branches. It does not force a pipeline implementation.

Bill runs and ordinary memos are basic product completeness, not a new frontier
difficulty claim. The useful tests contrast equal-looking outcomes with different
continuations: a full credit versus reversal, or net-zero documents that leave
different coverage and revenue. Adding CRUD screens without those continuations
would increase work without establishing semantic pressure.

**The formulas may be easy for Astra.** Relative SSP allocation is simple.
Double entry is familiar. Their combination may be implemented correctly at low
effort. The proposed screen must be allowed to reject the difficulty hypothesis.

**The packet can accidentally provide the implementation.** Requirements need
precise behavior and conventions, but not a prescribed database schema, function
decomposition or full list of hidden impact paths. Candidate examples should
teach the rules; the private panel should compose them with different data.
Do not hide an essential rule merely to avoid teaching it.

**Accounting may become arbitrary vocabulary.** Every named account and treatment
needs an externally meaningful distinction and a worked posting. The synthetic
policy explicitly supplies judgment. It is not fair to expect undocumented
vendor defaults or to call one generally reasonable accounting policy wrong.

**Feature silos could masquerade as one complex system.** Isolated allocation,
usage and ledger tests are insufficient. Case I and its amended-bundle continuation
must actually use the shared records and check resulting documents and journals.
Keep independently initialized cases too, so one integration failure does not
hide all the economic rules.

**Configuration can add administration without depth.** A thousand accounts or
products is not harder if one correct lookup handles all of them. Use several
contrasting merchants and change their configurations on the same artifact.
The useful pressure is in composed choices: allowance before tiers, cap before
discount, scoped discount before funding, price amendment before revenue
remeasurement, and retained or current account rules after reclassification.
Test these crossings, including valid combinations not illustrated by the
candidate's merchant examples. No fixture names may imply undocumented rules.

**The cost could grow before signal appears.** Do not add tax, currency conversion,
unbounded DSLs, a payment optimizer or a large operational simulator. The seven
releases are still a substantial build; their runtime is unknown. Measure the
first screen rather than asserting it will fit a three-hour target.

## Ambiguities Resolved In The Proposal

| Potential disagreement | Chosen policy |
|---|---|
| Expiry means last usable or first unavailable day | Explicit `ends_before`; end is unavailable |
| Volume versus graduated tiers | Separate tariff types with formulas and boundary examples |
| Which customer's usage affects another | Only explicitly shared pricing groups |
| One paid dollar or one face dollar is recognized | Allocated consideration basis determines revenue |
| Missing SSP/progress is zero | Hold/unknown; explicit zero progress is different |
| Invoice payment controls recognition | Performance controls recognition; collection is separate |
| A changed price always rewrites history | Separate source correction, prospective amendment and cumulative remeasurement |
| Any parent can see every child's usage | Explicit customer visibility; payer and hierarchy alone do not confer all access |
| Posted history versus recalculated truth | Immutable journal/document history and separate corrected economics |
| A balanced ledger is a correct ledger | Compare required account, arrangement, obligation, period and source effects |
| Any credit is cash the customer can withdraw | Apply to referenced unpaid AR first; preserve cash-backed versus restricted credit provenance on unapplication |
| Target, invoice and posting dates are interchangeable | Due-date selection, document date and open-period accounting are separate |
| Credit, cancellation and reversal are the same transition | Draft cancellation has no financial effects; commercial memos retain coverage; billing reversal releases it |
| All proration scales the same quantity | Recurring fee, usage amount and included-unit allowance have explicit separate rules |

Exact API schemas and the role matrix remain part of later implementation. They
must be specified before candidate runs; this review is not a claim that a prose
proposal is already an executable, ambiguity-free contract.

## Evidence Provenance

The numeric observations above were checked against these reports in the Sweat
Bench working repository on 13 September 2026. They are prior investigations,
not newly rerun candidate experiments. Some supporting v7 trajectories are local
research artifacts rather than a public benchmark release. Paths below are
relative to that repository; hashes identify the reviewed report revisions.

| Report | SHA-256 |
|---|---|
| `evaluation/results/v6/ASTRA_DEEP_DIVE.md` | `4945803f0ccf14e9a4cbe842f8170840402fcf6ddba0114c65f34dabe161ae34` |
| `evaluation/results/v7/rebuild-screen-01/report.md` | `92422f1a0d2c4c29fc3b6413218f0a399ffab2bdf9627de41f9c3c5620340563` |
| `evaluation/results/v7/evolution-comparison-03/report.md` | `425f1316b19436d39f7f3794cc0743b357f073f0b8f3d96aaa96195fd77ba2f1` |
| `evaluation/results/v7/shared-commitments-screen-01/README.md` | `01294a3d3cacaee959573f628060db08889d728f383a0e160bf05fb143c79867` |
| `evaluation/results/v7/service-packages-comparison-02/README.md` | `318e08ac45120cf6db43efaddbcd9a43ec7d7111c70e593a37cd45c14f1fd155` |
| `evaluation/results/v7/shared-commitments-screen-01/SATURATION_REVIEW.md` | `ca44bfae22daaa9ac3865fb3d5f7c2f75e0982e3ea8f92175ef91e90d88d8396` |

The [v6 dashboard](https://kkondaurov.github.io/sweatbench/#findings) and
[published source archive](https://github.com/kkondaurov/sweatbench-runs) provide
public context. This repository does not republish private sessions or imply
that every local diagnostic is independently reproducible from those archives.
