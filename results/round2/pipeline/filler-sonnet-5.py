def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    
    grid = copy.deepcopy(grid)
    m = len(grid)
    n = len(grid[0]) if m > 0 else 0
    
    while True:
        to_delete = set()
        
        # Detect horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if grid[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                start = j
                base_symbol = grid[i][j] if grid[i][j] != '*' else None
                has_non_wildcard = grid[i][j] != '*'
                
                j += 1
                while j < n:
                    current = grid[i][j]
                    if current == '#' or current == '.':
                        break
                    if current == '*':
                        j += 1
                        continue
                    if base_symbol is None:
                        base_symbol = current
                        has_non_wildcard = True
                        j += 1
                    elif current == base_symbol:
                        has_non_wildcard = True
                        j += 1
                    else:
                        break
                
                length = j - start
                if length >= 3 and has_non_wildcard:
                    for k in range(start, j):
                        to_delete.add((i, k))
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if grid[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                start = i
                base_symbol = grid[i][j] if grid[i][j] != '*' else None
                has_non_wildcard = grid[i][j] != '*'
                
                i += 1
                while i < m:
                    current = grid[i][j]
                    if current == '#' or current == '.':
                        break
                    if current == '*':
                        i += 1
                        continue
                    if base_symbol is None:
                        base_symbol = current
                        has_non_wildcard = True
                        i += 1
                    elif current == base_symbol:
                        has_non_wildcard = True
                        i += 1
                    else:
                        break
                
                length = i - start
                if length >= 3 and has_non_wildcard:
                    for k in range(start, i):
                        to_delete.add((k, j))
        
        if not to_delete:
            break
        
        # Delete
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