def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    board = [row[:] for row in grid]
    if not board or not board[0]:
        return board

    m, n = len(board), len(board[0])

    def mark_runs() -> set[tuple[int, int]]:
        marked: set[tuple[int, int]] = set()

        def scan_line(cells, coords):
            for target_ord in range(ord('A'), ord('Z') + 1):
                target = chr(target_ord)
                start = 0
                count_letter = 0

                for i, ch in enumerate(cells + ['!']):
                    if ch == target or ch == '*':
                        if i == start:
                            count_letter = 0
                        if ch == target:
                            count_letter += 1
                    else:
                        length = i - start
                        if length >= 3 and count_letter > 0:
                            for k in range(start, i):
                                marked.add(coords[k])
                        start = i + 1
                        count_letter = 0

        for r in range(m):
            scan_line(board[r], [(r, c) for c in range(n)])

        for c in range(n):
            scan_line([board[r][c] for r in range(m)], [(r, c) for r in range(m)])

        return marked

    while True:
        marked = mark_runs()
        if not marked:
            return board

        for r, c in marked:
            if board[r][c] != '#':
                board[r][c] = '.'

        for c in range(n):
            falling = [board[r][c] for r in range(m) if board[r][c] != '.']
            write = m - 1
            for ch in reversed(falling):
                board[write][c] = ch
                write -= 1
            while write >= 0:
                board[write][c] = '.'
                write -= 1