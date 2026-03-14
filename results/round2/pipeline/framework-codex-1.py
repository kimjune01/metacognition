def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid:
        return []
    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    while True:
        remove = [[False] * n for _ in range(m)]

        for ch in letters:
            for i in range(m):
                j = 0
                while j < n:
                    if board[i][j] != ch and board[i][j] != '*':
                        j += 1
                        continue
                    start = j
                    has_letter = False
                    while j < n and (board[i][j] == ch or board[i][j] == '*'):
                        if board[i][j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - start >= 3:
                        for k in range(start, j):
                            remove[i][k] = True

            for j in range(n):
                i = 0
                while i < m:
                    if board[i][j] != ch and board[i][j] != '*':
                        i += 1
                        continue
                    start = i
                    has_letter = False
                    while i < m and (board[i][j] == ch or board[i][j] == '*'):
                        if board[i][j] == ch:
                            has_letter = True
                        i += 1
                    if has_letter and i - start >= 3:
                        for k in range(start, i):
                            remove[k][j] = True

        if not any(any(row) for row in remove):
            return board

        for i in range(m):
            for j in range(n):
                if remove[i][j]:
                    board[i][j] = '.'

        for j in range(n):
            vals = [board[i][j] for i in range(m) if board[i][j] != '.']
            write = m - 1
            for i in range(m - 1, -1, -1):
                board[i][j] = '.'
            for v in reversed(vals):
                board[write][j] = v
                write -= 1