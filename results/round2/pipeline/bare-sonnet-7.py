def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    grid = copy.deepcopy(grid)
    
    while True:
        to_delete = set()
        m = len(grid)
        n = len(grid[0]) if m > 0 else 0
        
        # Detect horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if grid[i][j] in ('#', '.'):
                    j += 1
                    continue
                
                start = j
                symbol = grid[i][j] if grid[i][j] != '*' else None
                
                while j < n and grid[i][j] not in ('#', '.'):
                    if grid[i][j] != '*':
                        if symbol is None:
                            symbol = grid[i][j]
                        elif symbol != grid[i][j]:
                            break
                    j += 1
                
                length = j - start
                has_non_wildcard = symbol is not None
                
                if length >= 3 and has_non_wildcard:
                    for k in range(start, j):
                        to_delete.add((i, k))
                
                if j == start:
                    j += 1
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if grid[i][j] in ('#', '.'):
                    i += 1
                    continue
                
                start = i
                symbol = grid[i][j] if grid[i][j] != '*' else None
                
                while i < m and grid[i][j] not in ('#', '.'):
                    if grid[i][j] != '*':
                        if symbol is None:
                            symbol = grid[i][j]
                        elif symbol != grid[i][j]:
                            break
                    i += 1
                
                length = i - start
                has_non_wildcard = symbol is not None
                
                if length >= 3 and has_non_wildcard:
                    for k in range(start, i):
                        to_delete.add((k, j))
                
                if i == start:
                    i += 1
        
        if not to_delete:
            break
        
        # Delete cells
        for i, j in to_delete:
            grid[i][j] = '.'
        
        # Apply gravity
        for j in range(n):
            non_empty = []
            for i in range(m):
                if grid[i][j] != '.':
                    non_empty.append(grid[i][j])
            
            for i in range(m):
                if i < m - len(non_empty):
                    grid[i][j] = '.'
                else:
                    grid[i][j] = non_empty[i - (m - len(non_empty))]
    
    return grid