def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]

    def mark_line(cells, coords, marked):
        for ch_ord in range(26):
            ch = chr(ord('A') + ch_ord)
            i = 0
            while i < len(cells):
                if cells[i] == ch or cells[i] == '*':
                    j = i
                    has_letter = False
                    while j < len(cells) and (cells[j] == ch or cells[j] == '*'):
                        if cells[j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - i >= 3:
                        for k in range(i, j):
                            r, c = coords[k]
                            marked[r][c] = True
                    i = j
                else:
                    i += 1

    while True:
        marked = [[False] * n for _ in range(m)]

        for r in range(m):
            cells = board[r]
            coords = [(r, c) for c in range(n)]
            mark_line(cells, coords, marked)

        for c in range(n):
            cells = [board[r][c] for r in range(m)]
            coords = [(r, c) for r in range(m)]
            mark_line(cells, coords, marked)

        any_marked = False
        for r in range(m):
            for c in range(n):
                if marked[r][c]:
                    board[r][c] = '.'
                    any_marked = True

        if not any_marked:
            break

        for c in range(n):
            kept = [board[r][c] for r in range(m) if board[r][c] != '.']
            write_r = m - 1
            for i in range(len(kept) - 1, -1, -1):
                board[write_r][c] = kept[i]
                write_r -= 1
            while write_r >= 0:
                board[write_r][c] = '.'
                write_r -= 1

    return board