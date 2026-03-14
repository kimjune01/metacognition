def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    result = copy.deepcopy(grid)
    
    while True:
        m = len(result)
        n = len(result[0]) if m > 0 else 0
        
        to_delete = set()
        
        # Detect horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if result[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                # Start of potential run
                start = j
                cells = [(i, j)]
                
                # Collect contiguous cells
                j += 1
                while j < n and result[i][j] != '.' and result[i][j] != '#':
                    cells.append((i, j))
                    j += 1
                
                # Check if this is a valid run
                if len(cells) >= 3:
                    # Find non-wildcard symbols
                    symbols = set()
                    for r, c in cells:
                        if result[r][c] != '*':
                            symbols.add(result[r][c])
                    
                    # Valid if there's at least one non-wildcard and all non-wildcards are the same
                    if len(symbols) == 1:
                        to_delete.update(cells)
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if result[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                # Start of potential run
                start = i
                cells = [(i, j)]
                
                # Collect contiguous cells
                i += 1
                while i < m and result[i][j] != '.' and result[i][j] != '#':
                    cells.append((i, j))
                    i += 1
                
                # Check if this is a valid run
                if len(cells) >= 3:
                    # Find non-wildcard symbols
                    symbols = set()
                    for r, c in cells:
                        if result[r][c] != '*':
                            symbols.add(result[r][c])
                    
                    # Valid if there's at least one non-wildcard and all non-wildcards are the same
                    if len(symbols) == 1:
                        to_delete.update(cells)
        
        # If no runs detected, we're stable
        if not to_delete:
            break
        
        # Delete cells
        for r, c in to_delete:
            result[r][c] = '.'
        
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