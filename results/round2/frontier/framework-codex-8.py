def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    lt_pairs = []
    adj_pairs = []
    diff_pairs = []
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
            lt_pairs.append((i, j))
        elif typ == "adj":
            adj_pairs.append((i, j))
        elif typ == "diff":
            diff_pairs.append((i, j))
        else:
            return []

    def has_perfect_matching(domains: list[set[int]]) -> bool:
        order = sorted(range(n), key=lambda k: len(domains[k]))
        match_to_slot = {}

        def dfs(slot: int, seen: set[int]) -> bool:
            for v in domains[slot]:
                if v in seen:
                    continue
                seen.add(v)
                if v not in match_to_slot or dfs(match_to_slot[v], seen):
                    match_to_slot[v] = slot
                    return True
            return False

        for slot in order:
            if not dfs(slot, set()):
                return False
        return True

    def propagate(domains: list[set[int]]) -> list[set[int]] | None:
        while True:
            changed = False

            for d in domains:
                if not d:
                    return None

            seen_singletons = {}
            for idx, d in enumerate(domains):
                if len(d) == 1:
                    v = next(iter(d))
                    if v in seen_singletons and seen_singletons[v] != idx:
                        return None
                    seen_singletons[v] = idx

            assigned = set(seen_singletons.keys())
            for i, d in enumerate(domains):
                if len(d) > 1:
                    new_d = d - assigned
                    if not new_d:
                        return None
                    if new_d != d:
                        domains[i] = new_d
                        changed = True

            for i, j in lt_pairs:
                di, dj = domains[i], domains[j]
                max_j = max(dj)
                min_i = min(di)

                new_di = {x for x in di if x < max_j}
                if not new_di:
                    return None
                if new_di != di:
                    domains[i] = new_di
                    di = new_di
                    changed = True

                new_dj = {y for y in dj if y > min_i}
                if not new_dj:
                    return None
                if new_dj != dj:
                    domains[j] = new_dj
                    changed = True

            for i, j in adj_pairs:
                di, dj = domains[i], domains[j]

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
                di, dj = domains[i], domains[j]

                new_di = {x for x in di if any(abs(x - y) >= 2 for y in dj)}
                if not new_di:
                    return None
                if new_di != di:
                    domains[i] = new_di
                    di = new_di
                    changed = True

                new_dj = {y for y in dj if any(abs(x - y) >= 2 for x in di)}
                if not new_dj:
                    return None
                if new_dj != dj:
                    domains[j] = new_dj
                    changed = True

            if not changed:
                break

        if not has_perfect_matching(domains):
            return None
        return domains

    def value_score(slot: int, val: int, domains: list[set[int]]) -> int:
        score = 0
        for a, b in lt_pairs:
            if a == slot and len(domains[b]) > 1:
                score += sum(1 for y in domains[b] if val < y)
            elif b == slot and len(domains[a]) > 1:
                score += sum(1 for x in domains[a] if x < val)
        for a, b in adj_pairs:
            other = None
            if a == slot:
                other = b
            elif b == slot:
                other = a
            if other is not None and len(domains[other]) > 1:
                score += (val - 1 in domains[other]) + (val + 1 in domains[other])
        for a, b in diff_pairs:
            other = None
            if a == slot:
                other = b
            elif b == slot:
                other = a
            if other is not None and len(domains[other]) > 1:
                score += sum(1 for y in domains[other] if abs(val - y) >= 2)
        return score

    def backtrack(domains: list[set[int]]) -> list[int]:
        domains = [set(d) for d in domains]
        domains = propagate(domains)
        if domains is None:
            return []

        if all(len(d) == 1 for d in domains):
            return [next(iter(d)) for d in domains]

        slot = min((i for i in range(n) if len(domains[i]) > 1), key=lambda k: len(domains[k]))
        values = sorted(domains[slot], key=lambda v: (-value_score(slot, v, domains), v))

        for v in values:
            new_domains = [set(d) for d in domains]
            new_domains[slot] = {v}
            result = backtrack(new_domains)
            if result:
                return result
        return []

    return backtrack([set(range(1, n + 1)) for _ in range(n)])