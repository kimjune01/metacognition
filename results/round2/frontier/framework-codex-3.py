def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n <= 0:
        return []

    lt_out = [[] for _ in range(n)]
    lt_in = [[] for _ in range(n)]
    diff_neighbors = [[] for _ in range(n)]
    adj_neighbors = [[] for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            if typ in ("lt", "diff", "adj"):
                return []
        if typ == "lt":
            lt_out[i].append(j)
            lt_in[j].append(i)
        elif typ == "diff":
            diff_neighbors[i].append(j)
            diff_neighbors[j].append(i)
        elif typ == "adj":
            adj_neighbors[i].append(j)
            adj_neighbors[j].append(i)
        else:
            return []

    indeg = [len(lt_in[i]) for i in range(n)]
    queue = [i for i in range(n) if indeg[i] == 0]
    topo = []
    qi = 0
    while qi < len(queue):
        u = queue[qi]
        qi += 1
        topo.append(u)
        for v in lt_out[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    if len(topo) != n:
        return []

    ancestors = [0] * n
    for u in topo:
        mask = ancestors[u] | (1 << u)
        for v in lt_out[u]:
            ancestors[v] |= mask

    descendants = [0] * n
    for u in reversed(topo):
        mask = descendants[u] | (1 << u)
        for p in lt_in[u]:
            descendants[p] |= mask

    lower_bound = [ancestors[i].bit_count() + 1 for i in range(n)]
    upper_bound = [n - descendants[i].bit_count() for i in range(n)]
    for i in range(n):
        if lower_bound[i] > upper_bound[i]:
            return []

    assigned = [0] * n
    used = [False] * (n + 1)

    def candidate_values(slot: int):
        vals = []
        lo = lower_bound[slot]
        hi = upper_bound[slot]

        for v in range(lo, hi + 1):
            if used[v]:
                continue

            ok = True

            for p in lt_in[slot]:
                ap = assigned[p]
                if ap and not (ap < v):
                    ok = False
                    break
            if not ok:
                continue

            for q in lt_out[slot]:
                aq = assigned[q]
                if aq and not (v < aq):
                    ok = False
                    break
            if not ok:
                continue

            for j in diff_neighbors[slot]:
                aj = assigned[j]
                if aj and abs(v - aj) < 2:
                    ok = False
                    break
            if not ok:
                continue

            for j in adj_neighbors[slot]:
                aj = assigned[j]
                if aj and abs(v - aj) != 1:
                    ok = False
                    break
            if not ok:
                continue

            vals.append(v)

        return vals

    def feasible():
        seen_masks = {}
        for i in range(n):
            if assigned[i]:
                continue
            vals = candidate_values(i)
            if not vals:
                return False
            mask = 0
            for v in vals:
                mask |= 1 << v
            seen_masks[mask] = seen_masks.get(mask, 0) + 1

        for mask, count in seen_masks.items():
            if mask.bit_count() < count:
                return False
        return True

    def choose_slot():
        best_slot = -1
        best_vals = None
        for i in range(n):
            if assigned[i]:
                continue
            vals = candidate_values(i)
            if not vals:
                return i, []
            if best_vals is None or len(vals) < len(best_vals):
                best_slot = i
                best_vals = vals
                if len(best_vals) == 1:
                    break
        return best_slot, best_vals

    def backtrack(placed: int):
        if placed == n:
            return True

        slot, vals = choose_slot()
        if not vals:
            return False

        def score(v: int):
            s = 0
            for j in adj_neighbors[slot]:
                if not assigned[j]:
                    if v > 1 and not used[v - 1]:
                        s += 1
                    if v < n and not used[v + 1]:
                        s += 1
            return s

        vals.sort(key=score)

        for v in vals:
            assigned[slot] = v
            used[v] = True

            ok = True
            for j in adj_neighbors[slot]:
                if not assigned[j]:
                    need_left = v > 1 and not used[v - 1]
                    need_right = v < n and not used[v + 1]
                    if not (need_left or need_right):
                        ok = False
                        break

            if ok and feasible() and backtrack(placed + 1):
                return True

            used[v] = False
            assigned[slot] = 0

        return False

    return assigned[:] if backtrack(0) else []