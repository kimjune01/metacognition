def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n <= 0:
        return []

    lt_out = [[] for _ in range(n)]
    lt_in = [[] for _ in range(n)]
    diff_neighbors = [set() for _ in range(n)]
    adj_neighbors = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            return []
        if typ == "lt":
            lt_out[i].append(j)
            lt_in[j].append(i)
        elif typ == "diff":
            diff_neighbors[i].add(j)
            diff_neighbors[j].add(i)
        elif typ == "adj":
            adj_neighbors[i].add(j)
            adj_neighbors[j].add(i)
        else:
            return []

    assigned = [0] * n
    unused = set(range(1, n + 1))

    def candidates(slot: int) -> list[int]:
        vals = []
        pred_unassigned = sum(1 for p in lt_in[slot] if assigned[p] == 0)
        succ_unassigned = sum(1 for q in lt_out[slot] if assigned[q] == 0)
        adj_unassigned = sum(1 for k in adj_neighbors[slot] if assigned[k] == 0)
        diff_unassigned = sum(1 for k in diff_neighbors[slot] if assigned[k] == 0)

        for v in sorted(unused):
            ok = True

            for p in lt_in[slot]:
                pv = assigned[p]
                if pv and not (pv < v):
                    ok = False
                    break
            if not ok:
                continue

            for q in lt_out[slot]:
                qv = assigned[q]
                if qv and not (v < qv):
                    ok = False
                    break
            if not ok:
                continue

            for k in diff_neighbors[slot]:
                kv = assigned[k]
                if kv and abs(v - kv) < 2:
                    ok = False
                    break
            if not ok:
                continue

            for k in adj_neighbors[slot]:
                kv = assigned[k]
                if kv and abs(v - kv) != 1:
                    ok = False
                    break
            if not ok:
                continue

            less = sum(1 for x in unused if x < v)
            greater = sum(1 for x in unused if x > v)
            if less < pred_unassigned or greater < succ_unassigned:
                continue

            adjacent_unused = (1 if v - 1 in unused else 0) + (1 if v + 1 in unused else 0)
            if adjacent_unused < adj_unassigned:
                continue

            nonadj_unused = len(unused) - 1 - adjacent_unused
            if nonadj_unused < diff_unassigned:
                continue

            vals.append(v)

        return vals

    def feasible_all_unassigned() -> bool:
        for i in range(n):
            if assigned[i] == 0 and not candidates(i):
                return False
        return True

    def backtrack(remaining: int) -> bool:
        if remaining == 0:
            return True

        best_slot = -1
        best_vals = None

        for i in range(n):
            if assigned[i] == 0:
                vals = candidates(i)
                if not vals:
                    return False
                if best_vals is None or len(vals) < len(best_vals):
                    best_slot = i
                    best_vals = vals
                    if len(best_vals) == 1:
                        break

        for v in best_vals:
            assigned[best_slot] = v
            unused.remove(v)

            if feasible_all_unassigned() and backtrack(remaining - 1):
                return True

            unused.add(v)
            assigned[best_slot] = 0

        return False

    return assigned[:] if backtrack(n) else []