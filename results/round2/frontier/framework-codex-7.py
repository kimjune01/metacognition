def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n <= 0:
        return []

    lt_edges = [[] for _ in range(n)]
    adj_pairs = [[] for _ in range(n)]
    diff_pairs = [[] for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if i == j:
            if typ == "lt" or typ == "adj":
                return []
            continue
        if typ == "lt":
            lt_edges[i].append(j)
        elif typ == "adj":
            adj_pairs[i].append(j)
            adj_pairs[j].append(i)
        elif typ == "diff":
            diff_pairs[i].append(j)
            diff_pairs[j].append(i)
        else:
            return []

    # Transitive closure for lt constraints and cycle detection.
    reach = [0] * n
    for i in range(n):
        mask = 0
        stack = lt_edges[i][:]
        seen = 0
        while stack:
            u = stack.pop()
            bit = 1 << u
            if seen & bit:
                continue
            seen |= bit
            mask |= bit
            stack.extend(lt_edges[u])
        if mask & (1 << i):
            return []
        reach[i] = mask

    pred_mask = [0] * n
    succ_mask = reach[:]
    for i in range(n):
        m = succ_mask[i]
        while m:
            lsb = m & -m
            j = lsb.bit_length() - 1
            pred_mask[j] |= 1 << i
            m ^= lsb

    pred_count = [pred_mask[i].bit_count() for i in range(n)]
    succ_count = [succ_mask[i].bit_count() for i in range(n)]

    # Early contradiction checks among relation types.
    for i in range(n):
        if succ_mask[i] & pred_mask[i]:
            return []
        for j in adj_pairs[i]:
            if j < i:
                continue
            if ((succ_mask[i] >> j) & 1) or ((succ_mask[j] >> i) & 1):
                return []
        for j in diff_pairs[i]:
            if j < i:
                continue
            if n == 1:
                return []
            # diff is always satisfied for lt pairs because values are unique integers.
            # no extra contradiction here.

    all_values_mask = (1 << n) - 1
    assigned = [-1] * n
    unassigned_mask = (1 << n) - 1

    def feasible_value(slot: int, v: int, avail_mask: int, unassigned_mask_now: int) -> bool:
        bit_v = 1 << (v - 1)
        if not (avail_mask & bit_v):
            return False

        if v < pred_count[slot] + 1 or v > n - succ_count[slot]:
            return False

        unassigned_preds = (pred_mask[slot] & unassigned_mask_now).bit_count()
        unassigned_succs = (succ_mask[slot] & unassigned_mask_now).bit_count()

        lower_avail = (avail_mask & ((1 << (v - 1)) - 1)).bit_count()
        upper_avail = (avail_mask & (all_values_mask ^ ((1 << v) - 1))).bit_count()

        if lower_avail < unassigned_preds or upper_avail < unassigned_succs:
            return False

        for j in adj_pairs[slot]:
            aj = assigned[j]
            if aj != -1 and abs(v - aj) != 1:
                return False

        for j in diff_pairs[slot]:
            aj = assigned[j]
            if aj != -1 and abs(v - aj) < 2:
                return False

        pm = pred_mask[slot]
        while pm:
            lsb = pm & -pm
            j = lsb.bit_length() - 1
            aj = assigned[j]
            if aj != -1 and not (aj < v):
                return False
            pm ^= lsb

        sm = succ_mask[slot]
        while sm:
            lsb = sm & -sm
            j = lsb.bit_length() - 1
            aj = assigned[j]
            if aj != -1 and not (v < aj):
                return False
            sm ^= lsb

        return True

    def domain_values(slot: int, avail_mask: int, unassigned_mask_now: int) -> list[int]:
        vals = []
        m = avail_mask
        while m:
            lsb = m & -m
            v = lsb.bit_length()
            if feasible_value(slot, v, avail_mask, unassigned_mask_now ^ (1 << slot)):
                vals.append(v)
            m ^= lsb
        return vals

    def forward_check(avail_mask: int, unassigned_mask_now: int) -> bool:
        m = unassigned_mask_now
        while m:
            lsb = m & -m
            slot = lsb.bit_length() - 1
            if not domain_values(slot, avail_mask, unassigned_mask_now):
                return False
            m ^= lsb
        return True

    def choose_slot(avail_mask: int, unassigned_mask_now: int):
        best_slot = -1
        best_domain = None
        m = unassigned_mask_now
        while m:
            lsb = m & -m
            slot = lsb.bit_length() - 1
            dom = domain_values(slot, avail_mask, unassigned_mask_now)
            if not dom:
                return slot, dom
            if best_domain is None or len(dom) < len(best_domain):
                best_slot = slot
                best_domain = dom
                if len(best_domain) == 1:
                    break
            m ^= lsb
        return best_slot, best_domain

    def backtrack(avail_mask: int, unassigned_mask_now: int) -> bool:
        if unassigned_mask_now == 0:
            return True

        slot, dom = choose_slot(avail_mask, unassigned_mask_now)
        if not dom:
            return False

        for v in dom:
            assigned[slot] = v
            new_avail = avail_mask ^ (1 << (v - 1))
            new_unassigned = unassigned_mask_now ^ (1 << slot)

            if forward_check(new_avail, new_unassigned) and backtrack(new_avail, new_unassigned):
                return True

            assigned[slot] = -1

        return False

    if backtrack(all_values_mask, unassigned_mask):
        return assigned
    return []