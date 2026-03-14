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
                current_symbol = result[i][j] if result[i][j] != '*' else None
                wildcards = []
                cells = []
                
                while j < n and result[i][j] not in ('.', '#'):
                    if result[i][j] == '*':
                        wildcards.append((i, j))
                        cells.append((i, j))
                    else:
                        if current_symbol is None:
                            current_symbol = result[i][j]
                        if result[i][j] == current_symbol:
                            cells.append((i, j))
                        else:
                            break
                    j += 1
                
                if current_symbol is not None and len(cells) >= 3:
                    to_delete.update(cells)
                else:
                    j = start + 1
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if result[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                start = i
                current_symbol = result[i][j] if result[i][j] != '*' else None
                wildcards = []
                cells = []
                
                while i < m and result[i][j] not in ('.', '#'):
                    if result[i][j] == '*':
                        wildcards.append((i, j))
                        cells.append((i, j))
                    else:
                        if current_symbol is None:
                            current_symbol = result[i][j]
                        if result[i][j] == current_symbol:
                            cells.append((i, j))
                        else:
                            break
                    i += 1
                
                if current_symbol is not None and len(cells) >= 3:
                    to_delete.update(cells)
                else:
                    i = start + 1
        
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