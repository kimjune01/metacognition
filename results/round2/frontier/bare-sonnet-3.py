def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from itertools import permutations
    
    def is_valid(assignment):
        for ctype, i, j in constraints:
            if ctype == 'lt':
                if assignment[i] >= assignment[j]:
                    return False
            elif ctype == 'diff':
                if abs(assignment[i] - assignment[j]) < 2:
                    return False
            elif ctype == 'adj':
                if abs(assignment[i] - assignment[j]) != 1:
                    return False
        return True
    
    # For small n, try all permutations
    if n <= 8:
        for perm in permutations(range(1, n + 1)):
            if is_valid(perm):
                return list(perm)
        return []
    
    # For larger n, use backtracking with constraint propagation
    def backtrack(assignment, remaining):
        if not remaining:
            if is_valid(assignment):
                return assignment[:]
            return None
        
        slot = len(assignment)
        for value in sorted(remaining):
            assignment.append(value)
            new_remaining = remaining - {value}
            
            # Check constraints involving this slot
            valid = True
            for ctype, i, j in constraints:
                if j == slot and i < slot:
                    if ctype == 'lt' and assignment[i] >= assignment[j]:
                        valid = False
                        break
                    elif ctype == 'diff' and abs(assignment[i] - assignment[j]) < 2:
                        valid = False
                        break
                    elif ctype == 'adj' and abs(assignment[i] - assignment[j]) != 1:
                        valid = False
                        break
                elif i == slot and j < slot:
                    if ctype == 'lt' and assignment[i] >= assignment[j]:
                        valid = False
                        break
                    elif ctype == 'diff' and abs(assignment[i] - assignment[j]) < 2:
                        valid = False
                        break
                    elif ctype == 'adj' and abs(assignment[i] - assignment[j]) != 1:
                        valid = False
                        break
            
            if valid:
                result = backtrack(assignment, new_remaining)
                if result is not None:
                    return result
            
            assignment.pop()
        
        return None
    
    result = backtrack([], set(range(1, n + 1)))
    return result if result is not None else []