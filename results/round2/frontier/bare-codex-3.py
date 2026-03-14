def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    cons = []
    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n) or i == j:
            return []
        if typ not in ("lt", "diff", "adj"):
            return []
        cons.append((typ, i, j))

    domains = [set(range(1, n + 1)) for _ in range(n)]

    def propagate(ds: list[set[int]]) -> list[set[int]] | None:
        while True:
            changed = False

            for d in ds:
                if not d:
                    return None

            singletons = {}
            for idx, d in enumerate(ds):
                if len(d) == 1:
                    v = next(iter(d))
                    if v in singletons and singletons[v] != idx:
                        return None
                    singletons[v] = idx

            used_vals = set(singletons.keys())
            for idx, d in enumerate(ds):
                if len(d) > 1:
                    nd = d - used_vals
                    if not nd:
                        return None
                    if nd != d:
                        ds[idx] = nd
                        changed = True

            for typ, i, j in cons:
                di = ds[i]
                dj = ds[j]

                if typ == "lt":
                    max_j = max(dj)
                    min_i = min(di)

                    ndi = {x for x in di if x < max_j}
                    ndj = {y for y in dj if y > min_i}

                elif typ == "adj":
                    ndi = {x for x in di if (x - 1 in dj or x + 1 in dj)}
                    ndj = {y for y in dj if (y - 1 in di or y + 1 in di)}

                else:  # diff
                    ndi = {x for x in di if any(abs(x - y) >= 2 for y in dj)}
                    ndj = {y for y in dj if any(abs(y - x) >= 2 for x in di)}

                if not ndi or not ndj:
                    return None

                if ndi != di:
                    ds[i] = ndi
                    changed = True
                if ndj != dj:
                    ds[j] = ndj
                    changed = True

            if not changed:
                return ds

    def search(ds: list[set[int]]) -> list[int]:
        ds = [set(d) for d in ds]
        ds = propagate(ds)
        if ds is None:
            return []

        if all(len(d) == 1 for d in ds):
            return [next(iter(d)) for d in ds]

        var = min((i for i in range(n) if len(ds[i]) > 1), key=lambda i: len(ds[i]))
        for v in sorted(ds[var]):
            next_ds = [set(d) for d in ds]
            next_ds[var] = {v}
            ans = search(next_ds)
            if ans:
                return ans
        return []

    return search(domains)