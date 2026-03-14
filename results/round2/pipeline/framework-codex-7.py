def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    board = [row[:] for row in grid]
    m, n = len(board), len(board[0])
    symbols = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def mark_line(line, coords, marked):
        for ch in symbols:
            i = 0
            while i < len(line):
                if line[i] == '#' or (line[i] != '*' and line[i] != ch):
                    i += 1
                    continue
                j = i
                has_symbol = False
                while j < len(line) and line[j] != '#' and (line[j] == '*' or line[j] == ch):
                    if line[j] == ch:
                        has_symbol = True
                    j += 1
                if has_symbol and j - i >= 3:
                    for k in range(i, j):
                        r, c = coords[k]
                        marked[r][c] = True
                i = j

    while True:
        marked = [[False] * n for _ in range(m)]

        for r in range(m):
            line = board[r]
            coords = [(r, c) for c in range(n)]
            mark_line(line, coords, marked)

        for c in range(n):
            line = [board[r][c] for r in range(m)]
            coords = [(r, c) for r in range(m)]
            mark_line(line, coords, marked)

        any_marked = False
        for r in range(m):
            for c in range(n):
                if marked[r][c]:
                    board[r][c] = '.'
                    any_marked = True

        if not any_marked:
            return board

        for c in range(n):
            kept = [board[r][c] for r in range(m) if board[r][c] != '.']
            write = m - 1
            for i in range(len(kept) - 1, -1, -1):
                board[write][c] = kept[i]
                write -= 1
            while write >= 0:
                board[write][c] = '.'
                write -= 1