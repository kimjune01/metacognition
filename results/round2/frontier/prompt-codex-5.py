def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return []

    lt_pairs = []
    diff_pairs = []
    adj_pairs = []

    adj_sets = [set() for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt_pairs.append((i, j))
        elif typ == "diff":
            if i == j:
                return []
            a, b = (i, j) if i < j else (j, i)
            diff_pairs.append((a, b))
        elif typ == "adj":
            if i == j:
                return []
            if j not in adj_sets[i]:
                adj_sets[i].add(j)
                adj_sets[j].add(i)
            a, b = (i, j) if i < j else (j, i)
            adj_pairs.append((a, b))
        else:
            return []

    for v in range(n):
        if len(adj_sets[v]) > 2:
            return []

    block_of = [-1] * n
    idx_in_block = [-1] * n
    blocks = []
    seen = [False] * n

    for s in range(n):
        if seen[s]:
            continue
        if len(adj_sets[s]) == 0:
            seen[s] = True
            block_id = len(blocks)
            block_of[s] = block_id
            idx_in_block[s] = 0
            blocks.append([s])
            continue

        comp = []
        stack = [s]
        seen[s] = True
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj_sets[u]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)

        endpoints = [v for v in comp if len(adj_sets[v]) == 1]
        if len(comp) > 1 and len(endpoints) != 2:
            return []

        start = min(endpoints)
        order = []
        prev = -1
        cur = start
        while True:
            order.append(cur)
            nxt = None
            for v in adj_sets[cur]:
                if v != prev:
                    nxt = v
                    break
            if nxt is None:
                break
            prev, cur = cur, nxt

        if len(order) != len(comp):
            return []

        block_id = len(blocks)
        for idx, v in enumerate(order):
            block_of[v] = block_id
            idx_in_block[v] = idx
        blocks.append(order)

    m = len(blocks)
    allowed_orients = [[True, True] for _ in range(m)]

    for a, b in adj_pairs:
        ba, bb = block_of[a], block_of[b]
        if ba != bb:
            return []
        da = idx_in_block[a]
        db = idx_in_block[b]
        if abs(da - db) != 1:
            return []

    for a, b in diff_pairs:
        ba, bb = block_of[a], block_of[b]
        if ba == bb and abs(idx_in_block[a] - idx_in_block[b]) < 2:
            return []

    for a, b in lt_pairs:
        ba, bb = block_of[a], block_of[b]
        if ba != bb:
            continue
        ia = idx_in_block[a]
        ib = idx_in_block[b]
        normal_ok = ia < ib
        reverse_ok = ia > ib
        allowed_orients[ba][0] &= normal_ok
        allowed_orients[ba][1] &= reverse_ok

    for b in range(m):
        if not allowed_orients[b][0] and not allowed_orients[b][1]:
            return []

    succ = [set() for _ in range(m)]
    indeg = [0] * m
    for a, b in lt_pairs:
        ba, bb = block_of[a], block_of[b]
        if ba == bb:
            continue
        if bb not in succ[ba]:
            succ[ba].add(bb)
            indeg[bb] += 1

    start_slot = [[0, 0] for _ in range(m)]
    end_slot = [[0, 0] for _ in range(m)]
    for b, block in enumerate(blocks):
        start_slot[b][0] = block[0]
        end_slot[b][0] = block[-1]
        start_slot[b][1] = block[-1]
        end_slot[b][1] = block[0]

    forbidden = set()
    diff_seen = set(diff_pairs)
    for a, b in diff_seen:
        ba, bb = block_of[a], block_of[b]
        if ba == bb:
            continue
        for oa in (0, 1):
            for ob in (0, 1):
                if end_slot[ba][oa] == a and start_slot[bb][ob] == b:
                    forbidden.add((ba, oa, bb, ob))
                if end_slot[ba][oa] == b and start_slot[bb][ob] == a:
                    forbidden.add((ba, oa, bb, ob))
                if end_slot[bb][ob] == a and start_slot[ba][oa] == b:
                    forbidden.add((bb, ob, ba, oa))
                if end_slot[bb][ob] == b and start_slot[ba][oa] == a:
                    forbidden.add((bb, ob, ba, oa))

    used = [False] * m
    order_blocks = []
    indeg_cur = indeg[:]

    def dfs(prev_block: int, prev_orient: int) -> bool:
        if len(order_blocks) == m:
            return True

        avail = [b for b in range(m) if not used[b] and indeg_cur[b] == 0]
        if not avail:
            return False

        def score(b: int) -> tuple[int, int, int]:
            cnt = 0
            for o in (0, 1):
                if not allowed_orients[b][o]:
                    continue
                if prev_block != -1 and (prev_block, prev_orient, b, o) in forbidden:
                    continue
                cnt += 1
            return (cnt, len(succ[b]), b)

        avail.sort(key=score)

        for b in avail:
            for o in (0, 1):
                if not allowed_orients[b][o]:
                    continue
                if prev_block != -1 and (prev_block, prev_orient, b, o) in forbidden:
                    continue

                used[b] = True
                order_blocks.append((b, o))
                changed = []
                for nb in succ[b]:
                    indeg_cur[nb] -= 1
                    changed.append(nb)

                if dfs(b, o):
                    return True

                for nb in changed:
                    indeg_cur[nb] += 1
                order_blocks.pop()
                used[b] = False

        return False

    if not dfs(-1, 0):
        return []

    slot_order = []
    for b, o in order_blocks:
        block = blocks[b]
        if o == 0:
            slot_order.extend(block)
        else:
            slot_order.extend(reversed(block))

    if len(slot_order) != n:
        return []

    ans = [0] * n
    for pos, slot in enumerate(slot_order, 1):
        ans[slot] = pos
    return ans