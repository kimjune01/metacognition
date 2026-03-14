def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    cons = []
    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ not in ("lt", "diff", "adj"):
            return []
        if i == j:
            return []
        cons.append((typ, i, j))

    initial_domains = [set(range(1, n + 1)) for _ in range(n)]

    def propagate(domains, assignment):
        changed = True
        while changed:
            changed = False

            assigned_values = {assignment[i] for i in range(n) if assignment[i] != 0}
            for i in range(n):
                if assignment[i] == 0:
                    new_dom = domains[i] - assigned_values
                    if not new_dom:
                        return False
                    if new_dom != domains[i]:
                        domains[i] = new_dom
                        changed = True
                else:
                    if domains[i] != {assignment[i]}:
                        domains[i] = {assignment[i]}
                        changed = True

            for typ, i, j in cons:
                di, dj = domains[i], domains[j]

                if typ == "lt":
                    if not di or not dj:
                        return False
                    max_j = max(dj)
                    min_i = min(di)
                    ndi = {a for a in di if a < max_j}
                    ndj = {b for b in dj if b > min_i}
                elif typ == "diff":
                    ndi = {a for a in di if any(abs(a - b) >= 2 for b in dj)}
                    ndj = {b for b in dj if any(abs(a - b) >= 2 for a in di)}
                else:  # adj
                    ndi = {a for a in di if any(abs(a - b) == 1 for b in dj)}
                    ndj = {b for b in dj if any(abs(a - b) == 1 for a in di)}

                if not ndi or not ndj:
                    return False
                if ndi != di:
                    domains[i] = ndi
                    changed = True
                if ndj != dj:
                    domains[j] = ndj
                    changed = True

            for i in range(n):
                if assignment[i] == 0 and len(domains[i]) == 1:
                    v = next(iter(domains[i]))
                    if v in assigned_values:
                        return False
                    assignment[i] = v
                    changed = True

        return True

    def backtrack(domains, assignment):
        if not propagate(domains, assignment):
            return []

        if all(v != 0 for v in assignment):
            return assignment[:]

        i = min((k for k in range(n) if assignment[k] == 0), key=lambda k: len(domains[k]))

        for v in sorted(domains[i]):
            new_assignment = assignment[:]
            new_domains = [d.copy() for d in domains]
            new_assignment[i] = v
            new_domains[i] = {v}
            result = backtrack(new_domains, new_assignment)
            if result:
                return result

        return []

    return backtrack(initial_domains, [0] * n)