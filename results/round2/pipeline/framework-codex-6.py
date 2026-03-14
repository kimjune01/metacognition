def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    board = [row[:] for row in grid]
    if not board or not board[0]:
        return board

    m, n = len(board), len(board[0])
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    while True:
        marked = [[False] * n for _ in range(m)]

        for i in range(m):
            for ch in letters:
                j = 0
                while j < n:
                    while j < n and board[i][j] not in (ch, "*"):
                        j += 1
                    start = j
                    has_letter = False
                    while j < n and board[i][j] in (ch, "*"):
                        if board[i][j] == ch:
                            has_letter = True
                        j += 1
                    if j - start >= 3 and has_letter:
                        for k in range(start, j):
                            marked[i][k] = True

        for j in range(n):
            for ch in letters:
                i = 0
                while i < m:
                    while i < m and board[i][j] not in (ch, "*"):
                        i += 1
                    start = i
                    has_letter = False
                    while i < m and board[i][j] in (ch, "*"):
                        if board[i][j] == ch:
                            has_letter = True
                        i += 1
                    if i - start >= 3 and has_letter:
                        for k in range(start, i):
                            marked[k][j] = True

        changed = False
        for i in range(m):
            for j in range(n):
                if marked[i][j]:
                    board[i][j] = "."
                    changed = True

        if not changed:
            return board

        for j in range(n):
            vals = [board[i][j] for i in range(m) if board[i][j] != "."]
            write = m - 1
            for v in reversed(vals):
                board[write][j] = v
                write -= 1
            while write >= 0:
                board[write][j] = "."
                write -= 1