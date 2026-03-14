def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from itertools import permutations
    
    def is_valid(assignment):
        for constraint_type, i, j in constraints:
            val_i = assignment[i]
            val_j = assignment[j]
            
            if constraint_type == 'lt':
                if not (val_i < val_j):
                    return False
            elif constraint_type == 'diff':
                if not (abs(val_i - val_j) >= 2):
                    return False
            elif constraint_type == 'adj':
                if not (abs(val_i - val_j) == 1):
                    return False
        
        return True
    
    # For small n, try all permutations
    if n <= 8:
        for perm in permutations(range(1, n + 1)):
            if is_valid(list(perm)):
                return list(perm)
        return []
    
    # For larger n, use backtracking
    def backtrack(assignment, remaining):
        if len(assignment) == n:
            return assignment[:]
        
        slot_idx = len(assignment)
        
        for value in sorted(remaining):
            assignment.append(value)
            
            # Check all constraints involving this slot
            valid = True
            for constraint_type, i, j in constraints:
                if i == slot_idx:
                    if j < len(assignment):
                        val_i = assignment[i]
                        val_j = assignment[j]
                        if constraint_type == 'lt' and not (val_i < val_j):
                            valid = False
                            break
                        elif constraint_type == 'diff' and not (abs(val_i - val_j) >= 2):
                            valid = False
                            break
                        elif constraint_type == 'adj' and not (abs(val_i - val_j) == 1):
                            valid = False
                            break
                elif j == slot_idx:
                    if i < len(assignment):
                        val_i = assignment[i]
                        val_j = assignment[j]
                        if constraint_type == 'lt' and not (val_i < val_j):
                            valid = False
                            break
                        elif constraint_type == 'diff' and not (abs(val_i - val_j) >= 2):
                            valid = False
                            break
                        elif constraint_type == 'adj' and not (abs(val_i - val_j) == 1):
                            valid = False
                            break
            
            if valid:
                remaining.remove(value)
                result = backtrack(assignment, remaining)
                if result:
                    return result
                remaining.add(value)
            
            assignment.pop()
        
        return None
    
    result = backtrack([], set(range(1, n + 1)))
    return result if result else []