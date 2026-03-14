def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    if not grid or not grid[0]:
        return [row[:] for row in grid]

    board = [row[:] for row in grid]
    m, n = len(board), len(board[0])

    def mark_runs() -> set[tuple[int, int]]:
        marked = set()

        for r in range(m):
            for ch_ord in range(26):
                ch = chr(ord('A') + ch_ord)
                c = 0
                while c < n:
                    while c < n and board[r][c] == '#':
                        c += 1
                    start = c
                    has_letter = False
                    while c < n and board[r][c] != '#' and board[r][c] in (ch, '*'):
                        if board[r][c] == ch:
                            has_letter = True
                        c += 1
                    if has_letter and c - start >= 3:
                        for j in range(start, c):
                            marked.add((r, j))
                    if start == c:
                        c += 1

        for c in range(n):
            for ch_ord in range(26):
                ch = chr(ord('A') + ch_ord)
                r = 0
                while r < m:
                    while r < m and board[r][c] == '#':
                        r += 1
                    start = r
                    has_letter = False
                    while r < m and board[r][c] != '#' and board[r][c] in (ch, '*'):
                        if board[r][c] == ch:
                            has_letter = True
                        r += 1
                    if has_letter and r - start >= 3:
                        for i in range(start, r):
                            marked.add((i, c))
                    if start == r:
                        r += 1

        return marked

    while True:
        to_delete = mark_runs()
        if not to_delete:
            break

        for r, c in to_delete:
            if board[r][c] != '#':
                board[r][c] = '.'

        for c in range(n):
            write = m - 1
            for r in range(m - 1, -1, -1):
                if board[r][c] != '.':
                    board[write][c] = board[r][c]
                    write -= 1
            while write >= 0:
                board[write][c] = '.'
                write -= 1

    return board