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
                if result[i][j] in ('#', '.'):
                    j += 1
                    continue
                
                start = j
                symbols = set()
                run_cells = []
                
                while j < n and result[i][j] not in ('#', '.'):
                    run_cells.append((i, j))
                    if result[i][j] != '*':
                        symbols.add(result[i][j])
                    j += 1
                
                # Check if valid run
                if len(run_cells) >= 3 and len(symbols) == 1:
                    for cell in run_cells:
                        to_delete.add(cell)
                elif len(run_cells) < 3:
                    pass
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if result[i][j] in ('#', '.'):
                    i += 1
                    continue
                
                start = i
                symbols = set()
                run_cells = []
                
                while i < m and result[i][j] not in ('#', '.'):
                    run_cells.append((i, j))
                    if result[i][j] != '*':
                        symbols.add(result[i][j])
                    i += 1
                
                # Check if valid run
                if len(run_cells) >= 3 and len(symbols) == 1:
                    for cell in run_cells:
                        to_delete.add(cell)
                elif len(run_cells) < 3:
                    pass
        
        if not to_delete:
            break
        
        # Delete cells
        for i, j in to_delete:
            result[i][j] = '.'
        
        # Apply gravity
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