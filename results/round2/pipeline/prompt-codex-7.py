def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid:
        return []
    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]

    def mark_runs():
        marked = [[False] * n for _ in range(m)]
        found = False

        for ch_ord in range(ord('A'), ord('Z') + 1):
            ch = chr(ch_ord)

            for i in range(m):
                j = 0
                while j < n:
                    if board[i][j] not in (ch, '*'):
                        j += 1
                        continue
                    start = j
                    has_letter = False
                    while j < n and board[i][j] in (ch, '*'):
                        if board[i][j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - start >= 3:
                        found = True
                        for k in range(start, j):
                            marked[i][k] = True

            for j in range(n):
                i = 0
                while i < m:
                    if board[i][j] not in (ch, '*'):
                        i += 1
                        continue
                    start = i
                    has_letter = False
                    while i < m and board[i][j] in (ch, '*'):
                        if board[i][j] == ch:
                            has_letter = True
                        i += 1
                    if has_letter and i - start >= 3:
                        found = True
                        for k in range(start, i):
                            marked[k][j] = True

        return found, marked

    while True:
        found, marked = mark_runs()
        if not found:
            break

        for i in range(m):
            for j in range(n):
                if marked[i][j] and board[i][j] != '#':
                    board[i][j] = '.'

        for j in range(n):
            stack = []
            for i in range(m):
                if board[i][j] != '.':
                    stack.append(board[i][j])
            write = m - 1
            for k in range(len(stack) - 1, -1, -1):
                board[write][j] = stack[k]
                write -= 1
            while write >= 0:
                board[write][j] = '.'
                write -= 1

    return board