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
    
    for perm in permutations(range(1, n + 1)):
        if is_valid(perm):
            return list(perm)
    
    return []