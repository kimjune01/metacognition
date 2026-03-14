def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    lt_out = [set() for _ in range(n)]
    adj = [set() for _ in range(n)]
    diff = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt_out[i].add(j)
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

    color = [0] * n

    def has_cycle(u: int) -> bool:
        color[u] = 1
        for v in lt_out[u]:
            if color[v] == 1:
                return True
            if color[v] == 0 and has_cycle(v):
                return True
        color[u] = 2
        return False

    for i in range(n):
        if color[i] == 0 and has_cycle(i):
            return []

    succ = [set() for _ in range(n)]
    for i in range(n):
        stack = list(lt_out[i])
        seen = set()
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            stack.extend(lt_out[u])
        succ[i] = seen

    pred = [set() for _ in range(n)]
    for i in range(n):
        for j in succ[i]:
            pred[j].add(i)

    base_lb = [len(pred[i]) + 1 for i in range(n)]
    base_ub = [n - len(succ[i]) for i in range(n)]
    for i in range(n):
        if base_lb[i] > base_ub[i]:
            return []

    assigned = [0] * n
    used = [False] * (n + 1)

    def candidates(i: int) -> list[int]:
        lb = base_lb[i]
        ub = base_ub[i]

        for p in pred[i]:
            ap = assigned[p]
            if ap:
                lb = max(lb, ap + 1)

        for s in succ[i]:
            av = assigned[s]
            if av:
                ub = min(ub, av - 1)

        if lb > ub:
            return []

        vals = []
        for v in range(lb, ub + 1):
            if used[v]:
                continue

            ok = True

            for j in adj[i]:
                aj = assigned[j]
                if aj and abs(v - aj) != 1:
                    ok = False
                    break
            if not ok:
                continue

            for j in diff[i]:
                aj = assigned[j]
                if aj and abs(v - aj) < 2:
                    ok = False
                    break
            if ok:
                vals.append(v)

        return vals

    def forward_check() -> bool:
        for i in range(n):
            if assigned[i] == 0 and not candidates(i):
                return False
        return True

    def dfs(filled: int) -> bool:
        if filled == n:
            return True

        best_i = -1
        best_vals = None

        for i in range(n):
            if assigned[i] == 0:
                vals = candidates(i)
                if not vals:
                    return False
                if best_vals is None or len(vals) < len(best_vals):
                    best_i = i
                    best_vals = vals
                    if len(best_vals) == 1:
                        break

        for v in best_vals:
            assigned[best_i] = v
            used[v] = True

            if forward_check() and dfs(filled + 1):
                return True

            used[v] = False
            assigned[best_i] = 0

        return False

    return assigned[:] if dfs(0) else []