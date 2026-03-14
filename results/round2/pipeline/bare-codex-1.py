def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]

    def mark_runs() -> list[list[bool]]:
        marked = [[False] * n for _ in range(m)]

        for i in range(m):
            row = board[i]
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                start = 0
                while start < n:
                    while start < n and row[start] == "#":
                        start += 1
                    end = start
                    while end < n and row[end] != "#":
                        end += 1

                    k = start
                    while k < end:
                        while k < end and row[k] not in (ch, "*"):
                            k += 1
                        l = k
                        has_letter = False
                        while k < end and row[k] in (ch, "*"):
                            if row[k] == ch:
                                has_letter = True
                            k += 1
                        if has_letter and k - l >= 3:
                            for c in range(l, k):
                                marked[i][c] = True
                    start = end

        for j in range(n):
            col = [board[i][j] for i in range(m)]
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                start = 0
                while start < m:
                    while start < m and col[start] == "#":
                        start += 1
                    end = start
                    while end < m and col[end] != "#":
                        end += 1

                    k = start
                    while k < end:
                        while k < end and col[k] not in (ch, "*"):
                            k += 1
                        l = k
                        has_letter = False
                        while k < end and col[k] in (ch, "*"):
                            if col[k] == ch:
                                has_letter = True
                            k += 1
                        if has_letter and k - l >= 3:
                            for r in range(l, k):
                                marked[r][j] = True
                    start = end

        return marked

    while True:
        marked = mark_runs()
        if not any(any(row) for row in marked):
            return board

        for i in range(m):
            for j in range(n):
                if marked[i][j]:
                    board[i][j] = "."

        for j in range(n):
            vals = [board[i][j] for i in range(m) if board[i][j] != "."]
            write = m - 1
            for k in range(len(vals) - 1, -1, -1):
                board[write][j] = vals[k]
                write -= 1
            while write >= 0:
                board[write][j] = "."
                write -= 1