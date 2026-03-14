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
                symbol = result[i][j] if result[i][j] != '*' else None
                has_non_wildcard = result[i][j] != '*'
                
                while j < n and result[i][j] not in ('.', '#'):
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                            has_non_wildcard = True
                        elif result[i][j] != symbol:
                            break
                    j += 1
                
                run_length = j - start
                if run_length >= 3 and has_non_wildcard:
                    for k in range(start, j):
                        to_delete.add((i, k))
                
                if j == start:
                    j += 1
        
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
                    i += 1
                
                run_length = i - start
                if run_length >= 3 and has_non_wildcard:
                    for k in range(start, i):
                        to_delete.add((k, j))
                
                if i == start:
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