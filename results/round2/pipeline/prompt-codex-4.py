def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    board = [row[:] for row in grid]

    def mark_runs() -> list[list[bool]]:
        marked = [[False] * cols for _ in range(rows)]

        for target_ord in range(26):
            target = chr(ord('A') + target_ord)

            for r in range(rows):
                start = 0
                while start < cols:
                    while start < cols and board[r][start] not in (target, '*'):
                        start += 1
                    end = start
                    has_target = False
                    while end < cols and board[r][end] in (target, '*'):
                        if board[r][end] == target:
                            has_target = True
                        end += 1
                    if has_target and end - start >= 3:
                        for c in range(start, end):
                            marked[r][c] = True
                    start = end + 1 if end == start else end

            for c in range(cols):
                start = 0
                while start < rows:
                    while start < rows and board[start][c] not in (target, '*'):
                        start += 1
                    end = start
                    has_target = False
                    while end < rows and board[end][c] in (target, '*'):
                        if board[end][c] == target:
                            has_target = True
                        end += 1
                    if has_target and end - start >= 3:
                        for r in range(start, end):
                            marked[r][c] = True
                    start = end + 1 if end == start else end

        return marked

    while True:
        marked = mark_runs()
        if not any(any(row) for row in marked):
            break

        for r in range(rows):
            for c in range(cols):
                if marked[r][c]:
                    board[r][c] = '.'

        for c in range(cols):
            falling = [board[r][c] for r in range(rows) if board[r][c] != '.']
            write = rows - 1
            for i in range(len(falling) - 1, -1, -1):
                board[write][c] = falling[i]
                write -= 1
            while write >= 0:
                board[write][c] = '.'
                write -= 1

    return board