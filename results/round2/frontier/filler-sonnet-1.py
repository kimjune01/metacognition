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
    
    if n <= 10:
        for perm in permutations(range(1, n + 1)):
            if is_valid(perm):
                return list(perm)
        return []
    
    def backtrack(assignment, used):
        if len(assignment) == n:
            return list(assignment) if is_valid(assignment) else None
        
        slot = len(assignment)
        
        for value in range(1, n + 1):
            if value in used:
                continue
            
            assignment.append(value)
            used.add(value)
            
            valid = True
            for constraint_type, i, j in constraints:
                if i < len(assignment) and j < len(assignment):
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
                elif i == slot or j == slot:
                    if i == slot:
                        other_idx = j
                        val_i = value
                        if other_idx < len(assignment) - 1:
                            val_j = assignment[other_idx]
                        else:
                            continue
                    else:
                        other_idx = i
                        val_j = value
                        if other_idx < len(assignment) - 1:
                            val_i = assignment[other_idx]
                        else:
                            continue
                    
                    if constraint_type == 'lt':
                        if val_i >= val_j:
                            valid = False
                            break
                    elif constraint_type == 'diff':
                        if abs(val_i - val_j) < 2:
                            valid = False
                            break
                    elif constraint_type == 'adj':
                        if abs(val_i - val_j) != 1:
                            valid = False
                            break
            
            if valid:
                result = backtrack(assignment, used)
                if result is not None:
                    return result
            
            assignment.pop()
            used.remove(value)
        
        return None
    
    result = backtrack([], set())
    return result if result is not None else []