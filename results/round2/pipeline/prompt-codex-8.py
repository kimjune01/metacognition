def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    board = [row[:] for row in grid]
    if not board or not board[0]:
        return board

    m, n = len(board), len(board[0])

    def mark_runs() -> set[tuple[int, int]]:
        marked: set[tuple[int, int]] = set()

        def process_line(cells: list[str], coords: list[tuple[int, int]]) -> None:
            length = len(cells)
            for code in range(ord('A'), ord('Z') + 1):
                ch = chr(code)
                i = 0
                while i < length:
                    if cells[i] != ch and cells[i] != '*':
                        i += 1
                        continue
                    j = i
                    seen_letter = False
                    while j < length and (cells[j] == ch or cells[j] == '*'):
                        if cells[j] == ch:
                            seen_letter = True
                        j += 1
                    if seen_letter and j - i >= 3:
                        for k in range(i, j):
                            marked.add(coords[k])
                    i = j

        for r in range(m):
            cells = board[r]
            start = 0
            while start < n:
                while start < n and (cells[start] == '#' or cells[start] == '.'):
                    start += 1
                end = start
                while end < n and cells[end] != '#' and cells[end] != '.':
                    end += 1
                if end > start:
                    process_line(cells[start:end], [(r, c) for c in range(start, end)])
                start = end

        for c in range(n):
            col = [board[r][c] for r in range(m)]
            start = 0
            while start < m:
                while start < m and (col[start] == '#' or col[start] == '.'):
                    start += 1
                end = start
                while end < m and col[end] != '#' and col[end] != '.':
                    end += 1
                if end > start:
                    process_line(col[start:end], [(r, c) for r in range(start, end)])
                start = end

        return marked

    while True:
        to_delete = mark_runs()
        if not to_delete:
            return board

        for r, c in to_delete:
            board[r][c] = '.'

        for c in range(n):
            items = [board[r][c] for r in range(m) if board[r][c] != '.']
            write = m - 1
            for r in range(m - 1, -1, -1):
                if items:
                    board[write][c] = items.pop()
                    write -= 1
                else:
                    break
            for r in range(write, -1, -1):
                board[r][c] = '.'