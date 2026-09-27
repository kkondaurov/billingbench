"""0.3 scope and packet order. Legacy helpers are isolated; unselected cases never run."""

from dataclasses import replace
from . import m1, m2, m3, m4, m5, m6, integrity, interactions
from . import funding_interactions, lifecycle_interactions, accounting_interactions, continuation_interactions
from . import v02, policies, reviewed_challenges, metering_evolution
from .suite import CASES

# Release assignments reflect the public 0.2 packets, not old M-number comments.
RELEASES = {
    1: """
subscription-lifecycle licensed-included licensed-at-included half-cent-tie
commercial-memo-backing close-and-cumulative-cents tenant-roles-pagination
mutation-replay split-chart bill-run-held-scope-recovery currency-isolation
draft-cancel-and-competing-coverage separate-positions-not-customer-net
invoice-grouping-payer zero-price-coverage account-routing-missing-context
account-routing-conflicting account-routing-identical commercial-credit-separate-position
rounded-correction-routing-original rounded-correction-routing-current
one-event-two-product-coverage interaction-two-feeds-independent-fixed-charge
interaction-source-typed-idempotency interaction-literal-context-segment
interaction-one-time-acceptance-null-window interaction-held-run-new-posting-month
interaction-saved-partial-competing-sweep interaction-partial-period-performance
allocated-zero-display-delivery billed-ssp-cumulative-cents customer-deal-redaction
interaction-allocation-display-0-split-0 interaction-allocation-display-1-split-1
interaction-split-posting-hold-recovery-close cold-first-retry competing-cash-applications
v02-linear-withdrawal-and-empty-completion
""",
    2: """
reverse-rebill memo-compensation source-revisions fixed-budget-redistribution
partial-budget-actual_day partial-budget-fixed atomic-subscription-order
zero-net-amendment-result quantity-amendment cancellation-credit-reversal
interaction-closed-usage-rebill-revised interaction-closed-usage-rebill-unchanged
interaction-shared-discount-incomplete-usage
interaction-commercial-credit-cash-0 interaction-commercial-credit-cash-10000
interaction-paid-credit-compensation-0 interaction-paid-credit-compensation-100
""",
    3: """
volume-9_999999 volume-10 volume-10_000001 paid-face-basis-expiry
promotion-priority-overage payer-policy-old-debt interaction-three-cent-funded-basis
interaction-funding-bill-first interaction-funding-recognize-first
interaction-grant-reverse-source-rebill interaction-grant-customer-redaction
""",
    4: """
concession-termination-settlement prospective-position-50000 prospective-position-100000
successor-rebill-terminate successor-rebill-terminate-default-chart
shared-pricing-rights-replacement bundled-paid-capacity
interaction-two-successors-original-rebill-termination
interaction-prospective-unissued-old-earned interaction-high-precision-ssp
interaction-concession-termination-retained-27000 interaction-concession-termination-retained-20000
interaction-scheduled-capacity-incomplete-boundary
interaction-scheduled-capacity-needs-prior-recognition
""",
    5: """
correction-through-replacement expired-basis-category-correction
reclassification-correction-original reclassification-correction-current
paid-correction-refund-next-revision historical-fixed-budget-redistribution
closed-current-reconciliation frozen-export-routing-original frozen-export-routing-current
export-lost-response-restart export-preaccept-recovery
interaction-pool-correction-10-discount-1-funding-1
interaction-pool-correction-41-discount-1-funding-1
interaction-pool-correction-10-discount-0-funding-1
interaction-pool-correction-10-discount-1-funding-0
interaction-retained-rights-correction-reclass-0-settled-0
interaction-retained-rights-correction-reclass-0-settled-1
interaction-retained-rights-correction-reclass-1-settled-0
interaction-two-rights-replacements-termination-correction
interaction-paid-usage-fixed-commercial-memo
interaction-earlier-recognition-does-not-reverse interaction-literal-charge-key-correction
interaction-report-opening-and-correction-month
interaction-freed-capacity-displaces-later-overage
interaction-carried-basis-fraction-and-expiry interaction-lost-export-then-correction
interaction-held-correction-new-month interaction-correction-other-tenant-isolation
v02-debtor-boundary-self v02-debtor-boundary-parent
v02-debtor-control-self v02-debtor-control-parent
v02-correction-refund-restoration v02-correction-token-and-isolation
""",
}

