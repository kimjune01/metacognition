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
    
    # For small n, brute force with permutations
    if n <= 10:
        for perm in permutations(range(1, n + 1)):
            if is_valid(perm):
                return list(perm)
        return []
    
    # For larger n, use backtracking with constraint propagation
    def backtrack(assignment, remaining):
        if len(assignment) == n:
            return assignment if is_valid(assignment) else None
        
        slot = len(assignment)
        for value in sorted(remaining):
            assignment.append(value)
            
            # Check constraints involving this slot
            valid = True
            for constraint_type, i, j in constraints:
                if j == slot and i < slot:
                    if constraint_type == 'lt':
                        if assignment[i] >= assignment[j]:
                            valid = False
                            break
                    elif constraint_type == 'diff':
                        if abs(assignment[i] - assignment[j]) < 2:
                            valid = False
                            break
                    elif constraint_type == 'adj':
                        if abs(assignment[i] - assignment[j]) != 1:
                            valid = False
                            break
                elif i == slot and j < slot:
                    if constraint_type == 'lt':
                        if assignment[i] >= assignment[j]:
                            valid = False
                            break
                    elif constraint_type == 'diff':
                        if abs(assignment[i] - assignment[j]) < 2:
                            valid = False
                            break
                    elif constraint_type == 'adj':
                        if abs(assignment[i] - assignment[j]) != 1:
                            valid = False
                            break
            
            if valid:
                new_remaining = remaining - {value}
                result = backtrack(assignment, new_remaining)
                if result is not None:
                    return result
            
            assignment.pop()
        
        return None
    
    result = backtrack([], set(range(1, n + 1)))
    return result if result is not None else []