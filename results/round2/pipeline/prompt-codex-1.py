def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid:
        return []
    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    symbols = [chr(ord('A') + i) for i in range(26)]

    while True:
        marked = [[False] * n for _ in range(m)]

        for i in range(m):
            j = 0
            while j < n:
                if board[i][j] == '#':
                    j += 1
                    continue
                k = j
                while k < n and board[i][k] != '#':
                    k += 1
                for sym in symbols:
                    p = j
                    while p < k:
                        if board[i][p] != sym and board[i][p] != '*':
                            p += 1
                            continue
                        q = p
                        has_sym = False
                        while q < k and (board[i][q] == sym or board[i][q] == '*'):
                            if board[i][q] == sym:
                                has_sym = True
                            q += 1
                        if has_sym and q - p >= 3:
                            for x in range(p, q):
                                marked[i][x] = True
                        p = q
                j = k + 1

        for j in range(n):
            i = 0
            while i < m:
                if board[i][j] == '#':
                    i += 1
                    continue
                k = i
                while k < m and board[k][j] != '#':
                    k += 1
                for sym in symbols:
                    p = i
                    while p < k:
                        if board[p][j] != sym and board[p][j] != '*':
                            p += 1
                            continue
                        q = p
                        has_sym = False
                        while q < k and (board[q][j] == sym or board[q][j] == '*'):
                            if board[q][j] == sym:
                                has_sym = True
                            q += 1
                        if has_sym and q - p >= 3:
                            for x in range(p, q):
                                marked[x][j] = True
                        p = q
                i = k + 1

        changed = False
        for i in range(m):
            for j in range(n):
                if marked[i][j]:
                    board[i][j] = '.'
                    changed = True

        if not changed:
            return board

        for j in range(n):
            vals = [board[i][j] for i in range(m) if board[i][j] != '.']
            write = m - 1
            for v in reversed(vals):
                board[write][j] = v
                write -= 1
            while write >= 0:
                board[write][j] = '.'
                write -= 1