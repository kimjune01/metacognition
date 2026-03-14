def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid:
        return []
    m, n = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def mark_line(line, mark_positions):
        for ch in letters:
            i = 0
            while i < len(line):
                if line[i] == ch or line[i] == "*":
                    j = i
                    has_letter = False
                    while j < len(line) and (line[j] == ch or line[j] == "*"):
                        if line[j] == ch:
                            has_letter = True
                        j += 1
                    if has_letter and j - i >= 3:
                        for k in range(i, j):
                            mark_positions(k)
                    i = j
                else:
                    i += 1

    while True:
        marked = [[False] * n for _ in range(m)]

        for r in range(m):
            line = board[r]
            mark_line(line, lambda c, r=r: marked[r].__setitem__(c, True))

        for c in range(n):
            line = [board[r][c] for r in range(m)]
            mark_line(line, lambda r, c=c: marked[r].__setitem__(c, True))

        any_marked = False
        for r in range(m):
            for c in range(n):
                if marked[r][c]:
                    board[r][c] = "."
                    any_marked = True

        if not any_marked:
            return board

        for c in range(n):
            stack = [board[r][c] for r in range(m) if board[r][c] != "."]
            for r in range(m - 1, -1, -1):
                board[r][c] = stack.pop() if stack else "."