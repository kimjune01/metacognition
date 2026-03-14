def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid:
        return []
    if not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = [chr(c) for c in range(ord('A'), ord('Z') + 1)]

    while True:
        marked = [[False] * n for _ in range(m)]
        found = False

        for i in range(m):
            row = board[i]
            for target in letters:
                j = 0
                while j < n:
                    if row[j] == target or row[j] == '*':
                        k = j
                        has_target = False
                        while k < n and (row[k] == target or row[k] == '*'):
                            if row[k] == target:
                                has_target = True
                            k += 1
                        if has_target and k - j >= 3:
                            found = True
                            for c in range(j, k):
                                marked[i][c] = True
                        j = k
                    else:
                        j += 1

        for j in range(n):
            for target in letters:
                i = 0
                while i < m:
                    if board[i][j] == target or board[i][j] == '*':
                        k = i
                        has_target = False
                        while k < m and (board[k][j] == target or board[k][j] == '*'):
                            if board[k][j] == target:
                                has_target = True
                            k += 1
                        if has_target and k - i >= 3:
                            found = True
                            for r in range(i, k):
                                marked[r][j] = True
                        i = k
                    else:
                        i += 1

        if not found:
            return board

        for i in range(m):
            for j in range(n):
                if marked[i][j]:
                    board[i][j] = '.'

        for j in range(n):
            fallen = [board[i][j] for i in range(m) if board[i][j] != '.']
            write = m - 1
            for idx in range(len(fallen) - 1, -1, -1):
                board[write][j] = fallen[idx]
                write -= 1
            while write >= 0:
                board[write][j] = '.'
                write -= 1