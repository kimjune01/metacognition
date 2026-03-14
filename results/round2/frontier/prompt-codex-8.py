def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from functools import lru_cache

    if n < 0:
        return []
    if n == 0:
        return []

    adj_graph = [set() for _ in range(n)]
    diff = [[False] * n for _ in range(n)]
    lt_pairs = []

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt_pairs.append((i, j))
        elif typ == "diff":
            if i == j:
                return []
            diff[i][j] = diff[j][i] = True
        elif typ == "adj":
            if i == j or diff[i][j]:
                return []
            adj_graph[i].add(j)
            adj_graph[j].add(i)
        else:
            return []

    for v in range(n):
        if len(adj_graph[v]) > 2:
            return []

    block_of = [-1] * n
    blocks = []
    idx_in_block = [None] * n
    seen = [False] * n

    for s in range(n):
        if seen[s]:
            continue
        stack = [s]
        comp = []
        seen[s] = True
        while stack:
            v = stack.pop()
            comp.append(v)
            for u in adj_graph[v]:
                if not seen[u]:
                    seen[u] = True
                    stack.append(u)

        if len(comp) == 1:
            path = [comp[0]]
        else:
            edge_count = sum(len(adj_graph[v]) for v in comp) // 2
            deg1 = [v for v in comp if len(adj_graph[v]) == 1]
            if edge_count != len(comp) - 1 or len(deg1) != 2:
                return []
            start = deg1[0]
            path = []
            prev = -1
            cur = start
            while True:
                path.append(cur)
                nxt = [u for u in adj_graph[cur] if u != prev]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
            if len(path) != len(comp):
                return []

        b = len(blocks)
        blocks.append(path)
        for idx, v in enumerate(path):
            block_of[v] = b
            idx_in_block[v] = idx

    m = len(blocks)
    allowed_orients = []
    start_node = []
    end_node = []

    for b, path in enumerate(blocks):
        if len(path) == 1:
            allowed = [0]
        else:
            allowed = [0, 1]
        allowed_set = set(allowed)

        for i, j in lt_pairs:
            if block_of[i] != b or block_of[j] != b:
                continue
            ii = idx_in_block[i]
            jj = idx_in_block[j]
            if ii >= jj:
                allowed_set.discard(0)
            if ii <= jj:
                allowed_set.discard(1)

        for v in path:
            for u in adj_graph[v]:
                if diff[v][u]:
                    return []
            for u in path:
                if u != v and diff[v][u] and abs(idx_in_block[v] - idx_in_block[u]) == 1:
                    return []

        if not allowed_set:
            return []

        allowed = sorted(allowed_set)
        allowed_orients.append(allowed)
        start_node.append({0: path[0], 1: path[-1]})
        end_node.append({0: path[-1], 1: path[0]})

    pred_masks = [0] * m
    for i, j in lt_pairs:
        bi = block_of[i]
        bj = block_of[j]
        if bi != bj:
            pred_masks[bj] |= 1 << bi

    full_mask = (1 << m) - 1

    @lru_cache(None)
    def dfs(mask: int, prev_end: int):
        if mask == full_mask:
            return ()

        available = [
            b for b in range(m)
            if not (mask >> b) & 1 and (pred_masks[b] & ~mask) == 0
        ]
        available.sort(key=lambda b: (len(allowed_orients[b]), -len(blocks[b])))

        for b in available:
            for o in allowed_orients[b]:
                s = start_node[b][o]
                if prev_end != -1 and diff[prev_end][s]:
                    continue
                e = end_node[b][o]
                suffix = dfs(mask | (1 << b), e)
                if suffix is not None:
                    return ((b, o),) + suffix
        return None

    plan = dfs(0, -1)
    if plan is None:
        return []

    order = []
    for b, o in plan:
        path = blocks[b]
        if o == 0:
            order.extend(path)
        else:
            order.extend(reversed(path))

    if len(order) != n:
        return []

    pos = [0] * n
    for p, slot in enumerate(order):
        pos[slot] = p

    for typ, i, j in constraints:
        if typ == "lt":
            if not (pos[i] < pos[j]):
                return []
        elif typ == "diff":
            if abs(pos[i] - pos[j]) < 2:
                return []
        else:  # adj
            if abs(pos[i] - pos[j]) != 1:
                return []

    return [pos[i] + 1 for i in range(n)]