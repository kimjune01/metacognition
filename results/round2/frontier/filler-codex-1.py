def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from collections import deque

    if n < 0:
        return []
    if n == 0:
        return []

    preds = [set() for _ in range(n)]
    succs = [set() for _ in range(n)]
    adj = [set() for _ in range(n)]
    diff = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            succs[i].add(j)
            preds[j].add(i)
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
        if len(adj[i]) > 2:
            return []
        if adj[i] & diff[i]:
            return []

    indeg = [len(preds[i]) for i in range(n)]
    q = deque(i for i in range(n) if indeg[i] == 0)
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for v in succs[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if seen != n:
        return []

    # Adjacency graph must be a disjoint union of paths (no cycles).
    vis = [False] * n
    for s in range(n):
        if vis[s] or not adj[s]:
            continue
        stack = [s]
        comp = []
        edges2 = 0
        while stack:
            u = stack.pop()
            if vis[u]:
                continue
            vis[u] = True
            comp.append(u)
            edges2 += len(adj[u])
            for v in adj[u]:
                if not vis[v]:
                    stack.append(v)
        edges = edges2 // 2
        if len(comp) > 1 and edges >= len(comp):
            return []

    pos = [-1] * n
    placed = [False] * n
    rem_pred = [len(preds[i]) for i in range(n)]
    order = []

    def candidate_ok(x: int, prev: int) -> bool:
        if placed[x] or rem_pred[x] != 0:
            return False

        if prev != -1 and x in diff[prev]:
            return False

        placed_adj = 0
        placed_adj_prev = False
        for y in adj[x]:
            if placed[y]:
                placed_adj += 1
                if y == prev:
                    placed_adj_prev = True

        if placed_adj > 1:
            return False
        if placed_adj == 1 and not placed_adj_prev:
            return False
        if len(adj[x]) == 2 and placed_adj == 0:
            return False

        if prev != -1:
            needed = [y for y in adj[prev] if not placed[y]]
            if len(needed) > 1:
                return False
            if len(needed) == 1 and needed[0] != x:
                return False

        return True

    def dfs() -> bool:
        k = len(order)
        if k == n:
            for u in range(n):
                for v in adj[u]:
                    if abs(pos[u] - pos[v]) != 1:
                        return False
                for v in diff[u]:
                    if abs(pos[u] - pos[v]) < 2:
                        return False
                for v in succs[u]:
                    if pos[u] >= pos[v]:
                        return False
            return True

        prev = order[-1] if order else -1

        if prev != -1:
            forced = [y for y in adj[prev] if not placed[y]]
            if len(forced) > 1:
                return False
            candidates = forced if forced else None
        else:
            candidates = None

        if candidates is None:
            candidates = [i for i in range(n) if not placed[i] and rem_pred[i] == 0]

            def score(x: int) -> tuple[int, int, int]:
                deg = len(adj[x])
                placed_adj = sum(1 for y in adj[x] if placed[y])
                return (deg == 0, deg == 1, -len(succs[x]) - placed_adj)

            candidates.sort(key=score)

        for x in candidates:
            if not candidate_ok(x, prev):
                continue

            placed[x] = True
            pos[x] = k
            order.append(x)

            changed = []
            for y in succs[x]:
                rem_pred[y] -= 1
                changed.append(y)

            if dfs():
                return True

            for y in changed:
                rem_pred[y] += 1
            order.pop()
            pos[x] = -1
            placed[x] = False

        return False

    if not dfs():
        return []

    ans = [0] * n
    for i in range(n):
        ans[i] = pos[i] + 1
    return ans