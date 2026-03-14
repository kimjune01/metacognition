def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    board = [row[:] for row in grid]
    m, n = len(board), len(board[0])

    def mark_runs() -> set[tuple[int, int]]:
        marked: set[tuple[int, int]] = set()

        def scan_line(coords):
            values = [board[r][c] for r, c in coords]
            for letter in map(chr, range(ord('A'), ord('Z') + 1)):
                start = 0
                while start < len(values):
                    if values[start] not in (letter, '*'):
                        start += 1
                        continue
                    end = start
                    has_letter = False
                    while end < len(values) and values[end] in (letter, '*'):
                        if values[end] == letter:
                            has_letter = True
                        end += 1
                    if has_letter and end - start >= 3:
                        for i in range(start, end):
                            marked.add(coords[i])
                    start = end

        for r in range(m):
            scan_line([(r, c) for c in range(n)])
        for c in range(n):
            scan_line([(r, c) for r in range(m)])

        return marked

    while True:
        to_delete = mark_runs()
        if not to_delete:
            return board

        for r, c in to_delete:
            board[r][c] = '.'

        for c in range(n):
            falling = [board[r][c] for r in range(m) if board[r][c] != '.']
            write = m - 1
            for i in range(len(falling) - 1, -1, -1):
                board[write][c] = falling[i]
                write -= 1
            while write >= 0:
                board[write][c] = '.'
                write -= 1