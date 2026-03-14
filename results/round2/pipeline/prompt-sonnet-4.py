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
                
                start = j
                cells = [(i, j)]
                symbol = result[i][j] if result[i][j] != '*' else None
                
                j += 1
                while j < n and result[i][j] != '.' and result[i][j] != '#':
                    cells.append((i, j))
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                        elif symbol != result[i][j]:
                            break
                    j += 1
                
                if len(cells) >= 3 and symbol is not None:
                    valid = True
                    for r, c in cells:
                        if result[r][c] != '*' and result[r][c] != symbol:
                            valid = False
                            break
                    if valid:
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
                cells = [(i, j)]
                symbol = result[i][j] if result[i][j] != '*' else None
                
                i += 1
                while i < m and result[i][j] != '.' and result[i][j] != '#':
                    cells.append((i, j))
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                        elif symbol != result[i][j]:
                            break
                    i += 1
                
                if len(cells) >= 3 and symbol is not None:
                    valid = True
                    for r, c in cells:
                        if result[r][c] != '*' and result[r][c] != symbol:
                            valid = False
                            break
                    if valid:
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