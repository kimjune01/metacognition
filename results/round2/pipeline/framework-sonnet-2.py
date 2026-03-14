def stabilize_board(grid: list[list[str]]) -> list[list[str]]:
    import copy
    result = copy.deepcopy(grid)
    m = len(result)
    n = len(result[0]) if m > 0 else 0
    
    while True:
        to_delete = set()
        
        for r in range(m):
            c = 0
            while c < n:
                if result[r][c] in ('.', '#'):
                    c += 1
                    continue
                
                start = c
                symbol = result[r][c] if result[r][c] != '*' else None
                has_non_wildcard = result[r][c] != '*'
                
                c += 1
                while c < n:
                    cell = result[r][c]
                    if cell == '#' or cell == '.':
                        break
                    if cell == '*':
                        c += 1
                        continue
                    if symbol is None:
                        symbol = cell
                        has_non_wildcard = True
                        c += 1
                    elif cell == symbol:
                        has_non_wildcard = True
                        c += 1
                    else:
                        break
                
                length = c - start
                if length >= 3 and has_non_wildcard and symbol is not None:
                    for col in range(start, c):
                        to_delete.add((r, col))
        
        for c in range(n):
            r = 0
            while r < m:
                if result[r][c] in ('.', '#'):
                    r += 1
                    continue
                
                start = r
                symbol = result[r][c] if result[r][c] != '*' else None
                has_non_wildcard = result[r][c] != '*'
                
                r += 1
                while r < m:
                    cell = result[r][c]
                    if cell == '#' or cell == '.':
                        break
                    if cell == '*':
                        r += 1
                        continue
                    if symbol is None:
                        symbol = cell
                        has_non_wildcard = True
                        r += 1
                    elif cell == symbol:
                        has_non_wildcard = True
                        r += 1
                    else:
                        break
                
                length = r - start
                if length >= 3 and has_non_wildcard and symbol is not None:
                    for row in range(start, r):
                        to_delete.add((row, c))
        
        if not to_delete:
            break
        
        for r, c in to_delete:
            result[r][c] = '.'
        
        for c in range(n):
            non_empty = []
            for r in range(m):
                if result[r][c] != '.':
                    non_empty.append(result[r][c])
            
            for r in range(m):
                result[r][c] = '.'
            
            write_pos = m - 1
            for i in range(len(non_empty) - 1, -1, -1):
                result[write_pos][c] = non_empty[i]
                write_pos -= 1
    
    return result