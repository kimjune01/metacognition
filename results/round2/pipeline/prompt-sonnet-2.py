def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    
    # Create a deep copy to avoid modifying the input
    board = copy.deepcopy(grid)
    
    while True:
        # Step 1: Detect all runs
        to_delete = set()
        m = len(board)
        n = len(board[0]) if m > 0 else 0
        
        # Check horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if board[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                # Start of a potential run
                start = j
                cells = [(i, j)]
                symbol = board[i][j] if board[i][j] != '*' else None
                
                j += 1
                while j < n and board[i][j] not in ('.', '#'):
                    cells.append((i, j))
                    if board[i][j] != '*':
                        if symbol is None:
                            symbol = board[i][j]
                        elif symbol != board[i][j]:
                            break
                    j += 1
                else:
                    # Successfully extended the run to the end or a blocker/empty
                    if len(cells) >= 3 and symbol is not None:
                        to_delete.update(cells)
                    continue
                
                # Broke due to symbol mismatch
                if len(cells) >= 3 and symbol is not None:
                    to_delete.update(cells)
                j = start + 1
        
        # Check vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if board[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                # Start of a potential run
                start = i
                cells = [(i, j)]
                symbol = board[i][j] if board[i][j] != '*' else None
                
                i += 1
                while i < m and board[i][j] not in ('.', '#'):
                    cells.append((i, j))
                    if board[i][j] != '*':
                        if symbol is None:
                            symbol = board[i][j]
                        elif symbol != board[i][j]:
                            break
                    i += 1
                else:
                    # Successfully extended the run to the end or a blocker/empty
                    if len(cells) >= 3 and symbol is not None:
                        to_delete.update(cells)
                    continue
                
                # Broke due to symbol mismatch
                if len(cells) >= 3 and symbol is not None:
                    to_delete.update(cells)
                i = start + 1
        
        # If no runs detected, we're stable
        if not to_delete:
            break
        
        # Step 2: Delete marked cells
        for i, j in to_delete:
            board[i][j] = '.'
        
        # Step 3: Apply gravity
        for j in range(n):
            # Collect non-empty cells from bottom to top
            non_empty = []
            for i in range(m - 1, -1, -1):
                if board[i][j] != '.':
                    non_empty.append(board[i][j])
            
            # Fill column from bottom
            for i in range(m - 1, -1, -1):
                if non_empty:
                    board[i][j] = non_empty.pop(0)
                else:
                    board[i][j] = '.'
    
    return board