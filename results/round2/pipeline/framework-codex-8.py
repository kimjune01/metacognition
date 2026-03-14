def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = [chr(ord('A') + i) for i in range(26)]

    def mark_runs_line(values):
        marked = [False] * len(values)
        for ch in letters:
            start = 0
            count_ch = 0
            for i, v in enumerate(values + [None]):
                if v == ch or v == '*':
                    if v == ch:
                        count_ch += 1
                else:
                    if i - start >= 3 and count_ch > 0:
                        for k in range(start, i):
                            marked[k] = True
                    start = i + 1
                    count_ch = 0
        return marked

    while True:
        to_delete = [[False] * n for _ in range(m)]

        for r in range(m):
            marks = mark_runs_line(board[r])
            for c in range(n):
                if marks[c]:
                    to_delete[r][c] = True

        for c in range(n):
            col = [board[r][c] for r in range(m)]
            marks = mark_runs_line(col)
            for r in range(m):
                if marks[r]:
                    to_delete[r][c] = True

        changed = False
        for r in range(m):
            for c in range(n):
                if to_delete[r][c]:
                    board[r][c] = '.'
                    changed = True

        if not changed:
            return board

        for c in range(n):
            kept = [board[r][c] for r in range(m) if board[r][c] != '.']
            write = m - 1
            for v in reversed(kept):
                board[write][c] = v
                write -= 1
            while write >= 0:
                board[write][c] = '.'
                write -= 1