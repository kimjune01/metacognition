def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    reach = [[False] * n for _ in range(n)]
    adj_pairs = []
    diff_pairs = []

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            return []
        if typ == "lt":
            reach[i][j] = True
        elif typ == "adj":
            adj_pairs.append((i, j))
        elif typ == "diff":
            diff_pairs.append((i, j))
        else:
            return []

    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                row_i = reach[i]
                row_k = reach[k]
                for j in range(n):
                    if row_k[j]:
                        row_i[j] = True

    for i in range(n):
        if reach[i][i]:
            return []

    preds = [set() for _ in range(n)]
    succs = [set() for _ in range(n)]
    lt_pairs = []
    for i in range(n):
        for j in range(n):
            if reach[i][j]:
                succs[i].add(j)
                preds[j].add(i)
                lt_pairs.append((i, j))

    failed = set()

    def build_domains(assign):
        available = [v for v in range(1, n + 1) if v not in assign]
        avail_set = set(available)
        less_count = {v: idx for idx, v in enumerate(available)}
        greater_count = {v: len(available) - idx - 1 for idx, v in enumerate(available)}

        domains = [set() for _ in range(n)]
        for i in range(n):
            if assign[i] is not None:
                domains[i] = {assign[i]}
                continue

            max_pred = 0
            min_succ = n + 1
            rem_pred = 0
            rem_succ = 0

            for p in preds[i]:
                if assign[p] is None:
                    rem_pred += 1
                else:
                    if assign[p] > max_pred:
                        max_pred = assign[p]

            for s in succs[i]:
                if assign[s] is None:
                    rem_succ += 1
                else:
                    if assign[s] < min_succ:
                        min_succ = assign[s]

            dom = set()
            for v in available:
                if v <= max_pred or v >= min_succ:
                    continue
                if less_count[v] < rem_pred:
                    continue
                if greater_count[v] < rem_succ:
                    continue
                dom.add(v)

            if not dom:
                return None
            domains[i] = dom

        changed = True
        while changed:
            changed = False

            singles = {}
            for i in range(n):
                if len(domains[i]) == 1:
                    singles[i] = next(iter(domains[i]))

            used_single_vals = {}
            for i, v in singles.items():
                if v in used_single_vals and used_single_vals[v] != i:
                    return None
                used_single_vals[v] = i

            for i, v in singles.items():
                for j in range(n):
                    if j != i and len(domains[j]) > 1 and v in domains[j]:
                        domains[j].remove(v)
                        if not domains[j]:
                            return None
                        changed = True

            for i, j in lt_pairs:
                di = domains[i]
                dj = domains[j]
                max_j = max(dj)
                min_i = min(di)

                new_di = {x for x in di if x < max_j}
                if not new_di:
                    return None
                if new_di != di:
                    domains[i] = new_di
                    di = new_di
                    min_i = min(di)
                    changed = True

                new_dj = {y for y in dj if y > min_i}
                if not new_dj:
                    return None
                if new_dj != dj:
                    domains[j] = new_dj
                    changed = True

            for i, j in adj_pairs:
                di = domains[i]
                dj = domains[j]

                new_di = {x for x in di if (x - 1 in dj) or (x + 1 in dj)}
                if not new_di:
                    return None
                if new_di != di:
                    domains[i] = new_di
                    di = new_di
                    changed = True

                new_dj = {y for y in dj if (y - 1 in di) or (y + 1 in di)}
                if not new_dj:
                    return None
                if new_dj != dj:
                    domains[j] = new_dj
                    changed = True

            for i, j in diff_pairs:
                di = domains[i]
                dj = domains[j]
                min_j = min(dj)
                max_j = max(dj)

                new_di = {x for x in di if min_j <= x - 2 or max_j >= x + 2}
                if not new_di:
                    return None
                if new_di != di:
                    domains[i] = new_di
                    di = new_di
                    changed = True

                min_i = min(di)
                max_i = max(di)
                new_dj = {y for y in dj if min_i <= y - 2 or max_i >= y + 2}
                if not new_dj:
                    return None
                if new_dj != dj:
                    domains[j] = new_dj
                    changed = True

        return domains

    def dfs(assign):
        key = tuple(-1 if v is None else v for v in assign)
        if key in failed:
            return None

        domains = build_domains(assign)
        if domains is None:
            failed.add(key)
            return None

        done = True
        best_i = -1
        best_dom = None
        for i in range(n):
            if assign[i] is None:
                done = False
                if best_dom is None or len(domains[i]) < len(best_dom):
                    best_i = i
                    best_dom = domains[i]

        if done:
            return [assign[i] if assign[i] is not None else next(iter(domains[i])) for i in range(n)]

        for v in sorted(best_dom):
            assign[best_i] = v
            res = dfs(assign)
            if res:
                return res
            assign[best_i] = None

        failed.add(key)
        return None

    result = dfs([None] * n)
    return result if result is not None else []