def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]

    def mark_line(line):
        marked = [False] * len(line)
        for target_ord in range(ord('A'), ord('Z') + 1):
            target = chr(target_ord)
            start = -1
            count_target = 0
            for i in range(len(line) + 1):
                ch = line[i] if i < len(line) else None
                if ch == target or ch == '*':
                    if start == -1:
                        start = i
                        count_target = 0
                    if ch == target:
                        count_target += 1
                else:
                    if start != -1 and i - start >= 3 and count_target > 0:
                        for j in range(start, i):
                            marked[j] = True
                    start = -1
                    count_target = 0
        return marked

    while True:
        to_delete = [[False] * n for _ in range(m)]

        for r in range(m):
            marks = mark_line(board[r])
            for c in range(n):
                if marks[c]:
                    to_delete[r][c] = True

        for c in range(n):
            col = [board[r][c] for r in range(m)]
            marks = mark_line(col)
            for r in range(m):
                if marks[r]:
                    to_delete[r][c] = True

        found = False
        for r in range(m):
            for c in range(n):
                if to_delete[r][c]:
                    board[r][c] = '.'
                    found = True

        if not found:
            return board

        for c in range(n):
            fallen = [board[r][c] for r in range(m) if board[r][c] != '.']
            empties = m - len(fallen)
            for r in range(empties):
                board[r][c] = '.'
            for i, val in enumerate(fallen):
                board[empties + i][c] = val