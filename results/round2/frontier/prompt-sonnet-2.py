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
    
    # For larger n, use backtracking
    def backtrack(assignment, used):
        if len(assignment) == n:
            return assignment[:]
        
        slot = len(assignment)
        
        for value in range(1, n + 1):
            if value in used:
                continue
            
            assignment.append(value)
            used.add(value)
            
            # Check constraints involving this slot
            valid = True
            for ctype, i, j in constraints:
                if i == slot:
                    if j < len(assignment):
                        if ctype == 'lt' and assignment[i] >= assignment[j]:
                            valid = False
                            break
                        elif ctype == 'diff' and abs(assignment[i] - assignment[j]) < 2:
                            valid = False
                            break
                        elif ctype == 'adj' and abs(assignment[i] - assignment[j]) != 1:
                            valid = False
                            break
                elif j == slot:
                    if i < len(assignment):
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
                result = backtrack(assignment, used)
                if result:
                    return result
            
            assignment.pop()
            used.remove(value)
        
        return None
    
    result = backtrack([], set())
    return result if result else []