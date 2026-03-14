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
                if grid[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                # Start a potential run
                start = j
                run_cells = [(i, j)]
                current_symbol = grid[i][j] if grid[i][j] != '*' else None
                
                j += 1
                while j < n:
                    cell = grid[i][j]
                    if cell == '#' or cell == '.':
                        break
                    if cell == '*':
                        run_cells.append((i, j))
                        j += 1
                    elif current_symbol is None:
                        current_symbol = cell
                        run_cells.append((i, j))
                        j += 1
                    elif cell == current_symbol:
                        run_cells.append((i, j))
                        j += 1
                    else:
                        break
                
                if current_symbol is not None and len(run_cells) >= 3:
                    to_delete.update(run_cells)
                
                if j == start + 1:
                    j = start + 1
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if grid[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                # Start a potential run
                start = i
                run_cells = [(i, j)]
                current_symbol = grid[i][j] if grid[i][j] != '*' else None
                
                i += 1
                while i < m:
                    cell = grid[i][j]
                    if cell == '#' or cell == '.':
                        break
                    if cell == '*':
                        run_cells.append((i, j))
                        i += 1
                    elif current_symbol is None:
                        current_symbol = cell
                        run_cells.append((i, j))
                        i += 1
                    elif cell == current_symbol:
                        run_cells.append((i, j))
                        i += 1
                    else:
                        break
                
                if current_symbol is not None and len(run_cells) >= 3:
                    to_delete.update(run_cells)
                
                if i == start + 1:
                    i = start + 1
        
        # If no runs detected, we're stable
        if not to_delete:
            break
        
        # Delete marked cells
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