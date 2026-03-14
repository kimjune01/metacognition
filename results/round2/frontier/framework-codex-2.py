def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n == 0:
        return []

    values = set(range(1, n + 1))
    domains = [set(values) for _ in range(n)]
    lt_pairs = []
    adj_pairs = []
    diff_pairs = []
    adj_graph = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            return []
        if typ == "lt":
            lt_pairs.append((i, j))
        elif typ == "adj":
            adj_pairs.append((i, j))
            adj_graph[i].add(j)
            adj_graph[j].add(i)
        elif typ == "diff":
            diff_pairs.append((i, j))
        else:
            return []

    for i in range(n):
        if len(adj_graph[i]) > 2:
            return []

    seen = [False] * n
    for start in range(n):
        if seen[start]:
            continue
        stack = [start]
        nodes = 0
        deg_sum = 0
        while stack:
            u = stack.pop()
            if seen[u]:
                continue
            seen[u] = True
            nodes += 1
            deg_sum += len(adj_graph[u])
            for v in adj_graph[u]:
                if not seen[v]:
                    stack.append(v)
        edges = deg_sum // 2
        if edges >= nodes and nodes > 0:
            return []

    out = [[] for _ in range(n)]
    indeg = [0] * n
    for i, j in lt_pairs:
        out[i].append(j)
        indeg[j] += 1

    topo = []
    queue = [i for i in range(n) if indeg[i] == 0]
    qh = 0
    while qh < len(queue):
        u = queue[qh]
        qh += 1
        topo.append(u)
        for v in out[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    if len(topo) != n:
        return []

    longest_before = [0] * n
    for u in topo:
        base = longest_before[u] + 1
        for v in out[u]:
            if longest_before[v] < base:
                longest_before[v] = base

    rev = [[] for _ in range(n)]
    for i, j in lt_pairs:
        rev[j].append(i)

    longest_after = [0] * n
    for u in reversed(topo):
        base = longest_after[u] + 1
        for v in rev[u]:
            if longest_after[v] < base:
                longest_after[v] = base

    for i in range(n):
        lo = longest_before[i] + 1
        hi = n - longest_after[i]
        if lo > hi:
            return []
        domains[i].intersection_update(range(lo, hi + 1))
        if not domains[i]:
            return []

    def propagate(state):
        while True:
            changed = False

            assigned = {}
            for idx, d in enumerate(state):
                if not d:
                    return None
                if len(d) == 1:
                    v = next(iter(d))
                    if v in assigned:
                        return None
                    assigned[v] = idx

            for v, idx in assigned.items():
                for k in range(n):
                    if k != idx and v in state[k]:
                        state[k].remove(v)
                        if not state[k]:
                            return None
                        changed = True

            occurrences = [[] for _ in range(n + 1)]
            for idx, d in enumerate(state):
                for v in d:
                    occurrences[v].append(idx)
            for v in range(1, n + 1):
                if not occurrences[v]:
                    return None
                if len(occurrences[v]) == 1:
                    idx = occurrences[v][0]
                    if len(state[idx]) > 1:
                        state[idx] = {v}
                        changed = True

            for i, j in lt_pairs:
                di = state[i]
                dj = state[j]
                max_j = max(dj)
                min_i = min(di)
                ndi = {a for a in di if a < max_j}
                ndj = {b for b in dj if b > min_i}
                if not ndi or not ndj:
                    return None
                if ndi != di:
                    state[i] = ndi
                    changed = True
                if ndj != dj:
                    state[j] = ndj
                    changed = True

            for i, j in adj_pairs:
                di = state[i]
                dj = state[j]
                ndi = {a for a in di if (a - 1 in dj) or (a + 1 in dj)}
                ndj = {b for b in dj if (b - 1 in di) or (b + 1 in di)}
                if not ndi or not ndj:
                    return None
                if ndi != di:
                    state[i] = ndi
                    changed = True
                if ndj != dj:
                    state[j] = ndj
                    changed = True

            for i, j in diff_pairs:
                di = state[i]
                dj = state[j]
                min_j, max_j = min(dj), max(dj)
                min_i, max_i = min(di), max(di)
                ndi = {a for a in di if min_j <= a - 2 or max_j >= a + 2}
                ndj = {b for b in dj if min_i <= b - 2 or max_i >= b + 2}
                if not ndi or not ndj:
                    return None
                if ndi != di:
                    state[i] = ndi
                    changed = True
                if ndj != dj:
                    state[j] = ndj
                    changed = True

            if not changed:
                return state

    def valid(assign):
        if len(set(assign)) != n or set(assign) != values:
            return False
        for i, j in lt_pairs:
            if not (assign[i] < assign[j]):
                return False
        for i, j in diff_pairs:
            if abs(assign[i] - assign[j]) < 2:
                return False
        for i, j in adj_pairs:
            if abs(assign[i] - assign[j]) != 1:
                return False
        return True

    def search(state):
        state = propagate(state)
        if state is None:
            return []
        if all(len(d) == 1 for d in state):
            result = [next(iter(d)) for d in state]
            return result if valid(result) else []

        idx = min((i for i in range(n) if len(state[i]) > 1), key=lambda k: len(state[k]))
        for v in sorted(state[idx]):
            new_state = [set(d) for d in state]
            new_state[idx] = {v}
            result = search(new_state)
            if result:
                return result
        return []

    return search(domains)