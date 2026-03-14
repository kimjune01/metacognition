def solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]:
    from itertools import permutations
    
    # For small n, try all permutations
    if n <= 8:
        for perm in permutations(range(1, n + 1)):
            valid = True
            for constraint_type, i, j in constraints:
                if constraint_type == 'lt':
                    if not (perm[i] < perm[j]):
                        valid = False
                        break
                elif constraint_type == 'diff':
                    if not (abs(perm[i] - perm[j]) >= 2):
                        valid = False
                        break
                elif constraint_type == 'adj':
                    if not (abs(perm[i] - perm[j]) == 1):
                        valid = False
                        break
            if valid:
                return list(perm)
        return []
    
    # For larger n, use backtracking with constraint propagation
    def is_valid(assignment, slot, value):
        for constraint_type, i, j in constraints:
            if i == slot:
                if j < len(assignment):
                    other_val = assignment[j]
                    if constraint_type == 'lt' and not (value < other_val):
                        return False
                    elif constraint_type == 'diff' and not (abs(value - other_val) >= 2):
                        return False
                    elif constraint_type == 'adj' and not (abs(value - other_val) == 1):
                        return False
            elif j == slot:
                if i < len(assignment):
                    other_val = assignment[i]
                    if constraint_type == 'lt' and not (other_val < value):
                        return False
                    elif constraint_type == 'diff' and not (abs(other_val - value) >= 2):
                        return False
                    elif constraint_type == 'adj' and not (abs(other_val - value) == 1):
                        return False
        return True
    
    def backtrack(assignment, used):
        if len(assignment) == n:
            return assignment[:]
        
        slot = len(assignment)
        for value in range(1, n + 1):
            if value not in used and is_valid(assignment, slot, value):
                assignment.append(value)
                used.add(value)
                result = backtrack(assignment, used)
                if result:
                    return result
                assignment.pop()
                used.remove(value)
        
        return None
    
    result = backtrack([], set())
    return result if result else []