def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    lt_reach = [0] * n
    adj = [set() for _ in range(n)]
    diff = [set() for _ in range(n)]
    pair_kind = {}

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt_reach[i] |= 1 << j
        elif typ in ("adj", "diff"):
            if i == j:
                return []
            a, b = (i, j) if i < j else (j, i)
            prev = pair_kind.get((a, b))
            if prev is not None and prev != typ:
                return []
            pair_kind[(a, b)] = typ
            if typ == "adj":
                adj[i].add(j)
                adj[j].add(i)
            else:
                diff[i].add(j)
                diff[j].add(i)
        else:
            return []

    for s in range(n):
        if len(adj[s]) > 2:
            return []

    seen = [False] * n
    for start in range(n):
        if seen[start] or not adj[start]:
            continue
        stack = [(start, -1)]
        nodes = 0
        edge_sum = 0
        while stack:
            u, parent = stack.pop()
            if seen[u]:
                continue
            seen[u] = True
            nodes += 1
            edge_sum += len(adj[u])
            for v in adj[u]:
                if not seen[v]:
                    stack.append((v, u))
        if edge_sum // 2 != nodes - 1:
            return []

    for k in range(n):
        bit = 1 << k
        rk = lt_reach[k]
        for i in range(n):
            if lt_reach[i] & bit:
                lt_reach[i] |= rk

    for i in range(n):
        if (lt_reach[i] >> i) & 1:
            return []

    preds = [0] * n
    for i in range(n):
        row = lt_reach[i]
        for j in range(n):
            if (row >> j) & 1:
                preds[j] |= 1 << i

    pred_total = [m.bit_count() for m in preds]
    succ_total = [m.bit_count() for m in lt_reach]
    static_lo = [c + 1 for c in pred_total]
    static_hi = [n - c for c in succ_total]
    for i in range(n):
        if static_lo[i] > static_hi[i]:
            return []

    assign = [0] * n
    unused = set(range(1, n + 1))

    def relation(a: int, b: int) -> int:
        if (lt_reach[a] >> b) & 1:
            return -1
        if (lt_reach[b] >> a) & 1:
            return 1
        return 0

    def can_match_adj(neighbors: list[int], options: list[tuple[int, ...]]) -> bool:
        used = set()

        def dfs(idx: int) -> bool:
            if idx == len(neighbors):
                return True
            for val in options[idx]:
                if val not in used:
                    used.add(val)
                    if dfs(idx + 1):
                        return True
                    used.remove(val)
            return False

        return dfs(0)

    def candidate_values(slot: int) -> list[int]:
        vals = []
        pred_mask = preds[slot]
        succ_mask = lt_reach[slot]
        unassigned_preds = 0
        unassigned_succs = 0

        pm = pred_mask
        while pm:
            b = pm & -pm
            idx = b.bit_length() - 1
            if assign[idx] == 0:
                unassigned_preds += 1
            pm ^= b

        sm = succ_mask
        while sm:
            b = sm & -sm
            idx = b.bit_length() - 1
            if assign[idx] == 0:
                unassigned_succs += 1
            sm ^= b

        sorted_unused = sorted(unused)
        for v in sorted_unused:
            if v < static_lo[slot] or v > static_hi[slot]:
                continue

            less_unused = 0
            greater_unused = 0
            for u in sorted_unused:
                if u < v:
                    less_unused += 1
                elif u > v:
                    greater_unused += 1
            if less_unused < unassigned_preds or greater_unused < unassigned_succs:
                continue

            ok = True

            pm = pred_mask
            while pm:
                b = pm & -pm
                idx = b.bit_length() - 1
                if assign[idx] and not (assign[idx] < v):
                    ok = False
                    break
                pm ^= b
            if not ok:
                continue

            sm = succ_mask
            while sm:
                b = sm & -sm
                idx = b.bit_length() - 1
                if assign[idx] and not (v < assign[idx]):
                    ok = False
                    break
                sm ^= b
            if not ok:
                continue

            for t in diff[slot]:
                if assign[t] and abs(v - assign[t]) == 1:
                    ok = False
                    break
            if not ok:
                continue

            for t in adj[slot]:
                if assign[t] and abs(v - assign[t]) != 1:
                    ok = False
                    break
            if not ok:
                continue

            pending_adj = []
            pending_opts = []
            for t in adj[slot]:
                if assign[t]:
                    continue
                opts = []
                rel = relation(slot, t)
                if v - 1 in unused and rel != -1:
                    opts.append(v - 1)
                if v + 1 in unused and rel != 1:
                    opts.append(v + 1)
                if not opts:
                    ok = False
                    break
                pending_adj.append(t)
                pending_opts.append(tuple(opts))
            if not ok:
                continue

            if pending_adj and not can_match_adj(pending_adj, pending_opts):
                continue

            vals.append(v)

        return vals

    def backtrack() -> bool:
        if not unused:
            return True

        best_slot = -1
        best_vals = None

        for s in range(n):
            if assign[s]:
                continue
            vals = candidate_values(s)
            if not vals:
                return False
            if best_vals is None or len(vals) < len(best_vals):
                best_slot = s
                best_vals = vals
                if len(best_vals) == 1:
                    break

        for v in best_vals:
            assign[best_slot] = v
            unused.remove(v)

            feasible = True
            for s in range(n):
                if assign[s] == 0 and not candidate_values(s):
                    feasible = False
                    break

            if feasible and backtrack():
                return True

            unused.add(v)
            assign[best_slot] = 0

        return False

    return assign[:] if backtrack() else []