def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    result = copy.deepcopy(grid)
    
    while True:
        to_delete = set()
        m = len(result)
        n = len(result[0]) if m > 0 else 0
        
        # Detect horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if result[i][j] in ('.', '#'):
                    j += 1
                    continue
                
                # Start of potential run
                start = j
                symbol = None
                run_cells = []
                
                while j < n and result[i][j] not in ('.', '#'):
                    cell = result[i][j]
                    run_cells.append((i, j))
                    if cell != '*':
                        if symbol is None:
                            symbol = cell
                        elif cell != symbol:
                            break
                    j += 1
                else:
                    # Check if this is a valid run
                    if symbol is not None and len(run_cells) >= 3:
                        for cell in run_cells:
                            to_delete.add(cell)
                    j = start + 1
                    continue
                
                # Mismatch found
                if symbol is not None and len(run_cells) >= 3:
                    for cell in run_cells:
                        to_delete.add(cell)
                j = start + 1
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if result[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                # Start of potential run
                start = i
                symbol = None
                run_cells = []
                
                while i < m and result[i][j] not in ('.', '#'):
                    cell = result[i][j]
                    run_cells.append((i, j))
                    if cell != '*':
                        if symbol is None:
                            symbol = cell
                        elif cell != symbol:
                            break
                    i += 1
                else:
                    # Check if this is a valid run
                    if symbol is not None and len(run_cells) >= 3:
                        for cell in run_cells:
                            to_delete.add(cell)
                    i = start + 1
                    continue
                
                # Mismatch found
                if symbol is not None and len(run_cells) >= 3:
                    for cell in run_cells:
                        to_delete.add(cell)
                i = start + 1
        
        # If no runs detected, we're stable
        if not to_delete:
            break
        
        # Delete marked cells
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