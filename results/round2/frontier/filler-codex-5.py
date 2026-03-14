def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    lt_edges = []
    diff_pairs = set()
    adj_pairs = set()

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            if typ == "lt" or typ == "adj":
                return []
            continue
        a, b = (i, j) if i < j else (j, i)
        if typ == "lt":
            lt_edges.append((i, j))
        elif typ == "diff":
            diff_pairs.add((a, b))
        elif typ == "adj":
            adj_pairs.add((a, b))
        else:
            return []

    if diff_pairs & adj_pairs:
        return []

    adj_graph = [[] for _ in range(n)]
    for a, b in adj_pairs:
        adj_graph[a].append(b)
        adj_graph[b].append(a)

    for v in range(n):
        if len(adj_graph[v]) > 2:
            return []

    comp_id = [-1] * n
    blocks = []
    visited = [False] * n

    for start in range(n):
        if visited[start]:
            continue
        stack = [start]
        nodes = []
        edge_count = 0
        visited[start] = True
        while stack:
            u = stack.pop()
            nodes.append(u)
            edge_count += len(adj_graph[u])
            for w in adj_graph[u]:
                if not visited[w]:
                    visited[w] = True
                    stack.append(w)
        edge_count //= 2

        if len(nodes) == 1:
            path = [nodes[0]]
        else:
            if edge_count != len(nodes) - 1:
                return []
            endpoints = [v for v in nodes if len(adj_graph[v]) == 1]
            if len(endpoints) != 2:
                return []
            path = []
            prev = -1
            cur = endpoints[0]
            while True:
                path.append(cur)
                nxt = None
                for w in adj_graph[cur]:
                    if w != prev:
                        nxt = w
                        break
                if nxt is None:
                    break
                prev, cur = cur, nxt
            if len(path) != len(nodes):
                return []

        cid = len(blocks)
        for v in path:
            comp_id[v] = cid
        blocks.append(path)

    bcount = len(blocks)

    internal_lt = [[] for _ in range(bcount)]
    pred_masks = [0] * bcount

    for u, v in lt_edges:
        cu = comp_id[u]
        cv = comp_id[v]
        if cu == cv:
            internal_lt[cu].append((u, v))
        else:
            pred_masks[cv] |= 1 << cu

    orientations = []
    for bid, path in enumerate(blocks):
        cand = [path]
        if len(path) > 1:
            cand.append(path[::-1])

        valid = []
        seen = set()
        for seq in cand:
            key = tuple(seq)
            if key in seen:
                continue
            seen.add(key)
            pos = {node: idx for idx, node in enumerate(seq)}
            ok = True
            for u, v in internal_lt[bid]:
                if pos[u] >= pos[v]:
                    ok = False
                    break
            if not ok:
                continue
            for idx in range(len(seq) - 1):
                a, b = seq[idx], seq[idx + 1]
                if (a, b) in diff_pairs or (b, a) in diff_pairs:
                    ok = False
                    break
            if ok:
                valid.append(seq)

        if not valid:
            return []
        orientations.append(valid)

    full_mask = (1 << bcount) - 1
    forbidden_boundary = set()
    for a, b in diff_pairs:
        ca = comp_id[a]
        cb = comp_id[b]
        if ca == cb:
            continue
        forbidden_boundary.add((a, b))
        forbidden_boundary.add((b, a))

    from functools import lru_cache

    @lru_cache(maxsize=None)
    def dfs(done_mask: int, prev_block: int, prev_ori: int):
        if done_mask == full_mask:
            return ()

        for b in range(bcount):
            bit = 1 << b
            if done_mask & bit:
                continue
            if pred_masks[b] & ~done_mask:
                continue

            for o, seq in enumerate(orientations[b]):
                if prev_block != -1:
                    prev_seq = orientations[prev_block][prev_ori]
                    if (prev_seq[-1], seq[0]) in forbidden_boundary:
                        continue
                tail = dfs(done_mask | bit, b, o)
                if tail is not None:
                    return ((b, o),) + tail
        return None

    order = dfs(0, -1, 0)
    if order is None:
        return []

    ranked_slots = []
    for b, o in order:
        ranked_slots.extend(orientations[b][o])

    if len(ranked_slots) != n:
        return []

    result = [0] * n
    for value, slot in enumerate(ranked_slots, 1):
        result[slot] = value
    return result