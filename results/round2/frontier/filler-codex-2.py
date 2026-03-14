def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    lt_edges = []
    adj_neighbors = [set() for _ in range(n)]
    diff_pairs = set()

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            if typ == 'lt':
                return []
            if typ == 'adj':
                return []
            continue
        if typ == 'lt':
            lt_edges.append((i, j))
        elif typ == 'adj':
            adj_neighbors[i].add(j)
            adj_neighbors[j].add(i)
        elif typ == 'diff':
            a, b = (i, j) if i < j else (j, i)
            diff_pairs.add((a, b))
        else:
            return []

    for v in range(n):
        if len(adj_neighbors[v]) > 2:
            return []

    comp_id = [-1] * n
    components = []
    for start in range(n):
        if comp_id[start] != -1:
            continue
        stack = [start]
        nodes = []
        comp_idx = len(components)
        comp_id[start] = comp_idx
        while stack:
            u = stack.pop()
            nodes.append(u)
            for w in adj_neighbors[u]:
                if comp_id[w] == -1:
                    comp_id[w] = comp_idx
                    stack.append(w)
                elif comp_id[w] != comp_idx:
                    return []
        components.append(nodes)

    oriented_components = []
    node_to_comp = [-1] * n
    node_pos_in_comp = [0] * n

    for cid, nodes in enumerate(components):
        if len(nodes) == 1:
            order = [nodes[0]]
            oriented_components.append([order])
            node_to_comp[nodes[0]] = cid
            node_pos_in_comp[nodes[0]] = 0
            continue

        ends = [v for v in nodes if len(adj_neighbors[v]) == 1]
        if len(ends) != 2:
            return []

        order = []
        prev = -1
        cur = ends[0]
        seen = set()
        while True:
            order.append(cur)
            seen.add(cur)
            nxts = [x for x in adj_neighbors[cur] if x != prev]
            if not nxts:
                break
            if len(nxts) != 1:
                return []
            prev, cur = cur, nxts[0]
            if cur in seen and cur != ends[1]:
                return []

        if len(order) != len(nodes):
            return []

        rev = list(reversed(order))
        oriented_components.append([order, rev])
        for idx, v in enumerate(order):
            node_to_comp[v] = cid
            node_pos_in_comp[v] = idx

    comp_count = len(components)
    lt_comp_edges = set()
    for i, j in lt_edges:
        ci = node_to_comp[i]
        cj = node_to_comp[j]
        if ci == cj:
            oi = node_pos_in_comp[i]
            oj = node_pos_in_comp[j]
            length = len(oriented_components[ci][0])
            if length == 1:
                return []
            forward_ok = oi < oj
            reverse_ok = (length - 1 - oi) < (length - 1 - oj)
            options = []
            if forward_ok:
                options.append(tuple(oriented_components[ci][0]))
            if reverse_ok:
                options.append(tuple(oriented_components[ci][-1]))
            if not options:
                return []
            unique = []
            seen = set()
            for opt in options:
                if opt not in seen:
                    unique.append(list(opt))
                    seen.add(opt)
            oriented_components[ci] = unique
        else:
            lt_comp_edges.add((ci, cj))

    for cid in range(comp_count):
        opts = oriented_components[cid]
        valid_opts = []
        for order in opts:
            pos = {v: idx for idx, v in enumerate(order)}
            ok = True
            for a, b in lt_edges:
                if node_to_comp[a] == cid and node_to_comp[b] == cid:
                    if pos[a] >= pos[b]:
                        ok = False
                        break
            if ok:
                valid_opts.append(order)
        if not valid_opts:
            return []
        oriented_components[cid] = valid_opts

    for a, b in list(diff_pairs):
        if node_to_comp[a] == node_to_comp[b]:
            cid = node_to_comp[a]
            new_opts = []
            for order in oriented_components[cid]:
                pos = {v: idx for idx, v in enumerate(order)}
                if abs(pos[a] - pos[b]) >= 2:
                    new_opts.append(order)
            if not new_opts:
                return []
            oriented_components[cid] = new_opts

    oriented_components = [list({tuple(opt): opt for opt in opts}.values()) for opts in oriented_components]

    comp_nodes = [set(nodes) for nodes in components]
    diff_comp_pairs = set()
    for a, b in diff_pairs:
        ca = node_to_comp[a]
        cb = node_to_comp[b]
        if ca != cb:
            x, y = (ca, cb) if ca < cb else (cb, ca)
            diff_comp_pairs.add((x, y))

    indeg = [0] * comp_count
    out = [[] for _ in range(comp_count)]
    for u, v in lt_comp_edges:
        out[u].append(v)
        indeg[v] += 1

    anc = [0] * comp_count
    desc = [0] * comp_count

    def dfs_reach(start, graph):
        seen = 0
        stack = [start]
        visited = [False] * comp_count
        visited[start] = True
        while stack:
            u = stack.pop()
            for w in graph[u]:
                if not visited[w]:
                    visited[w] = True
                    seen |= 1 << w
                    stack.append(w)
        return seen

    rev_graph = [[] for _ in range(comp_count)]
    for u in range(comp_count):
        for v in out[u]:
            rev_graph[v].append(u)

    for c in range(comp_count):
        desc[c] = dfs_reach(c, out)
        anc[c] = dfs_reach(c, rev_graph)
        if desc[c] & (1 << c):
            return []

    sizes = [len(components[c]) for c in range(comp_count)]
    total = sum(sizes)
    if total != n:
        return []

    diff_comp_map = [set() for _ in range(comp_count)]
    for x, y in diff_comp_pairs:
        diff_comp_map[x].add(y)
        diff_comp_map[y].add(x)

    boundary_forbidden = {}
    for x, y in diff_comp_pairs:
        pairs = set()
        for ox in oriented_components[x]:
            for oy in oriented_components[y]:
                if abs(ox[-1] - oy[0]) < 2:
                    pairs.add((tuple(ox), tuple(oy)))
                if abs(oy[-1] - ox[0]) < 2:
                    pairs.add((tuple(oy), tuple(ox)))
        if pairs:
            boundary_forbidden[(x, y)] = pairs
            boundary_forbidden[(y, x)] = {(b, a) for (a, b) in pairs}

    all_mask = (1 << comp_count) - 1
    order_comp = []
    used_mask = 0
    current_indeg = indeg[:]

    def available_components(mask):
        avail = []
        for c in range(comp_count):
            if not (mask >> c) & 1 and current_indeg[c] == 0:
                avail.append(c)
        return avail

    def can_finish(mask):
        temp_indeg = current_indeg[:]
        queue = [c for c in range(comp_count) if not (mask >> c) & 1 and temp_indeg[c] == 0]
        seen = 0
        idx = 0
        while idx < len(queue):
            u = queue[idx]
            idx += 1
            seen += 1
            for v in out[u]:
                if (mask >> v) & 1:
                    continue
                temp_indeg[v] -= 1
                if temp_indeg[v] == 0:
                    queue.append(v)
        return seen == comp_count - bin(mask).count("1")

    def backtrack_components(last_comp, last_order):
        nonlocal used_mask
        if used_mask == all_mask:
            return True

        avail = available_components(used_mask)
        scored = []
        for c in avail:
            future = 0
            d = desc[c]
            while d:
                future += 1
                d &= d - 1
            scored.append((future, -sizes[c], c))
        scored.sort(reverse=True)

        for _, _, c in scored:
            options = oriented_components[c]
            filtered = []
            if last_comp is not None and (last_comp, c) in boundary_forbidden:
                forbidden = boundary_forbidden[(last_comp, c)]
                for opt in options:
                    if (tuple(last_order), tuple(opt)) not in forbidden:
                        filtered.append(opt)
            else:
                filtered = options
            if not filtered:
                continue

            used_mask |= 1 << c
            changed = []
            for v in out[c]:
                current_indeg[v] -= 1
                changed.append(v)

            if can_finish(used_mask):
                for opt in filtered:
                    order_comp.append((c, opt))
                    if backtrack_components(c, opt):
                        return True
                    order_comp.pop()

            for v in changed:
                current_indeg[v] += 1
            used_mask ^= 1 << c

        return False

    if not backtrack_components(None, None):
        return []

    slot_order = []
    for _, comp_order in order_comp:
        slot_order.extend(comp_order)

    if len(slot_order) != n:
        return []

    position = [0] * n
    for idx, slot in enumerate(slot_order):
        position[slot] = idx

    for i, j in lt_edges:
        if not (position[i] < position[j]):
            return []
    for i in range(n):
        for j in adj_neighbors[i]:
            if i < j and abs(position[i] - position[j]) != 1:
                return []
    for i, j in diff_pairs:
        if abs(position[i] - position[j]) < 2:
            return []

    assignment = [0] * n
    for slot in range(n):
        assignment[slot] = position[slot] + 1
    return assignment