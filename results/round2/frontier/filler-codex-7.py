def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n <= 0:
        return []

    lt_out = [set() for _ in range(n)]
    lt_in = [set() for _ in range(n)]
    adj_neighbors = [set() for _ in range(n)]
    diff_neighbors = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            return []
        if typ == "lt":
            lt_out[i].add(j)
            lt_in[j].add(i)
        elif typ == "adj":
            adj_neighbors[i].add(j)
            adj_neighbors[j].add(i)
        elif typ == "diff":
            diff_neighbors[i].add(j)
            diff_neighbors[j].add(i)
        else:
            return []

    for i in range(n):
        if adj_neighbors[i] & diff_neighbors[i]:
            return []

    indeg = [len(lt_in[i]) for i in range(n)]
    queue = [i for i in range(n) if indeg[i] == 0]
    topo = []
    head = 0
    while head < len(queue):
        u = queue[head]
        head += 1
        topo.append(u)
        for v in lt_out[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)

    if len(topo) != n:
        return []

    ancestors = [set() for _ in range(n)]
    for u in topo:
        base = ancestors[u] | {u}
        for v in lt_out[u]:
            ancestors[v] |= base

    descendants = [set() for _ in range(n)]
    for u in reversed(topo):
        base = descendants[u] | {u}
        for v in lt_in[u]:
            descendants[v] |= base

    ancestors = [tuple(s) for s in ancestors]
    descendants = [tuple(s) for s in descendants]

    base_lb = [len(ancestors[i]) + 1 for i in range(n)]
    base_ub = [n - len(descendants[i]) for i in range(n)]
    for i in range(n):
        if base_lb[i] > base_ub[i]:
            return []

    assignment = [0] * n
    used = [False] * (n + 1)

    def domain(slot: int) -> list[int]:
        if assignment[slot]:
            return [assignment[slot]]

        lb = base_lb[slot]
        ub = base_ub[slot]

        for a in ancestors[slot]:
            va = assignment[a]
            if va:
                lb = max(lb, va + 1)

        for d in descendants[slot]:
            vd = assignment[d]
            if vd:
                ub = min(ub, vd - 1)

        if lb > ub:
            return []

        vals = []
        for v in range(lb, ub + 1):
            if used[v]:
                continue

            ok = True

            for t in adj_neighbors[slot]:
                vt = assignment[t]
                if vt and abs(v - vt) != 1:
                    ok = False
                    break
            if not ok:
                continue

            for t in diff_neighbors[slot]:
                vt = assignment[t]
                if vt and abs(v - vt) < 2:
                    ok = False
                    break

            if ok:
                vals.append(v)

        return vals

    def select_unassigned():
        best_slot = -1
        best_domain = None
        best_score = -1

        for s in range(n):
            if assignment[s]:
                continue
            d = domain(s)
            if not d:
                return s, d
            score = len(adj_neighbors[s]) + len(diff_neighbors[s]) + len(lt_in[s]) + len(lt_out[s])
            if best_domain is None or len(d) < len(best_domain) or (len(d) == len(best_domain) and score > best_score):
                best_slot = s
                best_domain = d
                best_score = score

        return best_slot, best_domain

    def forward_check() -> bool:
        for s in range(n):
            if assignment[s] == 0 and not domain(s):
                return False
        return True

    def backtrack(filled: int) -> bool:
        if filled == n:
            return True

        slot, vals = select_unassigned()
        if not vals:
            return False

        for v in vals:
            assignment[slot] = v
            used[v] = True

            if forward_check() and backtrack(filled + 1):
                return True

            used[v] = False
            assignment[slot] = 0

        return False

    return assignment[:] if backtrack(0) else []