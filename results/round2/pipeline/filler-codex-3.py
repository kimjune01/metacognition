def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    board = [row[:] for row in grid]
    m, n = len(board), len(board[0])
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    while True:
        to_delete = [[False] * n for _ in range(m)]

        def mark_line(cells):
            for ch in letters:
                start = 0
                while start < len(cells):
                    while start < len(cells) and cells[start][2] not in (ch, "*"):
                        start += 1
                    end = start
                    has_letter = False
                    while end < len(cells) and cells[end][2] in (ch, "*"):
                        if cells[end][2] == ch:
                            has_letter = True
                        end += 1
                    if has_letter and end - start >= 3:
                        for k in range(start, end):
                            r, c, _ = cells[k]
                            to_delete[r][c] = True
                    start = end + 1 if end == start else end

        for r in range(m):
            line = [(r, c, board[r][c]) for c in range(n)]
            mark_line(line)

        for c in range(n):
            line = [(r, c, board[r][c]) for r in range(m)]
            mark_line(line)

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
            write = m - 1
            for i in range(len(vals) - 1, -1, -1):
                board[write][c] = vals[i]
                write -= 1
            while write >= 0:
                board[write][c] = "."
                write -= 1