GROUPS = {
    "billing_settlement": {"B02", "B03", "B05", "B07", "B08", "B29", "B33", "B34", "B35", "B36"},
    "changed_coverage": {"B09", "B10", "B11", "B12"},
    "shared_ownership": {"B17", "B18", "B19"},
    "retained_agreements": {"B16", "B21", "B22", "B23", "B24", "B25", "B26"},
    "revenue_accounting": {"B04", "B13", "B14", "B15", "B27", "B28", "B30", "B31", "B32"},
    "durability_delivery": {"I01", "I02", "I03", "I04"},
}


def selected():
    result = {}
    for milestone, keys in RELEASES.items():
        for key in keys.split():
            if key in result:
                raise ValueError(f"Duplicate 0.2 case: {key}")
            original = CASES[key]
            group = next(name for name, families in GROUPS.items() if original.family in families)
            result[key] = replace(original, milestone=milestone, family=group,
                                  criteria=(f"0.2-M{milestone}", original.family))
    return result


METERING = {
    'one-event-two-product-coverage', 'interaction-two-feeds-independent-fixed-charge',
    'interaction-source-typed-idempotency', 'v02-linear-withdrawal-and-empty-completion',
    'source-revisions', 'interaction-closed-usage-rebill-revised',
    'interaction-closed-usage-rebill-unchanged', 'interaction-shared-discount-incomplete-usage',
}
EXPORT = {'frozen-export-routing-original', 'frozen-export-routing-current',
          'export-lost-response-restart', 'export-preaccept-recovery', 'interaction-lost-export-then-correction'}
for release, keys in RELEASES.items():
    RELEASES[release] = ' '.join(key for key in keys.split() if key not in EXPORT and key not in METERING)
RELEASES[3] += ' ' + ' '.join(sorted(METERING))
SELECTED = {key: replace(c, criteria=(f'0.3-M{c.milestone}', *c.criteria[1:])) for key, c in selected().items()}
for key, c in CASES.items():
    if key.startswith(('v03-policy-', 'v03-metering-')):
        SELECTED[key] = replace(c, family='policy_evolution', criteria=(f'0.3-M{c.milestone}', *c.criteria))

from .suite import Case
for split in (False, True):
    key = f'v03-source-ownership-{1+int(split)}-invoices-two-successors'
    SELECTED[key] = Case(key, 4, 'retained_agreements', ('0.3-M4', 'source-ownership'),
        'Reverse one original invoice after two replacements; retain the unrelated new sale',
        reviewed_challenges.checked(lambda c, s=split: reviewed_challenges.source_history(c, s, 2)))
for route, reclass, policy, release in (
        ('memo', True, 'original', 5), ('term', True, 'original', 5)):
    key = f'v03-routing-{route}-{policy}-reclass-{int(reclass)}'
    SELECTED[key] = Case(key, release, 'revenue_accounting', (f'0.3-M{release}', 'routing'),
        'A commercial change uses accepted accounting routing, not only a correct net balance',
        reviewed_challenges.checked(lambda c, r=route, x=reclass, p=policy: reviewed_challenges.routes(c, r, x, p)))

# Preserve inherited case keys for before/after attribution, with 0.4 criteria.
SELECTED = {key: replace(c, criteria=(f'0.4-M{c.milestone}', *c.criteria[1:]))
            for key, c in SELECTED.items()}
from . import fx
from .combined import CASES as COMBINED
for c in COMBINED:
    key = 'v04-' + c.key
    SELECTED[key] = replace(c, key=key, family='combined_regression', criteria=('0.4-M5', 'combined'))

# 0.5 retains M1-M5 case identities and rules, with versioned criteria only.
SELECTED = {key: replace(c, criteria=(f'0.5-M{c.milestone}', *c.criteria[1:]))
            for key, c in SELECTED.items()}
assert all(c.milestone <= 5 for c in SELECTED.values())
