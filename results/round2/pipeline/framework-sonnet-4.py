def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    result = copy.deepcopy(grid)
    m = len(result)
    n = len(result[0]) if m > 0 else 0
    
    while True:
        to_delete = [[False] * n for _ in range(m)]
        
        # Detect horizontal runs
        for i in range(m):
            j = 0
            while j < n:
                if result[i][j] == '#' or result[i][j] == '.':
                    j += 1
                    continue
                
                start = j
                symbol = result[i][j] if result[i][j] != '*' else None
                has_non_wildcard = result[i][j] != '*'
                
                while j < n and result[i][j] != '#' and result[i][j] != '.':
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
                        to_delete[i][k] = True
                
                if j == start:
                    j += 1
        
        # Detect vertical runs
        for j in range(n):
            i = 0
            while i < m:
                if result[i][j] == '#' or result[i][j] == '.':
                    i += 1
                    continue
                
                start = i
                symbol = result[i][j] if result[i][j] != '*' else None
                has_non_wildcard = result[i][j] != '*'
                
                while i < m and result[i][j] != '#' and result[i][j] != '.':
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
                        to_delete[k][j] = True
                
                if i == start:
                    i += 1
        
        # Check if any deletions
        has_deletions = any(any(row) for row in to_delete)
        if not has_deletions:
            break
        
        # Delete
        for i in range(m):
            for j in range(n):
                if to_delete[i][j]:
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