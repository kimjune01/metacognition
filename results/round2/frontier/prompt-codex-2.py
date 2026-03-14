def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from collections import deque
    from functools import lru_cache

    if n < 0:
        return []
    if n == 0:
        return []

    adj_graph = [set() for _ in range(n)]
    diff_pairs = set()
    lt_pairs = []

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            return []
        if typ == "adj":
            adj_graph[i].add(j)
            adj_graph[j].add(i)
        elif typ == "diff":
            diff_pairs.add((i, j) if i < j else (j, i))
        elif typ == "lt":
            lt_pairs.append((i, j))
        else:
            return []

    for v in range(n):
        if len(adj_graph[v]) > 2:
            return []

    comp_id = [-1] * n
    components = []

    for start in range(n):
        if comp_id[start] != -1:
            continue

        if not adj_graph[start]:
            comp_id[start] = len(components)
            components.append([start])
            continue

        stack = [start]
        nodes = []
        comp_index = len(components)
        comp_id[start] = comp_index
        while stack:
            u = stack.pop()
            nodes.append(u)
            for v in adj_graph[u]:
                if comp_id[v] == -1:
                    comp_id[v] = comp_index
                    stack.append(v)

        if len(nodes) > 1:
            endpoints = [v for v in nodes if len(adj_graph[v]) == 1]
            if len(endpoints) != 2:
                return []
            path = []
            prev = -1
            cur = endpoints[0]
            while True:
                path.append(cur)
                nxt = [x for x in adj_graph[cur] if x != prev]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
            if len(path) != len(nodes):
                return []
            components.append(path)
        else:
            components.append(nodes)

    m = len(components)
    pos_in_comp = {}
    for cid, path in enumerate(components):
        for idx, node in enumerate(path):
            pos_in_comp[node] = idx

    allowed_orients = []
    for path in components:
        if len(path) == 1:
            allowed_orients.append([0])
        else:
            allowed_orients.append([0, 1])

    pred_mask = [0] * m
    lt_dir = {}

    for i, j in lt_pairs:
        ci, cj = comp_id[i], comp_id[j]
        if ci == cj:
            pi, pj = pos_in_comp[i], pos_in_comp[j]
            new_allowed = []
            for orient in allowed_orients[ci]:
                ii = pi if orient == 0 else len(components[ci]) - 1 - pi
                jj = pj if orient == 0 else len(components[ci]) - 1 - pj
                if ii < jj:
                    new_allowed.append(orient)
            if not new_allowed:
                return []
            allowed_orients[ci] = new_allowed
        else:
            if (cj, ci) in lt_dir:
                return []
            lt_dir[(ci, cj)] = True

    for ci, cj in lt_dir:
        pred_mask[cj] |= 1 << ci

    for i, j in diff_pairs:
        ci, cj = comp_id[i], comp_id[j]
        if ci == cj and abs(pos_in_comp[i] - pos_in_comp[j]) == 1:
            return []

    def boundary_nodes(cid, orient):
        path = components[cid]
        if orient == 0:
            return path[0], path[-1]
        return path[-1], path[0]

    def forbidden_transition(a_c, a_o, b_c, b_o):
        _, a_last = boundary_nodes(a_c, a_o)
        b_first, _ = boundary_nodes(b_c, b_o)
        key = (a_last, b_first) if a_last < b_first else (b_first, a_last)
        return key in diff_pairs

    all_mask = (1 << m) - 1

    @lru_cache(maxsize=None)
    def dfs(mask, last_c, last_o):
        if mask == all_mask:
            return ()

        for c in range(m):
            if mask & (1 << c):
                continue
            if pred_mask[c] & ~mask:
                continue
            for o in allowed_orients[c]:
                if last_c != -1 and forbidden_transition(last_c, last_o, c, o):
                    continue
                tail = dfs(mask | (1 << c), c, o)
                if tail is not None:
                    return ((c, o),) + tail
        return None

    order = dfs(0, -1, 0)
    if order is None:
        return []

    slot_order = []
    for cid, orient in order:
        path = components[cid]
        if orient == 0:
            slot_order.extend(path)
        else:
            slot_order.extend(reversed(path))

    if len(slot_order) != n:
        return []

    assignment = [0] * n
    for value, slot in enumerate(slot_order, 1):
        assignment[slot] = value

    return assignment