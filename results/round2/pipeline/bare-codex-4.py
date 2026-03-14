def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid:
        return []
    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    while True:
        to_delete = [[False] * n for _ in range(m)]

        def mark_line(cells, coords):
            for ch in letters:
                i = 0
                while i < len(cells):
                    if cells[i] == ch or cells[i] == "*":
                        j = i
                        has_letter = False
                        while j < len(cells) and (cells[j] == ch or cells[j] == "*"):
                            if cells[j] == ch:
                                has_letter = True
                            j += 1
                        if has_letter and j - i >= 3:
                            for k in range(i, j):
                                r, c = coords[k]
                                to_delete[r][c] = True
                        i = j
                    else:
                        i += 1

        for r in range(m):
            mark_line(board[r], [(r, c) for c in range(n)])

        for c in range(n):
            mark_line([board[r][c] for r in range(m)], [(r, c) for r in range(m)])

        changed = False
        for r in range(m):
            for c in range(n):
                if to_delete[r][c]:
                    board[r][c] = "."
                    changed = True

        if not changed:
            return board

        for c in range(n):
            vals = [board[r][c] for r in range(m) if board[r][c] != "."]
            write_row = m - len(vals)
            for r in range(write_row):
                board[r][c] = "."
            for v in vals:
                board[write_row][c] = v
                write_row += 1