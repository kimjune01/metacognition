def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    board = [row[:] for row in grid]
    m, n = len(board), len(board[0])
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    while True:
        to_delete = [[False] * n for _ in range(m)]

        for r in range(m):
            row = board[r]
            for ch in letters:
                start = 0
                while start < n:
                    while start < n and row[start] not in (ch, '*'):
                        start += 1
                    end = start
                    has_letter = False
                    while end < n and row[end] in (ch, '*'):
                        if row[end] == ch:
                            has_letter = True
                        end += 1
                    if end - start >= 3 and has_letter:
                        for c in range(start, end):
                            to_delete[r][c] = True
                    start = end + 1 if end == start else end

        for c in range(n):
            for ch in letters:
                start = 0
                while start < m:
                    while start < m and board[start][c] not in (ch, '*'):
                        start += 1
                    end = start
                    has_letter = False
                    while end < m and board[end][c] in (ch, '*'):
                        if board[end][c] == ch:
                            has_letter = True
                        end += 1
                    if end - start >= 3 and has_letter:
                        for r in range(start, end):
                            to_delete[r][c] = True
                    start = end + 1 if end == start else end

        any_deleted = False
        for r in range(m):
            for c in range(n):
                if to_delete[r][c]:
                    board[r][c] = '.'
                    any_deleted = True

        if not any_deleted:
            return board

        for c in range(n):
            vals = [board[r][c] for r in range(m) if board[r][c] != '.']
            write = m - 1
            for i in range(len(vals) - 1, -1, -1):
                board[write][c] = vals[i]
                write -= 1
            while write >= 0:
                board[write][c] = '.'
                write -= 1