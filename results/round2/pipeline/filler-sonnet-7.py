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
                run_cells = [(i, j)]
                has_non_wildcard = grid[i][j] != '*'
                symbol = grid[i][j] if grid[i][j] != '*' else None
                
                j += 1
                while j < n:
                    current = grid[i][j]
                    if current == '#' or current == '.':
                        break
                    if current == '*':
                        run_cells.append((i, j))
                        j += 1
                    elif symbol is None:
                        # First non-wildcard symbol
                        symbol = current
                        has_non_wildcard = True
                        run_cells.append((i, j))
                        j += 1
                    elif current == symbol:
                        run_cells.append((i, j))
                        j += 1
                    else:
                        break
                
                if len(run_cells) >= 3 and has_non_wildcard:
                    to_delete.update(run_cells)
                else:
                    j = start + 1
        
        # Check vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if grid[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                # Start of potential run
                start = i
                run_cells = [(i, j)]
                has_non_wildcard = grid[i][j] != '*'
                symbol = grid[i][j] if grid[i][j] != '*' else None
                
                i += 1
                while i < m:
                    current = grid[i][j]
                    if current == '#' or current == '.':
                        break
                    if current == '*':
                        run_cells.append((i, j))
                        i += 1
                    elif symbol is None:
                        # First non-wildcard symbol
                        symbol = current
                        has_non_wildcard = True
                        run_cells.append((i, j))
                        i += 1
                    elif current == symbol:
                        run_cells.append((i, j))
                        i += 1
                    else:
                        break
                
                if len(run_cells) >= 3 and has_non_wildcard:
                    to_delete.update(run_cells)
                else:
                    i = start + 1
        
        # Step 2: Delete
        if not to_delete:
            break
        
        for i, j in to_delete:
            grid[i][j] = '.'
        
        # Step 3: Gravity
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