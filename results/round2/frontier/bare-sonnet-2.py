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
            if is_valid(perm):
                return list(perm)
        return []
    
    # For larger n, use backtracking
    def backtrack(assignment, used, pos):
        if pos == n:
            return is_valid(assignment)
        
        for val in range(1, n + 1):
            if val in used:
                continue
            
            assignment[pos] = val
            used.add(val)
            
            # Check constraints involving position pos
            valid = True
            for constraint_type, i, j in constraints:
                if i == pos and j < pos:
                    if constraint_type == 'lt' and assignment[i] >= assignment[j]:
                        valid = False
                        break
                    elif constraint_type == 'diff' and abs(assignment[i] - assignment[j]) < 2:
                        valid = False
                        break
                    elif constraint_type == 'adj' and abs(assignment[i] - assignment[j]) != 1:
                        valid = False
                        break
                elif j == pos and i < pos:
                    if constraint_type == 'lt' and assignment[i] >= assignment[j]:
                        valid = False
                        break
                    elif constraint_type == 'diff' and abs(assignment[i] - assignment[j]) < 2:
                        valid = False
                        break
                    elif constraint_type == 'adj' and abs(assignment[i] - assignment[j]) != 1:
                        valid = False
                        break
            
            if valid and backtrack(assignment, used, pos + 1):
                return True
            
            used.remove(val)
            assignment[pos] = 0
        
        return False
    
    assignment = [0] * n
    if backtrack(assignment, set(), 0):
        return assignment
    return []