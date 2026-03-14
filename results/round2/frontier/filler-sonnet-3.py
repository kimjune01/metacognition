def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from itertools import permutations
    
    def is_valid(assignment):
        for constraint_type, i, j in constraints:
            if constraint_type == 'lt':
                if assignment[i] >= assignment[j]:
                    return False
            elif constraint_type == 'diff':
                if abs(assignment[i] - assignment[j]) < 2:
                    return False
            elif constraint_type == 'adj':
                if abs(assignment[i] - assignment[j]) != 1:
                    return False
        return True
    
    # For small n, try all permutations
    if n <= 8:
        for perm in permutations(range(1, n + 1)):
            if is_valid(list(perm)):
                return list(perm)
        return []
    
    # For larger n, use backtracking
    assignment = [0] * n
    used = [False] * (n + 1)
    
    def backtrack(pos):
        if pos == n:
            return True
        
        for value in range(1, n + 1):
            if used[value]:
                continue
            
            assignment[pos] = value
            used[value] = True
            
            # Check constraints involving this position
            valid = True
            for constraint_type, i, j in constraints:
                if i == pos and assignment[j] != 0:
                    if constraint_type == 'lt' and assignment[i] >= assignment[j]:
                        valid = False
                        break
                    elif constraint_type == 'diff' and abs(assignment[i] - assignment[j]) < 2:
                        valid = False
                        break
                    elif constraint_type == 'adj' and abs(assignment[i] - assignment[j]) != 1:
                        valid = False
                        break
                elif j == pos and assignment[i] != 0:
                    if constraint_type == 'lt' and assignment[i] >= assignment[j]:
                        valid = False
                        break
                    elif constraint_type == 'diff' and abs(assignment[i] - assignment[j]) < 2:
                        valid = False
                        break
                    elif constraint_type == 'adj' and abs(assignment[i] - assignment[j]) != 1:
                        valid = False
                        break
            
            if valid and backtrack(pos + 1):
                return True
            
            assignment[pos] = 0
            used[value] = False
        
        return False
    
    if backtrack(0):
        return assignment
    return []