def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    grid = copy.deepcopy(grid)
    
    while True:
        # Step 1: Detect all runs
        to_delete = set()
        m = len(grid)
        n = len(grid[0]) if m > 0 else 0
        
        # Check horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if grid[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                # Start of potential run
                start = j
                cells = [(i, j)]
                symbol = grid[i][j] if grid[i][j] != '*' else None
                
                j += 1
                while j < n and grid[i][j] != '.' and grid[i][j] != '#':
                    cells.append((i, j))
                    if grid[i][j] != '*':
                        if symbol is None:
                            symbol = grid[i][j]
                        elif symbol != grid[i][j]:
                            break
                    j += 1
                
                # Check if valid run (3+ cells, at least one non-wildcard)
                if len(cells) >= 3 and symbol is not None:
                    # Verify all non-wildcards match
                    valid = True
                    for ci, cj in cells:
                        if grid[ci][cj] != '*' and grid[ci][cj] != symbol:
                            valid = False
                            break
                    if valid:
                        to_delete.update(cells)
                
                if j == start + 1:
                    continue
        
        # Check vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if grid[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                # Start of potential run
                start = i
                cells = [(i, j)]
                symbol = grid[i][j] if grid[i][j] != '*' else None
                
                i += 1
                while i < m and grid[i][j] != '.' and grid[i][j] != '#':
                    cells.append((i, j))
                    if grid[i][j] != '*':
                        if symbol is None:
                            symbol = grid[i][j]
                        elif symbol != grid[i][j]:
                            break
                    i += 1
                
                # Check if valid run (3+ cells, at least one non-wildcard)
                if len(cells) >= 3 and symbol is not None:
                    # Verify all non-wildcards match
                    valid = True
                    for ci, cj in cells:
                        if grid[ci][cj] != '*' and grid[ci][cj] != symbol:
                            valid = False
                            break
                    if valid:
                        to_delete.update(cells)
                
                if i == start + 1:
                    continue
        
        # If no runs detected, we're stable
        if not to_delete:
            break
        
        # Step 2: Delete runs
        for i, j in to_delete:
            grid[i][j] = '.'
        
        # Step 3: Apply gravity
        for j in range(n):
            # Collect non-empty cells from bottom to top
            non_empty = []
            for i in range(m - 1, -1, -1):
                if grid[i][j] != '.':
                    non_empty.append(grid[i][j])
            
            # Fill column from bottom
            for i in range(m - 1, -1, -1):
                if non_empty:
                    grid[i][j] = non_empty.pop(0)
                else:
                    grid[i][j] = '.'
    
    return grid