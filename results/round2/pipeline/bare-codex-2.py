def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    board = [row[:] for row in grid]
    if not board or not board[0]:
        return board

    m, n = len(board), len(board[0])

    def mark_runs() -> list[list[bool]]:
        marked = [[False] * n for _ in range(m)]

        for ch_ord in range(26):
            ch = chr(ord('A') + ch_ord)

            for i in range(m):
                j = 0
                while j < n:
                    if board[i][j] == '#' or (board[i][j] != ch and board[i][j] != '*'):
                        j += 1
                        continue
                    start = j
                    has_letter = False
                    while j < n and board[i][j] != '#' and (board[i][j] == ch or board[i][j] == '*'):
                        if board[i][j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - start >= 3:
                        for k in range(start, j):
                            marked[i][k] = True

            for j in range(n):
                i = 0
                while i < m:
                    if board[i][j] == '#' or (board[i][j] != ch and board[i][j] != '*'):
                        i += 1
                        continue
                    start = i
                    has_letter = False
                    while i < m and board[i][j] != '#' and (board[i][j] == ch or board[i][j] == '*'):
                        if board[i][j] == ch:
                            has_letter = True
                        i += 1
                    if has_letter and i - start >= 3:
                        for k in range(start, i):
                            marked[k][j] = True

        return marked

    while True:
        marked = mark_runs()
        if not any(any(row) for row in marked):
            break

        for i in range(m):
            for j in range(n):
                if marked[i][j] and board[i][j] != '#':
                    board[i][j] = '.'

        for j in range(n):
            write = m - 1
            for i in range(m - 1, -1, -1):
                if board[i][j] != '.':
                    board[write][j] = board[i][j]
                    write -= 1
            for i in range(write, -1, -1):
                board[i][j] = '.'

    return board