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
    
    for perm in permutations(range(1, n + 1)):
        if is_valid(perm):
            return list(perm)
    
    return []