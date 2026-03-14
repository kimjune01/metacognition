def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    result = copy.deepcopy(grid)
    
    while True:
        to_delete = set()
        m = len(result)
        n = len(result[0]) if m > 0 else 0
        
        # Detect horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if result[i][j] in ('#', '.'):
                    j += 1
                    continue
                
                # Start of potential run
                start = j
                cells = [(i, j)]
                symbol = result[i][j] if result[i][j] != '*' else None
                
                j += 1
                while j < n and result[i][j] != '#' and result[i][j] != '.':
                    cells.append((i, j))
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                        elif symbol != result[i][j]:
                            break
                    j += 1
                else:
                    # Check if we have a valid run
                    if len(cells) >= 3 and symbol is not None:
                        to_delete.update(cells)
                    continue
                
                # Didn't complete the run, reset
                j = start + 1
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if result[i][j] in ('#', '.'):
                    i += 1
                    continue
                
                # Start of potential run
                start = i
                cells = [(i, j)]
                symbol = result[i][j] if result[i][j] != '*' else None
                
                i += 1
                while i < m and result[i][j] != '#' and result[i][j] != '.':
                    cells.append((i, j))
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                        elif symbol != result[i][j]:
                            break
                    i += 1
                else:
                    # Check if we have a valid run
                    if len(cells) >= 3 and symbol is not None:
                        to_delete.update(cells)
                    continue
                
                # Didn't complete the run, reset
                i = start + 1
        
        # If no runs detected, we're stable
        if not to_delete:
            break
        
        # Delete marked cells
        for i, j in to_delete:
            result[i][j] = '.'
        
        # Apply gravity
        for j in range(n):
            # Collect non-empty cells from bottom to top
            non_empty = []
            for i in range(m - 1, -1, -1):
                if result[i][j] != '.':
                    non_empty.append(result[i][j])
            
            # Fill column from bottom
            for i in range(m - 1, -1, -1):
                if non_empty:
                    result[i][j] = non_empty.pop(0)
                else:
                    result[i][j] = '.'
    
    return result