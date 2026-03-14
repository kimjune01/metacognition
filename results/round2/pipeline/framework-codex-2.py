def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]

    def mark_runs() -> set[tuple[int, int]]:
        marked = set()

        for i in range(m):
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                j = 0
                while j < n:
                    if board[i][j] not in (ch, "*"):
                        j += 1
                        continue
                    start = j
                    has_letter = False
                    while j < n and board[i][j] in (ch, "*"):
                        if board[i][j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - start >= 3:
                        for c in range(start, j):
                            marked.add((i, c))

        for j in range(n):
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                i = 0
                while i < m:
                    if board[i][j] not in (ch, "*"):
                        i += 1
                        continue
                    start = i
                    has_letter = False
                    while i < m and board[i][j] in (ch, "*"):
                        if board[i][j] == ch:
                            has_letter = True
                        i += 1
                    if has_letter and i - start >= 3:
                        for r in range(start, i):
                            marked.add((r, j))

        return marked

    while True:
        marked = mark_runs()
        if not marked:
            return board

        for r, c in marked:
            if board[r][c] != "#":
                board[r][c] = "."

        for c in range(n):
            cells = [board[r][c] for r in range(m) if board[r][c] != "."]
            write = m - 1
            for r in range(m - 1, -1, -1):
                board[r][c] = "."
            for val in reversed(cells):
                board[write][c] = val
                write -= 1