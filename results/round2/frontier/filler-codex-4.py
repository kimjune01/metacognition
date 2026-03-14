def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    parents = [[] for _ in range(n)]
    children = [[] for _ in range(n)]
    adj = [[] for _ in range(n)]
    diff = [[] for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            children[i].append(j)
            parents[j].append(i)
        elif typ == "adj":
            if i == j:
                return []
            adj[i].append(j)
            adj[j].append(i)
        elif typ == "diff":
            if i == j:
                return []
            diff[i].append(j)
            diff[j].append(i)
        else:
            return []

    indeg = [len(parents[i]) for i in range(n)]
    stack = [i for i in range(n) if indeg[i] == 0]
    topo = []
    while stack:
        u = stack.pop()
        topo.append(u)
        for v in children[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                stack.append(v)
    if len(topo) != n:
        return []

    desc_bits = [0] * n
    for u in reversed(topo):
        bits = 0
        for v in children[u]:
            bits |= desc_bits[v] | (1 << v)
        desc_bits[u] = bits

    anc_bits = [0] * n
    for u in topo:
        bits = 0
        for v in parents[u]:
            bits |= anc_bits[v] | (1 << v)
        anc_bits[u] = bits

    base_min = [0] * n
    base_max = [0] * n
    for i in range(n):
        amin = anc_bits[i].bit_count() + 1
        amax = n - desc_bits[i].bit_count()
        if amin > amax:
            return []
        base_min[i] = amin
        base_max[i] = amax

    assign = [-1] * n
    used = [False] * (n + 1)

    def domain(pos: int) -> list[int]:
        lo = base_min[pos]
        hi = base_max[pos]

        for p in parents[pos]:
            vp = assign[p]
            if vp != -1 and vp + 1 > lo:
                lo = vp + 1
        for c in children[pos]:
            vc = assign[c]
            if vc != -1 and vc - 1 < hi:
                hi = vc - 1

        if lo > hi:
            return []

        vals = []
        for v in range(lo, hi + 1):
            if used[v]:
                continue

            ok = True
            for q in adj[pos]:
                aq = assign[q]
                if aq != -1 and abs(v - aq) != 1:
                    ok = False
                    break
            if not ok:
                continue

            for q in diff[pos]:
                aq = assign[q]
                if aq != -1 and abs(v - aq) < 2:
                    ok = False
                    break
            if not ok:
                continue

            vals.append(v)

        return vals

    def search() -> bool:
        best_pos = -1
        best_dom = None

        for i in range(n):
            if assign[i] == -1:
                d = domain(i)
                if not d:
                    return False
                if best_dom is None or len(d) < len(best_dom):
                    best_pos = i
                    best_dom = d
                    if len(best_dom) == 1:
                        break

        if best_pos == -1:
            return True

        for v in best_dom:
            assign[best_pos] = v
            used[v] = True

            failed = False
            for i in range(n):
                if assign[i] == -1 and not domain(i):
                    failed = True
                    break

            if not failed and search():
                return True

            used[v] = False
            assign[best_pos] = -1

        return False

    return assign[:] if search() else []