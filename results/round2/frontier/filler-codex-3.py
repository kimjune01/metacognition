def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    lt_out = [set() for _ in range(n)]
    adj_nei = [set() for _ in range(n)]
    diff_nei = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            return []
        if typ == "lt":
            lt_out[i].add(j)
        elif typ == "adj":
            adj_nei[i].add(j)
            adj_nei[j].add(i)
        elif typ == "diff":
            diff_nei[i].add(j)
            diff_nei[j].add(i)
        else:
            return []

    # Transitive closure for lt constraints; detect cycles.
    pred = [set() for _ in range(n)]
    succ = [set() for _ in range(n)]

    def dfs(start: int, u: int, seen: set[int]) -> bool:
        for v in lt_out[u]:
            if v == start:
                return True
            if v not in seen:
                seen.add(v)
                if dfs(start, v, seen):
                    return True
        return False

    for i in range(n):
        seen = set()
        if dfs(i, i, seen):
            return []
        succ[i] = seen
        for j in seen:
            pred[j].add(i)

    order_pairs = []
    for i in range(n):
        for j in lt_out[i]:
            order_pairs.append((i, j))

    assign = [0] * n
    used = [False] * (n + 1)
    unassigned = set(range(n))

    def is_feasible(slot: int, val: int) -> bool:
        if used[val]:
            return False

        # Direct lt checks against assigned neighbors.
        for j in lt_out[slot]:
            if assign[j] and not (val < assign[j]):
                return False
        for i in pred[slot]:
            if assign[i] and not (assign[i] < val):
                return False

        # adj/diff checks against assigned neighbors.
        for j in adj_nei[slot]:
            if assign[j] and abs(val - assign[j]) != 1:
                return False
        for j in diff_nei[slot]:
            if assign[j] and abs(val - assign[j]) < 2:
                return False

        # Global lt pruning using transitive closure.
        smaller_unused = 0
        larger_unused = 0
        for x in range(1, val):
            if not used[x]:
                smaller_unused += 1
        for x in range(val + 1, n + 1):
            if not used[x]:
                larger_unused += 1

        need_smaller = 0
        for p in pred[slot]:
            if assign[p]:
                if not (assign[p] < val):
                    return False
            else:
                need_smaller += 1

        need_larger = 0
        for s in succ[slot]:
            if assign[s]:
                if not (val < assign[s]):
                    return False
            else:
                need_larger += 1

        if need_smaller > smaller_unused:
            return False
        if need_larger > larger_unused:
            return False

        return True

    def forward_ok() -> bool:
        # Every unassigned slot must have at least one candidate.
        for s in unassigned:
            found = False
            for v in range(1, n + 1):
                if is_feasible(s, v):
                    found = True
                    break
            if not found:
                return False

        # For every unassigned adjacent pair, there must remain some possible pair of values.
        for i in list(unassigned):
            for j in adj_nei[i]:
                if j not in unassigned or i > j:
                    continue
                ok = False
                for v in range(1, n + 1):
                    if not is_feasible(i, v):
                        continue
                    for w in (v - 1, v + 1):
                        if 1 <= w <= n and w != v and is_feasible(j, w):
                            ok = True
                            break
                    if ok:
                        break
                if not ok:
                    return False
        return True

    def select_slot() -> tuple[int, list[int]] | tuple[None, None]:
        best_slot = None
        best_domain = None
        best_key = None

        for s in unassigned:
            domain = []
            for v in range(1, n + 1):
                if is_feasible(s, v):
                    domain.append(v)
            if not domain:
                return None, None
            degree = len(adj_nei[s]) + len(diff_nei[s]) + len(pred[s]) + len(succ[s])
            key = (len(domain), -degree, s)
            if best_key is None or key < best_key:
                best_key = key
                best_slot = s
                best_domain = domain

        return best_slot, best_domain

    def backtrack() -> bool:
        if not unassigned:
            return True

        slot, domain = select_slot()
        if slot is None:
            return False

        # Prefer middle-ish values to satisfy diff/adj more flexibly.
        mid = (n + 1) / 2
        domain.sort(key=lambda x: (abs(x - mid), x))

        unassigned.remove(slot)
        for val in domain:
            assign[slot] = val
            used[val] = True

            if forward_ok() and backtrack():
                return True

            used[val] = False
            assign[slot] = 0
        unassigned.add(slot)
        return False

    return assign[:] if backtrack() else []