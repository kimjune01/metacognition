def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from collections import defaultdict, deque
    from functools import lru_cache

    if n < 0:
        return []
    if n == 0:
        return []

    adj_graph = [set() for _ in range(n)]
    lt_pairs = []
    diff_pairs = set()

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            return []
        if typ == "adj":
            adj_graph[i].add(j)
            adj_graph[j].add(i)
        elif typ == "lt":
            lt_pairs.append((i, j))
        elif typ == "diff":
            a, b = (i, j) if i < j else (j, i)
            diff_pairs.add((a, b))
        else:
            return []

    for u in range(n):
        if len(adj_graph[u]) > 2:
            return []

    comp_id = [-1] * n
    components = []
    for start in range(n):
        if comp_id[start] != -1:
            continue
        q = deque([start])
        nodes = []
        comp_id[start] = len(components)
        while q:
            u = q.popleft()
            nodes.append(u)
            for v in adj_graph[u]:
                if comp_id[v] == -1:
                    comp_id[v] = comp_id[start]
                    q.append(v)
        components.append(nodes)

    block_nodes = []
    for cid, nodes in enumerate(components):
        if len(nodes) == 1:
            block_nodes.append(nodes[:])
            continue
        deg1 = [u for u in nodes if len(adj_graph[u]) == 1]
        deg2 = [u for u in nodes if len(adj_graph[u]) == 2]
        if len(deg1) != 2 or len(deg1) + len(deg2) != len(nodes):
            return []
        order = []
        prev = -1
        cur = deg1[0]
        while True:
            order.append(cur)
            nxt = [v for v in adj_graph[cur] if v != prev]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
        if len(order) != len(nodes):
            return []
        block_nodes.append(order)

    m = len(block_nodes)
    node_pos_in_block = {}
    for b, nodes in enumerate(block_nodes):
        for idx, u in enumerate(nodes):
            node_pos_in_block[u] = (b, idx)

    for a, b in diff_pairs:
        ba, pa = node_pos_in_block[a]
        bb, pb = node_pos_in_block[b]
        if ba == bb and abs(pa - pb) == 1:
            return []

    block_orders = []
    valid_oris = []
    for b, nodes in enumerate(block_nodes):
        orders = [nodes]
        if len(nodes) > 1:
            orders.append(list(reversed(nodes)))
        keep = []
        for ori, order in enumerate(orders):
            pos = {u: idx for idx, u in enumerate(order)}
            ok = True
            for i, j in lt_pairs:
                bi, _ = node_pos_in_block[i]
                bj, _ = node_pos_in_block[j]
                if bi == b and bj == b and pos[i] >= pos[j]:
                    ok = False
                    break
            if ok:
                keep.append(ori)
        if not keep:
            return []
        block_orders.append(orders)
        valid_oris.append(keep)

    pred_masks = [0] * m
    for i, j in lt_pairs:
        bi, _ = node_pos_in_block[i]
        bj, _ = node_pos_in_block[j]
        if bi == bj:
            continue
        if bi == bj:
            return []
        pred_masks[bj] |= 1 << bi

    indeg = [0] * m
    succ = [[] for _ in range(m)]
    for b in range(m):
        mask = pred_masks[b]
        x = mask
        while x:
            lsb = x & -x
            p = lsb.bit_length() - 1
            succ[p].append(b)
            indeg[b] += 1
            x -= lsb
    dq = deque([b for b in range(m) if indeg[b] == 0])
    seen = 0
    indeg2 = indeg[:]
    while dq:
        u = dq.popleft()
        seen += 1
        for v in succ[u]:
            indeg2[v] -= 1
            if indeg2[v] == 0:
                dq.append(v)
    if seen != m:
        return []

    diff_lookup = diff_pairs

    def boundary_ok(b1, o1, b2, o2):
        u = block_orders[b1][o1][-1]
        v = block_orders[b2][o2][0]
        a, b = (u, v) if u < v else (v, u)
        return (a, b) not in diff_lookup

    all_used = (1 << m) - 1

    @lru_cache(maxsize=None)
    def dfs(used_mask, last_block, last_ori):
        if used_mask == all_used:
            return ()
        available = []
        for b in range(m):
            if (used_mask >> b) & 1:
                continue
            if pred_masks[b] & ~used_mask:
                continue
            available.append(b)
        available.sort(key=lambda b: (len(valid_oris[b]), -len(succ[b]), len(block_nodes[b])))

        for b in available:
            for ori in valid_oris[b]:
                if last_block != -1 and not boundary_ok(last_block, last_ori, b, ori):
                    continue
                tail = dfs(used_mask | (1 << b), b, ori)
                if tail is not None:
                    return ((b, ori),) + tail
        return None

    plan = dfs(0, -1, 0)
    if plan is None:
        return []

    sequence = []
    for b, ori in plan:
        sequence.extend(block_orders[b][ori])

    if len(sequence) != n:
        return []

    ans = [0] * n
    for value, slot in enumerate(sequence, 1):
        ans[slot] = value

    return ans