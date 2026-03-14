def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    
    result = copy.deepcopy(grid)
    m = len(result)
    n = len(result[0]) if m > 0 else 0
    
    while True:
        to_delete = set()
        
        # Detect horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if result[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                start = j
                base_symbol = None
                run_cells = []
                
                while j < n and result[i][j] != '#':
                    cell = result[i][j]
                    if cell == '.':
                        break
                    
                    run_cells.append((i, j))
                    
                    if cell != '*':
                        if base_symbol is None:
                            base_symbol = cell
                        elif cell != base_symbol:
                            break
                    
                    j += 1
                
                if base_symbol is not None and len(run_cells) >= 3:
                    to_delete.update(run_cells)
                elif j == start:
                    j += 1
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if result[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                start = i
                base_symbol = None
                run_cells = []
                
                while i < m and result[i][j] != '#':
                    cell = result[i][j]
                    if cell == '.':
                        break
                    
                    run_cells.append((i, j))
                    
                    if cell != '*':
                        if base_symbol is None:
                            base_symbol = cell
                        elif cell != base_symbol:
                            break
                    
                    i += 1
                
                if base_symbol is not None and len(run_cells) >= 3:
                    to_delete.update(run_cells)
                elif i == start:
                    i += 1
        
        if not to_delete:
            break
        
        # Delete
        for i, j in to_delete:
            result[i][j] = '.'
        
        # Gravity
        for j in range(n):
            non_empty = []
            for i in range(m):
                if result[i][j] != '.':
                    non_empty.append(result[i][j])
            
            for i in range(m):
                if i < m - len(non_empty):
                    result[i][j] = '.'
                else:
                    result[i][j] = non_empty[i - (m - len(non_empty))]
    
    return result