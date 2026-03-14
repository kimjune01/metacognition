def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    lt_out = [[] for _ in range(n)]
    lt_in = [[] for _ in range(n)]
    adj_pairs = []
    diff_pairs = []
    adj_of = [[] for _ in range(n)]
    diff_of = [[] for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            if typ == "lt":
                return []
            if typ == "adj":
                return []
            continue
        if typ == "lt":
            lt_out[i].append(j)
            lt_in[j].append(i)
        elif typ == "adj":
            adj_pairs.append((i, j))
            adj_of[i].append(j)
            adj_of[j].append(i)
        elif typ == "diff":
            diff_pairs.append((i, j))
            diff_of[i].append(j)
            diff_of[j].append(i)
        else:
            return []

    # Detect cycles and compute transitive closure for static rank bounds.
    reach = [set() for _ in range(n)]
    for s in range(n):
        stack = lt_out[s][:]
        seen = set()
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            reach[s].add(u)
            stack.extend(lt_out[u])
        if s in reach[s]:
            return []

    pred_count = [0] * n
    succ_count = [0] * n
    for i in range(n):
        succ_count[i] = len(reach[i])
    for j in range(n):
        pred_count[j] = sum(1 for i in range(n) if j in reach[i])

    static_domains = []
    for i in range(n):
        lo = pred_count[i] + 1
        hi = n - succ_count[i]
        if lo > hi:
            return []
        static_domains.append(set(range(lo, hi + 1)))

    assign = [0] * n
    available = set(range(1, n + 1))

    def compute_domains():
        domains = [None] * n
        for i in range(n):
            if assign[i]:
                domains[i] = {assign[i]}
                continue

            dom = static_domains[i] & available

            for p in lt_in[i]:
                if assign[p]:
                    ap = assign[p]
                    dom = {v for v in dom if v > ap}
            for q in lt_out[i]:
                if assign[q]:
                    aq = assign[q]
                    dom = {v for v in dom if v < aq}

            for j in adj_of[i]:
                if assign[j]:
                    aj = assign[j]
                    dom &= {aj - 1, aj + 1}

            for j in diff_of[i]:
                if assign[j]:
                    aj = assign[j]
                    if aj - 1 in dom:
                        dom.remove(aj - 1)
                    if aj + 1 in dom:
                        dom.remove(aj + 1)

            if not dom:
                return None
            domains[i] = dom
        return domains

    def pair_possible_lt(di, dj):
        if not di or not dj:
            return False
        min_j = min(dj)
        return any(v < min_j or any(v < w for w in dj) for v in di)

    def pair_possible_adj(di, dj):
        if not di or not dj:
            return False
        for v in di:
            if v - 1 in dj or v + 1 in dj:
                return True
        return False

    def pair_possible_diff(di, dj):
        if not di or not dj:
            return False
        if len(di) >= 3 or len(dj) >= 3:
            di_list = sorted(di)
            dj_set = set(dj)
            for v in di_list:
                if (v - 1 not in dj_set) and (v + 1 not in dj_set):
                    if dj:
                        return True
            for v in di_list:
                for w in dj:
                    if abs(v - w) >= 2:
                        return True
            return False
        for v in di:
            for w in dj:
                if abs(v - w) >= 2:
                    return True
        return False

    def all_different_feasible(domains):
        unassigned = [i for i in range(n) if not assign[i]]
        if not unassigned:
            return True

        value_to_idx = {v: k for k, v in enumerate(sorted(available))}
        adj = [[] for _ in unassigned]
        for ui, slot in enumerate(unassigned):
            for v in domains[slot]:
                adj[ui].append(value_to_idx[v])

        match_to_slot = [-1] * len(value_to_idx)

        def dfs(u, seen):
            for v in adj[u]:
                if seen[v]:
                    continue
                seen[v] = True
                if match_to_slot[v] == -1 or dfs(match_to_slot[v], seen):
                    match_to_slot[v] = u
                    return True
            return False

        for u in range(len(unassigned)):
            seen = [False] * len(value_to_idx)
            if not dfs(u, seen):
                return False
        return True

    def feasible(domains):
        for i in range(n):
            if not assign[i] and not domains[i]:
                return False

        for i in range(n):
            if assign[i]:
                ai = assign[i]
                for j in lt_out[i]:
                    if assign[j] and not (ai < assign[j]):
                        return False

        for i, j in adj_pairs:
            if assign[i] and assign[j]:
                if abs(assign[i] - assign[j]) != 1:
                    return False
            elif not assign[i] and not assign[j]:
                if not pair_possible_adj(domains[i], domains[j]):
                    return False

        for i, j in diff_pairs:
            if assign[i] and assign[j]:
                if abs(assign[i] - assign[j]) < 2:
                    return False
            elif not assign[i] and not assign[j]:
                if not pair_possible_diff(domains[i], domains[j]):
                    return False

        for i in range(n):
            if not assign[i]:
                for j in lt_out[i]:
                    if not assign[j]:
                        if not pair_possible_lt(domains[i], domains[j]):
                            return False

        return all_different_feasible(domains)

    def search():
        domains = compute_domains()
        if domains is None or not feasible(domains):
            return False

        if all(assign):
            return True

        slot = min((i for i in range(n) if not assign[i]), key=lambda x: (len(domains[x]), x))
        candidates = sorted(domains[slot])

        def score(v):
            s = 0
            for j in adj_of[slot]:
                if not assign[j]:
                    if v - 1 in domains[j]:
                        s += 1
                    if v + 1 in domains[j]:
                        s += 1
            for j in diff_of[slot]:
                if not assign[j]:
                    if v - 1 in domains[j]:
                        s -= 1
                    if v + 1 in domains[j]:
                        s -= 1
            return -s, v

        candidates.sort(key=score)

        for v in candidates:
            assign[slot] = v
            available.remove(v)
            if search():
                return True
            available.add(v)
            assign[slot] = 0

        return False

    return assign[:] if search() else []