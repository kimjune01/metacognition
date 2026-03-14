def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from collections import deque

    if n < 0:
        return []
    if n == 0:
        return []

    lt_out = [set() for _ in range(n)]
    lt_in = [set() for _ in range(n)]
    adj = [set() for _ in range(n)]
    diff = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt_out[i].add(j)
            lt_in[j].add(i)
        elif typ == "adj":
            if i == j:
                return []
            adj[i].add(j)
            adj[j].add(i)
        elif typ == "diff":
            if i == j:
                return []
            diff[i].add(j)
            diff[j].add(i)
        else:
            return []

    for i in range(n):
        if adj[i] & diff[i]:
            return []

    for i in range(n):
        if len(adj[i]) > 2:
            return []

    seen = [False] * n
    for start in range(n):
        if seen[start] or not adj[start]:
            continue
        q = deque([start])
        seen[start] = True
        nodes = 0
        deg1 = 0
        edge_sum = 0
        while q:
            u = q.popleft()
            nodes += 1
            du = len(adj[u])
            edge_sum += du
            if du == 1:
                deg1 += 1
            elif du > 2:
                return []
            for v in adj[u]:
                if not seen[v]:
                    seen[v] = True
                    q.append(v)
        edges = edge_sum // 2
        if edges != nodes - 1:
            return []
        if nodes > 1 and deg1 != 2:
            return []

    indeg = [len(lt_in[i]) for i in range(n)]
    q = deque([i for i in range(n) if indeg[i] == 0])
    topo = []
    while q:
        u = q.popleft()
        topo.append(u)
        for v in lt_out[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(topo) != n:
        return []

    ancestors = [set() for _ in range(n)]
    for u in topo:
        acc = ancestors[u]
        for v in lt_out[u]:
            ancestors[v].add(u)
            ancestors[v].update(acc)

    descendants = [set() for _ in range(n)]
    for u in reversed(topo):
        acc = descendants[u]
        for v in lt_out[u]:
            acc.add(v)
            acc.update(descendants[v])

    lower_bound = [len(ancestors[i]) + 1 for i in range(n)]
    upper_bound = [n - len(descendants[i]) for i in range(n)]
    for i in range(n):
        if lower_bound[i] > upper_bound[i]:
            return []

    assigned = [-1] * n
    available = set(range(1, n + 1))

    def candidates(i: int):
        if assigned[i] != -1:
            return [assigned[i]]

        lo = lower_bound[i]
        hi = upper_bound[i]

        for p in lt_in[i]:
            vp = assigned[p]
            if vp != -1:
                lo = max(lo, vp + 1)

        for s in lt_out[i]:
            vs = assigned[s]
            if vs != -1:
                hi = min(hi, vs - 1)

        if lo > hi:
            return []

        forced = None
        used_adj_values = set()
        unassigned_adj = 0

        for j in adj[i]:
            vj = assigned[j]
            if vj == -1:
                unassigned_adj += 1
                continue
            opts = {vj - 1, vj + 1}
            forced = opts if forced is None else forced & opts
            used_adj_values.add(vj)

        out = []
        base = forced if forced is not None else available
        for v in base:
            if v not in available or v < lo or v > hi:
                continue

            ok = True

            for j in diff[i]:
                vj = assigned[j]
                if vj != -1 and abs(v - vj) < 2:
                    ok = False
                    break
            if not ok:
                continue

            if unassigned_adj:
                remaining_adj_values = 0
                if v - 1 in available and (v - 1) not in used_adj_values:
                    remaining_adj_values += 1
                if v + 1 in available and (v + 1) not in used_adj_values:
                    remaining_adj_values += 1
                if remaining_adj_values < unassigned_adj:
                    continue

            out.append(v)

        out.sort()
        return out

    def consistent_all_unassigned():
        for i in range(n):
            if assigned[i] == -1 and not candidates(i):
                return False
        return True

    def backtrack():
        if not available:
            return True

        best_i = -1
        best_cands = None

        for i in range(n):
            if assigned[i] != -1:
                continue
            cands = candidates(i)
            if not cands:
                return False
            if best_cands is None or len(cands) < len(best_cands):
                best_i = i
                best_cands = cands
                if len(best_cands) == 1:
                    break

        for v in best_cands:
            assigned[best_i] = v
            available.remove(v)

            if consistent_all_unassigned() and backtrack():
                return True

            available.add(v)
            assigned[best_i] = -1

        return False

    return assigned[:] if backtrack() else []