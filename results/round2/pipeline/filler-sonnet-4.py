def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    grid = copy.deepcopy(grid)
    
    while True:
        # Step 1: Detect all runs
        to_delete = set()
        m, n = len(grid), len(grid[0]) if grid else 0
        
        # Check horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if grid[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                # Start of potential run
                start = j
                base_symbol = None
                has_non_wildcard = False
                
                # Collect run
                while j < n and grid[i][j] not in ('.', '#'):
                    if grid[i][j] == '*':
                        j += 1
                        continue
                    
                    if base_symbol is None:
                        base_symbol = grid[i][j]
                        has_non_wildcard = True
                    elif grid[i][j] == base_symbol:
                        has_non_wildcard = True
                    else:
                        # Different symbol, break run
                        break
                    j += 1
                
                # Check if valid run (length >= 3 and has non-wildcard)
                if j - start >= 3 and has_non_wildcard:
                    for k in range(start, j):
                        to_delete.add((i, k))
                else:
                    # Not a valid run, move to next position
                    if j == start:
                        j += 1
        
        # Check vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if grid[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                # Start of potential run
                start = i
                base_symbol = None
                has_non_wildcard = False
                
                # Collect run
                while i < m and grid[i][j] not in ('.', '#'):
                    if grid[i][j] == '*':
                        i += 1
                        continue
                    
                    if base_symbol is None:
                        base_symbol = grid[i][j]
                        has_non_wildcard = True
                    elif grid[i][j] == base_symbol:
                        has_non_wildcard = True
                    else:
                        # Different symbol, break run
                        break
                    i += 1
                
                # Check if valid run (length >= 3 and has non-wildcard)
                if i - start >= 3 and has_non_wildcard:
                    for k in range(start, i):
                        to_delete.add((k, j))
                else:
                    # Not a valid run, move to next position
                    if i == start:
                        i += 1
        
        # If no runs detected, we're stable
        if not to_delete:
            break
        
        # Step 2: Delete all cells in runs
        for i, j in to_delete:
            grid[i][j] = '.'
        
        # Step 3: Apply gravity
        for j in range(n):
            # Collect non-empty cells in column
            non_empty = []
            for i in range(m):
                if grid[i][j] != '.':
                    non_empty.append(grid[i][j])
            
            # Fill column: empty at top, non-empty at bottom
            for i in range(m):
                if i < m - len(non_empty):
                    grid[i][j] = '.'
                else:
                    grid[i][j] = non_empty[i - (m - len(non_empty))]
    
    return grid