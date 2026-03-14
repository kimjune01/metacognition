def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    adj_graph = [set() for _ in range(n)]
    lt_constraints = []
    diff_pairs = set()
    same_comp_checks = [[] for _ in range(n)]  # temporary bucket by slot, reused later

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
            a, b = (i, j) if i < j else (j, i)
            diff_pairs.add((a, b))
        elif typ == "adj":
            if i == j:
                return []
            adj_graph[i].add(j)
            adj_graph[j].add(i)
        else:
            return []

    for v in range(n):
        if len(adj_graph[v]) > 2:
            return []

    comp_id = [-1] * n
    components = []
    for s in range(n):
        if comp_id[s] != -1:
            continue
        stack = [s]
        nodes = []
        comp_id[s] = len(components)
        while stack:
            u = stack.pop()
            nodes.append(u)
            for v in adj_graph[u]:
                if comp_id[v] == -1:
                    comp_id[v] = comp_id[s]
                    stack.append(v)

        if len(nodes) == 1:
            components.append([nodes[0]])
            continue

        edge_count = sum(len(adj_graph[u]) for u in nodes) // 2
        if edge_count != len(nodes) - 1:
            return []

        starts = [u for u in nodes if len(adj_graph[u]) == 1]
        if len(starts) != 2:
            return []

        start = starts[0]
        order = []
        prev = -1
        cur = start
        while True:
            order.append(cur)
            nxt = [v for v in adj_graph[cur] if v != prev]
            if not nxt:
                break
            if len(nxt) != 1:
                return []
            prev, cur = cur, nxt[0]

        if len(order) != len(nodes):
            return []
        components.append(order)

    m = len(components)

    internal_constraints = [[] for _ in range(m)]
    cross_lt = set()
    forbidden_boundary = [set() for _ in range(n)]

    for i, j in lt_constraints:
        ci, cj = comp_id[i], comp_id[j]
        if ci == cj:
            internal_constraints[ci].append(("lt", i, j))
        else:
            cross_lt.add((ci, cj))

    for a, b in diff_pairs:
        ca, cb = comp_id[a], comp_id[b]
        if ca == cb:
            internal_constraints[ca].append(("diff", a, b))
        else:
            forbidden_boundary[a].add(b)
            forbidden_boundary[b].add(a)

    for u in range(n):
        for v in adj_graph[u]:
            if u < v:
                cu, cv = comp_id[u], comp_id[v]
                if cu != cv:
                    return []
                internal_constraints[cu].append(("adj", u, v))

    options = []
    for cid, base in enumerate(components):
        cand = [base]
        if len(base) > 1:
            rev = list(reversed(base))
            if rev != base:
                cand.append(rev)

        valid = []
        for seq in cand:
            pos = {slot: idx for idx, slot in enumerate(seq)}
            ok = True
            for typ, i, j in internal_constraints[cid]:
                d = abs(pos[i] - pos[j])
                if typ == "lt":
                    if pos[i] >= pos[j]:
                        ok = False
                        break
                elif typ == "diff":
                    if d < 2:
                        ok = False
                        break
                else:  # adj
                    if d != 1:
                        ok = False
                        break
            if ok:
                valid.append((seq, seq[0], seq[-1]))

        if not valid:
            return []
        options.append(valid)

    pred_masks = [0] * m
    for a, b in cross_lt:
        if a == b:
            return []
        pred_masks[b] |= 1 << a

    full_mask = (1 << m) - 1
    memo = {}

    def dfs(mask: int, last_end: int) -> list[tuple[int, int]] | None:
        key = (mask, last_end)
        if key in memo:
            return memo[key]
        if mask == full_mask:
            memo[key] = []
            return []

        available = []
        for cid in range(m):
            bit = 1 << cid
            if mask & bit:
                continue
            if pred_masks[cid] & ~mask:
                continue
            available.append(cid)

        available.sort(key=lambda c: (len(options[c]), len(components[c])))

        for cid in available:
            bit = 1 << cid
            for opt_idx, (_, start, end) in enumerate(options[cid]):
                if last_end != -1 and start in forbidden_boundary[last_end]:
                    continue
                rest = dfs(mask | bit, end)
                if rest is not None:
                    ans = [(cid, opt_idx)] + rest
                    memo[key] = ans
                    return ans

        memo[key] = None
        return None

    plan = dfs(0, -1)
    if plan is None:
        return []

    order = []
    for cid, opt_idx in plan:
        order.extend(options[cid][opt_idx][0])

    if len(order) != n:
        return []

    result = [0] * n
    for rank, slot in enumerate(order, 1):
        result[slot] = rank
    return result