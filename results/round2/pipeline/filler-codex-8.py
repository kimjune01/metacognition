def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    board = [row[:] for row in grid]
    if not board or not board[0]:
        return board

    m, n = len(board), len(board[0])
    letters = [chr(ord('A') + i) for i in range(26)]

    def detect():
        mark = [[False] * n for _ in range(m)]
        found = False

        for i in range(m):
            row = board[i]
            for ch in letters:
                j = 0
                while j < n:
                    while j < n and row[j] != ch and row[j] != '*':
                        j += 1
                    k = j
                    has_letter = False
                    while k < n and (row[k] == ch or row[k] == '*'):
                        if row[k] == ch:
                            has_letter = True
                        k += 1
                    if has_letter and k - j >= 3:
                        found = True
                        for c in range(j, k):
                            mark[i][c] = True
                    j = max(k, j + 1)

        for j in range(n):
            for ch in letters:
                i = 0
                while i < m:
                    while i < m and board[i][j] != ch and board[i][j] != '*':
                        i += 1
                    k = i
                    has_letter = False
                    while k < m and (board[k][j] == ch or board[k][j] == '*'):
                        if board[k][j] == ch:
                            has_letter = True
                        k += 1
                    if has_letter and k - i >= 3:
                        found = True
                        for r in range(i, k):
                            mark[r][j] = True
                    i = max(k, i + 1)

        return found, mark

    while True:
        found, mark = detect()
        if not found:
            break

        for i in range(m):
            for j in range(n):
                if mark[i][j]:
                    board[i][j] = '.'

        for j in range(n):
            vals = [board[i][j] for i in range(m) if board[i][j] != '.']
            write = m - 1
            for idx in range(len(vals) - 1, -1, -1):
                board[write][j] = vals[idx]
                write -= 1
            while write >= 0:
                board[write][j] = '.'
                write -= 1

    return board