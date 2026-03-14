def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    board = [row[:] for row in grid]
    if not board or not board[0]:
        return board

    m, n = len(board), len(board[0])

    while True:
        to_delete = [[False] * n for _ in range(m)]

        for i in range(m):
            letters = {c for c in board[i] if "A" <= c <= "Z"}
            for target in letters:
                j = 0
                while j < n:
                    if board[i][j] == target or board[i][j] == "*":
                        start = j
                        has_target = board[i][j] == target
                        j += 1
                        while j < n and (board[i][j] == target or board[i][j] == "*"):
                            has_target = has_target or board[i][j] == target
                            j += 1
                        if has_target and j - start >= 3:
                            for k in range(start, j):
                                to_delete[i][k] = True
                    else:
                        j += 1

        for j in range(n):
            letters = {board[i][j] for i in range(m) if "A" <= board[i][j] <= "Z"}
            for target in letters:
                i = 0
                while i < m:
                    if board[i][j] == target or board[i][j] == "*":
                        start = i
                        has_target = board[i][j] == target
                        i += 1
                        while i < m and (board[i][j] == target or board[i][j] == "*"):
                            has_target = has_target or board[i][j] == target
                            i += 1
                        if has_target and i - start >= 3:
                            for k in range(start, i):
                                to_delete[k][j] = True
                    else:
                        i += 1

        changed = False
        for i in range(m):
            for j in range(n):
                if to_delete[i][j]:
                    board[i][j] = "."
                    changed = True

        if not changed:
            break

        for j in range(n):
            write = m - 1
            for i in range(m - 1, -1, -1):
                if board[i][j] != ".":
                    board[write][j] = board[i][j]
                    write -= 1
            for i in range(write, -1, -1):
                board[i][j] = "."

    return board