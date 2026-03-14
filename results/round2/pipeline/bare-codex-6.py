def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    board = [row[:] for row in grid]
    m, n = len(board), len(board[0])

    def mark_runs():
        marked = [[False] * n for _ in range(m)]

        def process_line(coords):
            vals = [board[r][c] for r, c in coords]
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                i = 0
                while i < len(vals):
                    if vals[i] == ch or vals[i] == "*":
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
                    else:
                        i += 1

        for r in range(m):
            process_line([(r, c) for c in range(n)])
        for c in range(n):
            process_line([(r, c) for r in range(m)])

        return marked

    while True:
        marked = mark_runs()
        any_marked = False
        for r in range(m):
            for c in range(n):
                if marked[r][c]:
                    board[r][c] = "."
                    any_marked = True

        if not any_marked:
            return board

        for c in range(n):
            col = [board[r][c] for r in range(m) if board[r][c] != "."]
            write = m - 1
            for i in range(len(col) - 1, -1, -1):
                board[write][c] = col[i]
                write -= 1
            while write >= 0:
                board[write][c] = "."
                write -= 1