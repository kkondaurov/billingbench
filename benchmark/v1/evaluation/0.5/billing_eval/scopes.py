"""Resolve published scope membership without interpreting opaque identifiers."""
from .checks import equal, require


def scope_members(deals):
    members = {}
    for deal in deals:
        published = deal.get('scope_keys') or {}
        promises = published.get('promises', {})
        for scope in promises.values():
            members[scope] = frozenset((scope,))
        for group in deal.get('groups', []):
            scope = published.get('groups', {}).get(group['key'])
            keys = [p['key'] for p in group['promises']]
            if scope and keys and all(key in promises for key in keys):
                members[scope] = frozenset(promises[key] for key in keys)
    return members


def selected(members, scope):
    return members.get(scope, frozenset((scope,)))


def lineage(rows, transfers, original, deals):
    members = scope_members(deals)
    reached = set()
    for scope in (*original.get('scope_keys', {}).get('groups', {}).values(),
                  *original.get('scope_keys', {}).get('promises', {}).values(),
                  *(u['scope_key'] for u in rows if u.get('deal_id') == original['id'])):
        reached.update(selected(members, scope))
    while True:
        previous = set(reached)
        for transfer in transfers:
            if selected(members, transfer['predecessor_scope_key']) <= reached:
                reached.update(selected(members, transfer['successor_scope_key']))
        if previous == reached:
            break
    return [u for u in rows if u.get('deal_id') == original['id'] or
            selected(members, u['scope_key']) <= reached]


def chain_carries(transfers, deals, scopes, dates, expected):
    members = scope_members(deals)
    edges = [(selected(members, a), selected(members, b), date)
             for a, b, date in zip(scopes, scopes[1:], dates)]
    totals = [0] * len(edges)
    seen = set()
    for transfer in transfers:
        edge = (selected(members, transfer['predecessor_scope_key']),
                selected(members, transfer['successor_scope_key']), transfer['effective_on'])
        require(edge in edges, 'replacement transfer leaves the published rights chain')
        index = edges.index(edge)
        seen.add(index)
        totals[index] += transfer['consideration_carry_minor']
    equal(seen, set(range(len(edges))), 'all replacement edges are represented')
    equal(totals, expected, 'reconstructed outgoing carries')
