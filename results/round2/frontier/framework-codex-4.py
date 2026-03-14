def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    adj_neighbors = [set() for _ in range(n)]
    diff_pairs = [set() for _ in range(n)]
    lt_constraints = []

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt_constraints.append((i, j))
        elif typ == "diff":
            if i == j:
                return []
            diff_pairs[i].add(j)
            diff_pairs[j].add(i)
        elif typ == "adj":
            if i == j:
                return []
            adj_neighbors[i].add(j)
            adj_neighbors[j].add(i)
        else:
            return []

    for v in range(n):
        if len(adj_neighbors[v]) > 2:
            return []

    comp_id = [-1] * n
    blocks = []
    pos_in_block = [0] * n

    for start in range(n):
        if comp_id[start] != -1:
            continue

        stack = [start]
        nodes = []
        comp_idx = len(blocks)
        comp_id[start] = comp_idx

        while stack:
            v = stack.pop()
            nodes.append(v)
            for u in adj_neighbors[v]:
                if comp_id[u] == -1:
                    comp_id[u] = comp_idx
                    stack.append(u)

        if len(nodes) == 1:
            order = nodes
        else:
            endpoints = [v for v in nodes if len(adj_neighbors[v]) == 1]
            if len(endpoints) != 2:
                return []
            order = []
            prev = -1
            cur = endpoints[0]
            for _ in range(len(nodes)):
                order.append(cur)
                nxt = None
                for u in adj_neighbors[cur]:
                    if u != prev:
                        nxt = u
                        break
                prev, cur = cur, nxt
                if cur is None:
                    break
            if len(order) != len(nodes):
                return []

        for idx, v in enumerate(order):
            pos_in_block[v] = idx
        blocks.append(order)

    m = len(blocks)
    internal_lt = [[] for _ in range(m)]

    for i, j in lt_constraints:
        bi = comp_id[i]
        bj = comp_id[j]
        if bi == bj:
            internal_lt[bi].append((i, j))

    feasible_orients = [[] for _ in range(m)]
    for b, order in enumerate(blocks):
        size = len(order)
        if size == 1:
            feasible_orients[b] = [0]
            continue

        ok = [True, True]
        for i in order:
            for j in diff_pairs[i]:
                if comp_id[j] == b and pos_in_block[i] + 1 == pos_in_block[j]:
                    return []

        for orient in (0, 1):
            for i, j in internal_lt[b]:
                pi = pos_in_block[i] if orient == 0 else size - 1 - pos_in_block[i]
                pj = pos_in_block[j] if orient == 0 else size - 1 - pos_in_block[j]
                if not (pi < pj):
                    ok[orient] = False
                    break

        feasible_orients[b] = [o for o in (0, 1) if ok[o]]
        if not feasible_orients[b]:
            return []

    succ = [set() for _ in range(m)]
    indeg = [0] * m

    for i, j in lt_constraints:
        bi = comp_id[i]
        bj = comp_id[j]
        if bi != bj and bj not in succ[bi]:
            succ[bi].add(bj)
            indeg[bj] += 1

    first_slot = [[0, 0] for _ in range(m)]
    last_slot = [[0, 0] for _ in range(m)]
    for b, order in enumerate(blocks):
        first_slot[b][0] = order[0]
        last_slot[b][0] = order[-1]
        first_slot[b][1] = order[-1]
        last_slot[b][1] = order[0]

    used = [False] * m
    available = {b for b in range(m) if indeg[b] == 0}
    sequence = []

    def dfs(prev_end_slot: int | None) -> bool:
        if len(sequence) == m:
            return True
        if not available:
            return False

        candidates = []
        for b in list(available):
            orients = []
            for o in feasible_orients[b]:
                if prev_end_slot is None or first_slot[b][o] not in diff_pairs[prev_end_slot]:
                    orients.append(o)
            if orients:
                candidates.append((len(orients), -len(succ[b]), b, orients))

        if not candidates:
            return False

        candidates.sort()

        for _, _, b, orients in candidates:
            available.remove(b)
            used[b] = True
            changed = []
            for nb in succ[b]:
                indeg[nb] -= 1
                if indeg[nb] == 0 and not used[nb]:
                    available.add(nb)
                    changed.append(nb)

            for o in orients:
                sequence.append((b, o))
                if dfs(last_slot[b][o]):
                    return True
                sequence.pop()

            for nb in changed:
                available.remove(nb)
            for nb in succ[b]:
                indeg[nb] += 1
            used[b] = False
            available.add(b)

        return False

    if not dfs(None):
        return []

    ans = [0] * n
    value = 1
    for b, o in sequence:
        order = blocks[b] if o == 0 else list(reversed(blocks[b]))
        for slot in order:
            ans[slot] = value
            value += 1
    return ans