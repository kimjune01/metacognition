def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    lt = [[False] * n for _ in range(n)]
    adj = [set() for _ in range(n)]
    diff = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt[i][j] = True
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

    for k in range(n):
        for i in range(n):
            if lt[i][k]:
                row_i = lt[i]
                row_k = lt[k]
                for j in range(n):
                    if row_k[j]:
                        row_i[j] = True

    for i in range(n):
        if lt[i][i]:
            return []

    pred_count = [sum(lt[j][i] for j in range(n)) for i in range(n)]
    succ_count = [sum(lt[i][j] for j in range(n)) for i in range(n)]

    for i in range(n):
        for j in adj[i]:
            for k in range(n):
                if (lt[i][k] and lt[k][j]) or (lt[j][k] and lt[k][i]):
                    return []

    assign = [0] * n
    unused = set(range(1, n + 1))

    def domain(i: int) -> list[int]:
        lo = pred_count[i] + 1
        hi = n - succ_count[i]

        for k, vk in enumerate(assign):
            if vk == 0:
                continue
            if lt[i][k]:
                hi = min(hi, vk - 1)
            if lt[k][i]:
                lo = max(lo, vk + 1)

        if lo > hi:
            return []

        out = []
        for v in unused:
            if v < lo or v > hi:
                continue

            ok = True
            for j in adj[i]:
                w = assign[j]
                if w and abs(v - w) != 1:
                    ok = False
                    break
            if not ok:
                continue

            for j in diff[i]:
                w = assign[j]
                if w and abs(v - w) < 2:
                    ok = False
                    break
            if ok:
                out.append(v)

        out.sort()
        return out

    def search() -> bool:
        chosen = -1
        chosen_domain = None

        for i in range(n):
            if assign[i] != 0:
                continue
            d = domain(i)
            if not d:
                return False
            if chosen_domain is None or len(d) < len(chosen_domain):
                chosen = i
                chosen_domain = d
                if len(chosen_domain) == 1:
                    break

        if chosen == -1:
            return True

        for v in chosen_domain:
            assign[chosen] = v
            unused.remove(v)

            feasible = True
            for i in range(n):
                if assign[i] == 0 and not domain(i):
                    feasible = False
                    break

            if feasible and search():
                return True

            unused.add(v)
            assign[chosen] = 0

        return False

    return assign if search() else []