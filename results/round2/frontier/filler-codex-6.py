def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    neighbors = [[] for _ in range(n)]
    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            if typ in ("lt", "diff", "adj"):
                return []
        neighbors[i].append((typ, i, j))
        neighbors[j].append((typ, i, j))

    def supported(typ: str, left_vals: set[int], right_vals: set[int]) -> tuple[set[int], set[int]]:
        if not left_vals or not right_vals:
            return set(), set()

        if typ == "lt":
            max_right = max(right_vals)
            min_left = min(left_vals)
            new_left = {v for v in left_vals if v < max_right}
            new_right = {v for v in right_vals if v > min_left}
            return new_left, new_right

        if typ == "adj":
            new_left = {v for v in left_vals if (v - 1 in right_vals) or (v + 1 in right_vals)}
            new_right = {v for v in right_vals if (v - 1 in left_vals) or (v + 1 in left_vals)}
            return new_left, new_right

        if typ == "diff":
            new_left = {v for v in left_vals if any(abs(v - w) >= 2 for w in right_vals)}
            new_right = {v for v in right_vals if any(abs(v - w) >= 2 for w in left_vals)}
            return new_left, new_right

        return set(left_vals), set(right_vals)

    def propagate(domains: list[set[int]]) -> list[set[int]] | None:
        changed = True
        while changed:
            changed = False

            singletons = {}
            for idx, d in enumerate(domains):
                if not d:
                    return None
                if len(d) == 1:
                    v = next(iter(d))
                    if v in singletons and singletons[v] != idx:
                        return None
                    singletons[v] = idx

            taken = set(singletons.keys())
            for idx, d in enumerate(domains):
                if len(d) > 1:
                    nd = d - taken
                    if not nd:
                        return None
                    if nd != d:
                        domains[idx] = nd
                        changed = True

            for typ, i, j in constraints:
                left, right = supported(typ, domains[i], domains[j])
                if not left or not right:
                    return None
                if left != domains[i]:
                    domains[i] = left
                    changed = True
                if right != domains[j]:
                    domains[j] = right
                    changed = True

        return domains

    def search(domains: list[set[int]]) -> list[int]:
        domains = [set(d) for d in domains]
        domains = propagate(domains)
        if domains is None:
            return []

        if all(len(d) == 1 for d in domains):
            return [next(iter(d)) for d in domains]

        var = min((i for i in range(n) if len(domains[i]) > 1), key=lambda i: len(domains[i]))

        def value_score(v: int) -> int:
            score = 0
            for typ, i, j in neighbors[var]:
                other = j if i == var else i
                od = domains[other]
                if typ == "lt":
                    if i == var:
                        score += sum(1 for w in od if v < w)
                    else:
                        score += sum(1 for w in od if w < v)
                elif typ == "adj":
                    score += int(v - 1 in od) + int(v + 1 in od)
                elif typ == "diff":
                    score += sum(1 for w in od if abs(v - w) >= 2)
            return -score

        for v in sorted(domains[var], key=value_score):
            new_domains = [set(d) for d in domains]
            new_domains[var] = {v}
            result = search(new_domains)
            if result:
                return result

        return []

    initial_domains = [set(range(1, n + 1)) for _ in range(n)]
    return search(initial_domains)