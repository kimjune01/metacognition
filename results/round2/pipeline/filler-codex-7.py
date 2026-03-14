def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    rows, cols = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def mark_runs() -> list[list[bool]]:
        marked = [[False] * cols for _ in range(rows)]

        for r in range(rows):
            for ch in letters:
                start = 0
                while start < cols:
                    while start < cols and board[r][start] not in (ch, "*"):
                        start += 1
                    end = start
                    has_letter = False
                    while end < cols and board[r][end] in (ch, "*"):
                        if board[r][end] == ch:
                            has_letter = True
                        end += 1
                    if end - start >= 3 and has_letter:
                        for c in range(start, end):
                            marked[r][c] = True
                    start = end + 1 if end == start else end

        for c in range(cols):
            for ch in letters:
                start = 0
                while start < rows:
                    while start < rows and board[start][c] not in (ch, "*"):
                        start += 1
                    end = start
                    has_letter = False
                    while end < rows and board[end][c] in (ch, "*"):
                        if board[end][c] == ch:
                            has_letter = True
                        end += 1
                    if end - start >= 3 and has_letter:
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
                if marked[r][c] and board[r][c] != "#":
                    board[r][c] = "."

        for c in range(cols):
            falling = [board[r][c] for r in range(rows) if board[r][c] != "."]
            write_row = rows - 1
            for i in range(len(falling) - 1, -1, -1):
                board[write_row][c] = falling[i]
                write_row -= 1
            while write_row >= 0:
                board[write_row][c] = "."
                write_row -= 1

    return board