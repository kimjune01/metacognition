def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    adj_sets = [set() for _ in range(n)]
    lt_pairs = []
    diff_pairs = set()

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            return []
        if typ == "adj":
            adj_sets[i].add(j)
            adj_sets[j].add(i)
        elif typ == "lt":
            lt_pairs.append((i, j))
        elif typ == "diff":
            a, b = (i, j) if i < j else (j, i)
            diff_pairs.add((a, b))
        else:
            return []

    for v in range(n):
        if len(adj_sets[v]) > 2:
            return []

    block_id = [-1] * n
    blocks_nodes = []
    pos_in_block = {}

    visited = [False] * n
    for start in range(n):
        if visited[start]:
            continue

        comp = []
        stack = [start]
        visited[start] = True
        while stack:
            u = stack.pop()
            comp.append(u)
            for w in adj_sets[u]:
                if not visited[w]:
                    visited[w] = True
                    stack.append(w)

        if len(comp) == 1 and not adj_sets[comp[0]]:
            order = [comp[0]]
        else:
            endpoints = [v for v in comp if len(adj_sets[v]) == 1]
            if len(endpoints) != 2:
                return []
            order = []
            prev = -1
            cur = endpoints[0]
            while True:
                order.append(cur)
                nxts = [x for x in adj_sets[cur] if x != prev]
                if not nxts:
                    break
                prev, cur = cur, nxts[0]
            if len(order) != len(comp):
                return []

        bid = len(blocks_nodes)
        blocks_nodes.append(order)
        for idx, node in enumerate(order):
            block_id[node] = bid
            pos_in_block[node] = idx

    for a, b in diff_pairs:
        if block_id[a] == block_id[b]:
            if abs(pos_in_block[a] - pos_in_block[b]) == 1:
                return []

    k = len(blocks_nodes)
    orientations = []
    first_slot = []
    last_slot = []

    for nodes in blocks_nodes:
        opts = [tuple(nodes)]
        if len(nodes) > 1:
            rev = tuple(reversed(nodes))
            if rev != opts[0]:
                opts.append(rev)

        valid_opts = []
        for seq in opts:
            pos = {node: idx for idx, node in enumerate(seq)}
            ok = True
            for a, b in lt_pairs:
                if block_id[a] == block_id[b] == block_id[seq[0]]:
                    if pos[a] >= pos[b]:
                        ok = False
                        break
            if ok:
                valid_opts.append(seq)

        if not valid_opts:
            return []

        orientations.append(valid_opts)
        first_slot.append([seq[0] for seq in valid_opts])
        last_slot.append([seq[-1] for seq in valid_opts])

    prereq = [0] * k
    for a, b in lt_pairs:
        ba, bb = block_id[a], block_id[b]
        if ba != bb:
            prereq[bb] |= 1 << ba

    boundary_ok = {}
    for pb in range(k):
        for po, plast in enumerate(last_slot[pb]):
            for nb in range(k):
                if pb == nb:
                    continue
                for no, nfirst in enumerate(first_slot[nb]):
                    key = (pb, po, nb, no)
                    a, b = (plast, nfirst) if plast < nfirst else (nfirst, plast)
                    boundary_ok[key] = (a, b) not in diff_pairs

    full_mask = (1 << k) - 1
    failed = set()

    def dfs(mask: int, prev_block: int, prev_ori: int):
        if mask == full_mask:
            return []
        state = (mask, prev_block, prev_ori)
        if state in failed:
            return None

        for b in range(k):
            if (mask >> b) & 1:
                continue
            if prereq[b] & ~mask:
                continue
            for o in range(len(orientations[b])):
                if prev_block != -1 and not boundary_ok[(prev_block, prev_ori, b, o)]:
                    continue
                rest = dfs(mask | (1 << b), b, o)
                if rest is not None:
                    return [(b, o)] + rest

        failed.add(state)
        return None

    plan = dfs(0, -1, -1)
    if plan is None:
        return []

    slot_order = []
    for b, o in plan:
        slot_order.extend(orientations[b][o])

    ans = [0] * n
    for value, slot in enumerate(slot_order, 1):
        ans[slot] = value
    return ans