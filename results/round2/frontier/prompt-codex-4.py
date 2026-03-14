def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from functools import lru_cache

    if n < 0:
        return []
    if n == 0:
        return []

    adj_sets = [set() for _ in range(n)]
    diff_sets = [set() for _ in range(n)]
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
            diff_sets[i].add(j)
            diff_sets[j].add(i)
        elif typ == "adj":
            if i == j:
                return []
            adj_sets[i].add(j)
            adj_sets[j].add(i)
        else:
            return []

    for i in range(n):
        if len(adj_sets[i]) > 2:
            return []
        for j in adj_sets[i]:
            if j in diff_sets[i]:
                return []

    block_id = [-1] * n
    index_in_block = [-1] * n
    blocks = []

    seen = [False] * n
    for start in range(n):
        if seen[start]:
            continue
        if len(adj_sets[start]) == 0:
            seen[start] = True
            block_id[start] = len(blocks)
            index_in_block[start] = 0
            blocks.append([start])
            continue

        comp = []
        stack = [start]
        seen[start] = True
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj_sets[u]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)

        endpoints = [u for u in comp if len(adj_sets[u]) == 1]
        if len(endpoints) != 2:
            return []

        chain = []
        prev = -1
        cur = endpoints[0]
        while True:
            chain.append(cur)
            nxt = [v for v in adj_sets[cur] if v != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]

        if len(chain) != len(comp):
            return []

        b = len(blocks)
        for idx, node in enumerate(chain):
            block_id[node] = b
            index_in_block[node] = idx
        blocks.append(chain)

    m = len(blocks)
    allowed_orients = []
    for chain in blocks:
        k = len(chain)
        ok = [True, True]
        for i, j in lt_pairs:
            if block_id[i] != block_id[j] or block_id[i] != len(allowed_orients):
                continue
            pi = index_in_block[i]
            pj = index_in_block[j]
            if not (pi < pj):
                ok[0] = False
            if not (k - 1 - pi < k - 1 - pj):
                ok[1] = False
        opts = []
        if ok[0]:
            opts.append(0)
        if ok[1]:
            opts.append(1)
        if not opts:
            return []
        allowed_orients.append(opts)

    pred_masks = [0] * m
    for i, j in lt_pairs:
        bi = block_id[i]
        bj = block_id[j]
        if bi == bj:
            continue
        pred_masks[bj] |= 1 << bi

    def first_node(b, o):
        chain = blocks[b]
        return chain[0] if o == 0 else chain[-1]

    def last_node(b, o):
        chain = blocks[b]
        return chain[-1] if o == 0 else chain[0]

    @lru_cache(maxsize=None)
    def dfs(mask: int, last_b: int, last_o: int):
        if mask == (1 << m) - 1:
            return ()

        for b in range(m):
            bit = 1 << b
            if mask & bit:
                continue
            if pred_masks[b] & ~mask:
                continue
            for o in allowed_orients[b]:
                if last_b != -1:
                    if first_node(b, o) in diff_sets[last_node(last_b, last_o)]:
                        continue
                tail = dfs(mask | bit, b, o)
                if tail is not None:
                    return ((b, o),) + tail
        return None

    order = dfs(0, -1, 0)
    if order is None:
        return []

    perm = []
    for b, o in order:
        chain = blocks[b]
        if o == 0:
            perm.extend(chain)
        else:
            perm.extend(reversed(chain))

    if len(perm) != n:
        return []

    ans = [0] * n
    for value, slot in enumerate(perm, 1):
        ans[slot] = value
    return ans