def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    if n < 0:
        return []
    if n == 0:
        return [] if constraints else []

    lt_edges = [0] * n
    adj_list = [[] for _ in range(n)]
    diff_list = [[] for _ in range(n)]

    for typ, i, j in constraints:
        if not (0 <= i < n and 0 <= j < n):
            return []
        if typ == "lt":
            if i == j:
                return []
            lt_edges[i] |= 1 << j
        elif typ == "adj":
            if i == j:
                return []
            adj_list[i].append(j)
            adj_list[j].append(i)
        elif typ == "diff":
            if i == j:
                return []
            diff_list[i].append(j)
            diff_list[j].append(i)
        else:
            return []

    reach = lt_edges[:]
    for k in range(n):
        kbit = 1 << k
        rk = reach[k]
        for i in range(n):
            if reach[i] & kbit:
                reach[i] |= rk

    for i in range(n):
        if (reach[i] >> i) & 1:
            return []

    pred = [0] * n
    for i in range(n):
        m = reach[i]
        while m:
            b = m & -m
            j = b.bit_length() - 1
            pred[j] |= 1 << i
            m ^= b

    full = (1 << n) - 1
    lt_mask = [0] * (n + 1)
    gt_mask = [0] * (n + 1)
    adj_mask = [0] * (n + 1)
    diff_mask = [0] * (n + 1)

    for v in range(1, n + 1):
        lt_mask[v] = (1 << (v - 1)) - 1
        gt_mask[v] = full ^ ((1 << v) - 1)
        am = 0
        if v > 1:
            am |= 1 << (v - 2)
        if v < n:
            am |= 1 << v
        adj_mask[v] = am
        diff_mask[v] = full & ~am & ~(1 << (v - 1))

    domains = [0] * n
    for i in range(n):
        lower = pred[i].bit_count() + 1
        upper = n - reach[i].bit_count()
        if lower > upper:
            return []
        domains[i] = ((1 << upper) - 1) ^ ((1 << (lower - 1)) - 1)

    assigned = [0] * n

    def consistent_assigned(slot: int, val: int) -> bool:
        m = pred[slot]
        while m:
            b = m & -m
            t = b.bit_length() - 1
            if assigned[t] and assigned[t] >= val:
                return False
            m ^= b

        m = reach[slot]
        while m:
            b = m & -m
            t = b.bit_length() - 1
            if assigned[t] and assigned[t] <= val:
                return False
            m ^= b

        for t in adj_list[slot]:
            if assigned[t] and abs(assigned[t] - val) != 1:
                return False

        for t in diff_list[slot]:
            if assigned[t] and abs(assigned[t] - val) < 2:
                return False

        return True

    def search(cur_domains: list[int], remaining: int) -> list[int] | None:
        if remaining == 0:
            return assigned[:]

        slot = -1
        slot_mask = 0
        best = n + 1
        for i in range(n):
            if assigned[i] == 0:
                c = cur_domains[i].bit_count()
                if c == 0:
                    return None
                if c < best:
                    best = c
                    slot = i
                    slot_mask = cur_domains[i]
                    if c == 1:
                        break

        m = slot_mask
        while m:
            b = m & -m
            m ^= b
            val = b.bit_length()

            if not consistent_assigned(slot, val):
                continue

            assigned[slot] = val
            new_domains = cur_domains[:]
            new_domains[slot] = b
            failed = False

            keep = full ^ b
            for t in range(n):
                if assigned[t] == 0:
                    nm = new_domains[t] & keep
                    if nm == 0:
                        failed = True
                        break
                    new_domains[t] = nm
            if failed:
                assigned[slot] = 0
                continue

            pm = pred[slot]
            while pm and not failed:
                pb = pm & -pm
                t = pb.bit_length() - 1
                pm ^= pb
                if assigned[t]:
                    if assigned[t] >= val:
                        failed = True
                else:
                    nm = new_domains[t] & lt_mask[val]
                    if nm == 0:
                        failed = True
                    else:
                        new_domains[t] = nm

            sm = reach[slot]
            while sm and not failed:
                sb = sm & -sm
                t = sb.bit_length() - 1
                sm ^= sb
                if assigned[t]:
                    if assigned[t] <= val:
                        failed = True
                else:
                    nm = new_domains[t] & gt_mask[val]
                    if nm == 0:
                        failed = True
                    else:
                        new_domains[t] = nm

            for t in adj_list[slot]:
                if failed:
                    break
                if assigned[t]:
                    if abs(assigned[t] - val) != 1:
                        failed = True
                else:
                    nm = new_domains[t] & adj_mask[val]
                    if nm == 0:
                        failed = True
                    else:
                        new_domains[t] = nm

            for t in diff_list[slot]:
                if failed:
                    break
                if assigned[t]:
                    if abs(assigned[t] - val) < 2:
                        failed = True
                else:
                    nm = new_domains[t] & diff_mask[val]
                    if nm == 0:
                        failed = True
                    else:
                        new_domains[t] = nm

            if not failed:
                result = search(new_domains, remaining - 1)
                if result is not None:
                    return result

            assigned[slot] = 0

        return None

    result = search(domains, n)
    return result if result is not None else []