def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid:
        return []
    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def detect_runs() -> list[list[bool]]:
        marked = [[False] * n for _ in range(m)]

        for i in range(m):
            row = board[i]
            for ch in letters:
                j = 0
                while j < n:
                    while j < n and row[j] not in (ch, "*"):
                        j += 1
                    start = j
                    has_letter = False
                    while j < n and row[j] in (ch, "*"):
                        if row[j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - start >= 3:
                        for k in range(start, j):
                            marked[i][k] = True

        for j in range(n):
            col = [board[i][j] for i in range(m)]
            for ch in letters:
                i = 0
                while i < m:
                    while i < m and col[i] not in (ch, "*"):
                        i += 1
                    start = i
                    has_letter = False
                    while i < m and col[i] in (ch, "*"):
                        if col[i] == ch:
                            has_letter = True
                        i += 1
                    if has_letter and i - start >= 3:
                        for k in range(start, i):
                            marked[k][j] = True

        return marked

    while True:
        marked = detect_runs()
        if not any(any(row) for row in marked):
            break

        for i in range(m):
            for j in range(n):
                if marked[i][j] and board[i][j] != "#":
                    board[i][j] = "."

        for j in range(n):
            fallen = [board[i][j] for i in range(m) if board[i][j] != "."]
            write = m - 1
            for i in range(len(fallen) - 1, -1, -1):
                board[write][j] = fallen[i]
                write -= 1
            while write >= 0:
                board[write][j] = "."
                write -= 1

    return board