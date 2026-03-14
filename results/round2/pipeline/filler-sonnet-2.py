def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    grid = copy.deepcopy(grid)
    
    while True:
        m = len(grid)
        n = len(grid[0]) if m > 0 else 0
        
        # Step 1: Detect all runs
        to_delete = set()
        
        # Check horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if grid[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                # Start of potential run
                start = j
                symbol = grid[i][j] if grid[i][j] != '*' else None
                run_cells = []
                
                while j < n and grid[i][j] != '.' and grid[i][j] != '#':
                    run_cells.append((i, j))
                    if grid[i][j] != '*':
                        if symbol is None:
                            symbol = grid[i][j]
                        elif symbol != grid[i][j]:
                            # Mixed symbols, not a valid run
                            break
                    j += 1
                else:
                    # Successfully scanned a potential run
                    if len(run_cells) >= 3 and symbol is not None:
                        to_delete.update(run_cells)
                    continue
                
                # If we broke, advance j past the problematic cell
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
                symbol = grid[i][j] if grid[i][j] != '*' else None
                run_cells = []
                
                while i < m and grid[i][j] != '.' and grid[i][j] != '#':
                    run_cells.append((i, j))
                    if grid[i][j] != '*':
                        if symbol is None:
                            symbol = grid[i][j]
                        elif symbol != grid[i][j]:
                            # Mixed symbols, not a valid run
                            break
                    i += 1
                else:
                    # Successfully scanned a potential run
                    if len(run_cells) >= 3 and symbol is not None:
                        to_delete.update(run_cells)
                    continue
                
                # If we broke, advance i past the problematic cell
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