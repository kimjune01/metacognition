def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def mark_runs():
        marked = [[False] * n for _ in range(m)]

        def scan_line(coords):
            vals = [board[r][c] for r, c in coords]
            for ch in letters:
                i = 0
                while i < len(vals):
                    if vals[i] != ch and vals[i] != "*":
                        i += 1
                        continue
                    j = i
                    has_letter = False
                    while j < len(vals) and (vals[j] == ch or vals[j] == "*"):
                        if vals[j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - i >= 3:
                        for k in range(i, j):
                            r, c = coords[k]
                            marked[r][c] = True
                    i = j

        for r in range(m):
            scan_line([(r, c) for c in range(n)])
        for c in range(n):
            scan_line([(r, c) for r in range(m)])

        return marked

    while True:
        marked = mark_runs()
        any_marked = any(any(row) for row in marked)
        if not any_marked:
            break

        for r in range(m):
            for c in range(n):
                if marked[r][c]:
                    board[r][c] = "."

        for c in range(n):
            write = m - 1
            for r in range(m - 1, -1, -1):
                if board[r][c] != ".":
                    board[write][c] = board[r][c]
                    write -= 1
            for r in range(write, -1, -1):
                board[r][c] = "."

    return board