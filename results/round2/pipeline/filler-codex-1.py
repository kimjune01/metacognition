def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    rows, cols = len(grid), len(grid[0])
    board = [row[:] for row in grid]
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def mark_runs() -> set[tuple[int, int]]:
        marked = set()

        def scan_line(coords):
            line = [board[r][c] for r, c in coords]
            n = len(line)
            for target in letters:
                i = 0
                while i < n:
                    if line[i] == "#" or (line[i] != "*" and line[i] != target):
                        i += 1
                        continue
                    j = i
                    has_target = False
                    while j < n and line[j] != "#" and (line[j] == "*" or line[j] == target):
                        if line[j] == target:
                            has_target = True
                        j += 1
                    if j - i >= 3 and has_target:
                        for k in range(i, j):
                            marked.add(coords[k])
                    i = j

        for r in range(rows):
            scan_line([(r, c) for c in range(cols)])
        for c in range(cols):
            scan_line([(r, c) for r in range(rows)])

        return marked

    while True:
        to_delete = mark_runs()
        if not to_delete:
            break

        for r, c in to_delete:
            board[r][c] = "."

        for c in range(cols):
            non_empty = [board[r][c] for r in range(rows) if board[r][c] != "."]
            write = rows - 1
            for i in range(len(non_empty) - 1, -1, -1):
                board[write][c] = non_empty[i]
                write -= 1
            while write >= 0:
                board[write][c] = "."
                write -= 1

    return board