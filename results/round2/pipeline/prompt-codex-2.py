def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    rows, cols = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def mark_runs_in_line(cells, coords, marked):
        n = len(cells)
        i = 0
        while i < n:
            if cells[i] in {'.', '#'}:
                i += 1
                continue
            j = i
            while j < n and cells[j] not in {'.', '#'}:
                j += 1

            segment = cells[i:j]
            seg_len = j - i

            for ch in letters:
                k = 0
                while k < seg_len:
                    if segment[k] != ch and segment[k] != '*':
                        k += 1
                        continue
                    start = k
                    has_letter = False
                    while k < seg_len and (segment[k] == ch or segment[k] == '*'):
                        if segment[k] == ch:
                            has_letter = True
                        k += 1
                    if k - start >= 3 and has_letter:
                        for t in range(start, k):
                            r, c = coords[i + t]
                            marked[r][c] = True
            i = j

    while True:
        marked = [[False] * cols for _ in range(rows)]

        for r in range(rows):
            cells = board[r]
            coords = [(r, c) for c in range(cols)]
            mark_runs_in_line(cells, coords, marked)

        for c in range(cols):
            cells = [board[r][c] for r in range(rows)]
            coords = [(r, c) for r in range(rows)]
            mark_runs_in_line(cells, coords, marked)

        changed = False
        for r in range(rows):
            for c in range(cols):
                if marked[r][c]:
                    board[r][c] = '.'
                    changed = True

        if not changed:
            return board

        for c in range(cols):
            falling = [board[r][c] for r in range(rows) if board[r][c] != '.']
            write_r = rows - 1
            for ch in reversed(falling):
                board[write_r][c] = ch
                write_r -= 1
            while write_r >= 0:
                board[write_r][c] = '.'
                write_r -= 1