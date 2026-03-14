def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    lt_out = [set() for _ in range(n)]
    lt_in = [set() for _ in range(n)]
    adj = [set() for _ in range(n)]
    diff = [set() for _ in range(n)]
    neighbors = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt_out[i].add(j)
            lt_in[j].add(i)
            neighbors[i].add(j)
            neighbors[j].add(i)
        elif typ == "adj":
            if i == j:
                return []
            adj[i].add(j)
            adj[j].add(i)
            neighbors[i].add(j)
            neighbors[j].add(i)
        elif typ == "diff":
            if i == j:
                continue
            diff[i].add(j)
            diff[j].add(i)
            neighbors[i].add(j)
            neighbors[j].add(i)
        else:
            return []

    for i in range(n):
        if adj[i] & diff[i]:
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
        if i in seen:
            return []
        succ[i] = seen

    pred = [set() for _ in range(n)]
    for i in range(n):
        for j in succ[i]:
            pred[j].add(i)

    pred_count = [len(pred[i]) for i in range(n)]
    succ_count = [len(succ[i]) for i in range(n)]

    assignment = [0] * n
    used = [False] * (n + 1)

    def iter_assigned_neighbors(i, extra_slot=-1, extra_val=0):
        for j in neighbors[i]:
            if assignment[j]:
                yield j, assignment[j]
            elif j == extra_slot:
                yield j, extra_val

    def candidate_ok(i, v, extra_slot=-1, extra_val=0):
        if assignment[i]:
            return assignment[i] == v
        if used[v]:
            return False
        if extra_slot != -1 and extra_slot != i and v == extra_val:
            return False

        low = pred_count[i] + 1
        high = n - succ_count[i]

        for p in lt_in[i]:
            pv = assignment[p] if assignment[p] else (extra_val if p == extra_slot else 0)
            if pv:
                low = max(low, pv + 1)
        for s in lt_out[i]:
            sv = assignment[s] if assignment[s] else (extra_val if s == extra_slot else 0)
            if sv:
                high = min(high, sv - 1)

        if not (low <= v <= high):
            return False

        for j, w in iter_assigned_neighbors(i, extra_slot, extra_val):
            if j in lt_in[i] and not (w < v):
                return False
            if j in lt_out[i] and not (v < w):
                return False
            if j in adj[i] and abs(v - w) != 1:
                return False
            if j in diff[i] and abs(v - w) < 2:
                return False

        return True

    def has_possible_value(i, extra_slot=-1, extra_val=0):
        if assignment[i]:
            return True
        for v in range(1, n + 1):
            if candidate_ok(i, v, extra_slot, extra_val):
                return True
        return False

    def domain(i):
        vals = []
        for v in range(1, n + 1):
            if not candidate_ok(i, v):
                continue
            ok = True
            for j in neighbors[i]:
                if assignment[j]:
                    continue
                if not has_possible_value(j, i, v):
                    ok = False
                    break
            if ok:
                vals.append(v)
        return vals

    def dfs():
        if all(assignment):
            return True

        best_i = -1
        best_dom = None
        best_key = None

        for i in range(n):
            if assignment[i]:
                continue
            d = domain(i)
            if not d:
                return False
            key = (len(d), -len(neighbors[i]))
            if best_key is None or key < best_key:
                best_key = key
                best_i = i
                best_dom = d

        for v in best_dom:
            assignment[best_i] = v
            used[v] = True

            feasible = True
            for j in range(n):
                if assignment[j]:
                    continue
                if not has_possible_value(j):
                    feasible = False
                    break

            if feasible and dfs():
                return True

            used[v] = False
            assignment[best_i] = 0

        return False

    return assignment if dfs() else []