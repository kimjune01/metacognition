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
                
                # Extend run
                while j < n and result[i][j] not in ('.', '#'):
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                        elif symbol != result[i][j]:
                            break
                    j += 1
                
                length = j - start
                # Check if valid run
                if length >= 3 and symbol is not None:
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
                
                # Extend run
                while i < m and result[i][j] not in ('.', '#'):
                    if result[i][j] != '*':
                        if symbol is None:
                            symbol = result[i][j]
                        elif symbol != result[i][j]:
                            break
                    i += 1
                
                length = i - start
                # Check if valid run
                if length >= 3 and symbol is not None:
                    for k in range(start, i):
                        to_delete.add((k, j))
                
                if i == start:
                    i += 1
        
        # If no matches, we're stable
        if not to_delete:
            break
        
        # Delete matched cells
        for i, j in to_delete:
            result[i][j] = '.'
        
        # Apply gravity
        for j in range(n):
            non_empty = []
            for i in range(m):
                if result[i][j] != '.':
                    non_empty.append(result[i][j])
            
            # Fill column from bottom
            for i in range(m):
                if i < m - len(non_empty):
                    result[i][j] = '.'
                else:
                    result[i][j] = non_empty[i - (m - len(non_empty))]
    
    return result