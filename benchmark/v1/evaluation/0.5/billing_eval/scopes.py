"""Resolve published scope membership without interpreting opaque identifiers."""
from .checks import equal, require


def current_transfers(rows):
    """Resolve explicit full-record supersession; retain unmarked signed deltas."""
    require(isinstance(rows, list), 'position transfers: expected collection')
    indexed = {}
    for row in rows:
        require(isinstance(row, dict), 'position transfer: expected object')
        if 'id' in row:
            require(isinstance(row['id'], str) and row['id'], 'invalid transfer ID')
            require(row['id'] not in indexed, 'duplicate transfer ID')
            indexed[row['id']] = row
    graph = {}
    for key, row in indexed.items():
        refs = row.get('corrects_ids', [])
        require(isinstance(refs, list) and all(isinstance(r, str) for r in refs),
                'transfer correction references: expected ID list')
        require(key not in refs, 'self-correcting transfer')
        # References can also name journals or records omitted from a current view.
        graph[key] = [r for r in refs if r in indexed]
    visiting, visited = set(), set()

    def visit(key):
        require(key not in visiting, 'cyclic transfer corrections')
        if key not in visited:
            visiting.add(key)
            for previous in graph[key]:
                visit(previous)
            visiting.remove(key)
            visited.add(key)

    for key in graph:
        visit(key)
    superseded = set()
    for key, refs in graph.items():
        row = indexed[key]
        for ref in refs:
            old = indexed[ref]
            if old.get('current') is False or old.get('status') == 'superseded':
                require(all(row.get(k) == old.get(k) for k in (
                    'predecessor_scope_key', 'successor_scope_key')),
                    'transfer correction crosses an unrelated edge')
                superseded.add(ref)
    for key, row in indexed.items():
        if 'current' in row:
            require(type(row['current']) is bool, 'transfer current flag: expected boolean')
            equal(row['current'], key not in superseded, 'transfer correction lineage/current flag')
        if row.get('status') == 'superseded':
            require(key in superseded, 'superseded transfer lacks a published replacement')
    return [row for row in rows if row.get('id') not in superseded]


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
    transfers = current_transfers(transfers)
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
