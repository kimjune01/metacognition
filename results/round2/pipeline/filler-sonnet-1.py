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
                symbol = result[i][j] if result[i][j] != '*' else None
                has_non_wildcard = result[i][j] != '*'
                
                while j < n and result[i][j] not in ('.', '#'):
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                            has_non_wildcard = True
                        elif result[i][j] != symbol:
                            break
                        else:
                            has_non_wildcard = True
                    j += 1
                
                length = j - start
                if length >= 3 and has_non_wildcard and symbol is not None:
                    for k in range(start, j):
                        to_delete.add((i, k))
                elif j < n and result[i][j] not in ('.', '#'):
                    j = start + 1
                    continue
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if result[i][j] in ('.', '#'):
                    i += 1
                    continue
                
                start = i
                symbol = result[i][j] if result[i][j] != '*' else None
                has_non_wildcard = result[i][j] != '*'
                
                while i < m and result[i][j] not in ('.', '#'):
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                            has_non_wildcard = True
                        elif result[i][j] != symbol:
                            break
                        else:
                            has_non_wildcard = True
                    i += 1
                
                length = i - start
                if length >= 3 and has_non_wildcard and symbol is not None:
                    for k in range(start, i):
                        to_delete.add((k, j))
                elif i < m and result[i][j] not in ('.', '#'):
                    i = start + 1
                    continue
        
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