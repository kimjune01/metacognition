def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def mark_line(line_cells, positions, to_delete):
        length = len(line_cells)
        for ch in letters:
            i = 0
            while i < length:
                if line_cells[i] == ch or line_cells[i] == "*":
                    j = i
                    has_letter = False
                    while j < length and (line_cells[j] == ch or line_cells[j] == "*"):
                        if line_cells[j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - i >= 3:
                        for k in range(i, j):
                            r, c = positions[k]
                            to_delete[r][c] = True
                    i = j
                else:
                    i += 1

    while True:
        to_delete = [[False] * n for _ in range(m)]

        for r in range(m):
            cells = board[r]
            positions = [(r, c) for c in range(n)]
            mark_line(cells, positions, to_delete)

        for c in range(n):
            cells = [board[r][c] for r in range(m)]
            positions = [(r, c) for r in range(m)]
            mark_line(cells, positions, to_delete)

        changed = False
        for r in range(m):
            for c in range(n):
                if to_delete[r][c]:
                    board[r][c] = "."
                    changed = True

        if not changed:
            return board

        for c in range(n):
            kept = [board[r][c] for r in range(m) if board[r][c] != "."]
            write = m - 1
            for i in range(len(kept) - 1, -1, -1):
                board[write][c] = kept[i]
                write -= 1
            while write >= 0:
                board[write][c] = "."
                write -= 1