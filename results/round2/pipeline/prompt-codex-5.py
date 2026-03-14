def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    rows, cols = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = [chr(ord('A') + i) for i in range(26)]

    while True:
        to_delete = [[False] * cols for _ in range(rows)]

        for r in range(rows):
            for ch in letters:
                c = 0
                while c < cols:
                    start = c
                    count_ch = 0
                    while c < cols and board[r][c] != '#' and (board[r][c] == ch or board[r][c] == '*'):
                        if board[r][c] == ch:
                            count_ch += 1
                        c += 1
                    if c - start >= 3 and count_ch > 0:
                        for k in range(start, c):
                            to_delete[r][k] = True
                    if c == start:
                        c += 1

        for c in range(cols):
            for ch in letters:
                r = 0
                while r < rows:
                    start = r
                    count_ch = 0
                    while r < rows and board[r][c] != '#' and (board[r][c] == ch or board[r][c] == '*'):
                        if board[r][c] == ch:
                            count_ch += 1
                        r += 1
                    if r - start >= 3 and count_ch > 0:
                        for k in range(start, r):
                            to_delete[k][c] = True
                    if r == start:
                        r += 1

        changed = False
        for r in range(rows):
            for c in range(cols):
                if to_delete[r][c]:
                    board[r][c] = '.'
                    changed = True

        if not changed:
            return board

        for c in range(cols):
            fallen = [board[r][c] for r in range(rows) if board[r][c] != '.']
            write_r = rows - 1
            for i in range(len(fallen) - 1, -1, -1):
                board[write_r][c] = fallen[i]
                write_r -= 1
            while write_r >= 0:
                board[write_r][c] = '.'
                write_r -= 1