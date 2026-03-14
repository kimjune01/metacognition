def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def mark_runs():
        marked = [[False] * n for _ in range(m)]
        found = False

        for r in range(m):
            for ch in letters:
                c = 0
                while c < n:
                    if board[r][c] == ch or board[r][c] == "*":
                        start = c
                        has_letter = board[r][c] == ch
                        c += 1
                        while c < n and (board[r][c] == ch or board[r][c] == "*"):
                            has_letter = has_letter or board[r][c] == ch
                            c += 1
                        if has_letter and c - start >= 3:
                            found = True
                            for k in range(start, c):
                                marked[r][k] = True
                    else:
                        c += 1

        for c in range(n):
            for ch in letters:
                r = 0
                while r < m:
                    if board[r][c] == ch or board[r][c] == "*":
                        start = r
                        has_letter = board[r][c] == ch
                        r += 1
                        while r < m and (board[r][c] == ch or board[r][c] == "*"):
                            has_letter = has_letter or board[r][c] == ch
                            r += 1
                        if has_letter and r - start >= 3:
                            found = True
                            for k in range(start, r):
                                marked[k][c] = True
                    else:
                        r += 1

        return found, marked

    while True:
        found, marked = mark_runs()
        if not found:
            break

        for r in range(m):
            for c in range(n):
                if marked[r][c]:
                    board[r][c] = "."

        for c in range(n):
            vals = [board[r][c] for r in range(m) if board[r][c] != "."]
            write = m - 1
            for i in range(len(vals) - 1, -1, -1):
                board[write][c] = vals[i]
                write -= 1
            while write >= 0:
                board[write][c] = "."
                write -= 1

    return board