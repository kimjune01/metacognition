"""Coding problems with test suites for metacognition experiment."""

PROBLEMS = {
    "easy": {
        "name": "run_length_encode",
        "prompt": (
            "Write a function `run_length_encode(s: str) -> list[tuple[str, int]]` "
            "that takes a string and returns a list of (character, count) tuples "
            "representing the run-length encoding.\n\n"
            "Examples:\n"
            "  run_length_encode('aabbbcc') -> [('a', 2), ('b', 3), ('c', 2)]\n"
            "  run_length_encode('') -> []\n"
            "  run_length_encode('xyz') -> [('x', 1), ('y', 1), ('z', 1)]\n"
        ),
        "tests": [
            ("run_length_encode('aabbbcc')", "[('a', 2), ('b', 3), ('c', 2)]"),
            ("run_length_encode('')", "[]"),
            ("run_length_encode('xyz')", "[('x', 1), ('y', 1), ('z', 1)]"),
            ("run_length_encode('aaaa')", "[('a', 4)]"),
            ("run_length_encode('aabbaa')", "[('a', 2), ('b', 2), ('a', 2)]"),
            ("run_length_encode('a')", "[('a', 1)]"),
        ],
    },
    "medium": {
        "name": "balanced_brackets",
        "prompt": (
            "Write a function `balanced_brackets(s: str) -> bool` that returns True "
            "if the string contains balanced brackets. The string may contain "
            "characters '(', ')', '[', ']', '{', '}' and any other characters "
            "(which should be ignored). Empty string is balanced.\n\n"
            "Examples:\n"
            "  balanced_brackets('({[]})') -> True\n"
            "  balanced_brackets('([)]') -> False\n"
            "  balanced_brackets('hello (world)') -> True\n"
        ),
        "tests": [
            ("balanced_brackets('({[]})')", "True"),
            ("balanced_brackets('([)]')", "False"),
            ("balanced_brackets('hello (world)')", "True"),
            ("balanced_brackets('')", "True"),
            ("balanced_brackets('(((')", "False"),
            ("balanced_brackets('{[()()]}')", "True"),
            ("balanced_brackets('}{)')", "False"),
            ("balanced_brackets('a(b[c{d}e]f)g')", "True"),
        ],
    },
    "hard": {
        "name": "evaluate_expression",
        "prompt": (
            "Write a function `evaluate_expression(expr: str) -> float` that "
            "evaluates a mathematical expression string containing integers, "
            "+, -, *, /, and parentheses. Follow standard operator precedence "
            "(* and / before + and -). Division is float division. "
            "The expression will always be valid.\n\n"
            "Examples:\n"
            "  evaluate_expression('2 + 3 * 4') -> 14.0\n"
            "  evaluate_expression('(2 + 3) * 4') -> 20.0\n"
            "  evaluate_expression('10 / 3') -> 3.3333333333333335\n"
            "\n"
            "Do NOT use eval() or exec().\n"
        ),
        "tests": [
            ("evaluate_expression('2 + 3 * 4')", "14.0"),
            ("evaluate_expression('(2 + 3) * 4')", "20.0"),
            ("evaluate_expression('10 - 2 - 3')", "5.0"),
            ("evaluate_expression('2 * 3 + 4 * 5')", "26.0"),
            ("evaluate_expression('(1 + 2) * (3 + 4)')", "21.0"),
            ("evaluate_expression('100')", "100.0"),
            ("evaluate_expression('10 / 4')", "2.5"),
            ("evaluate_expression('2 + 3 * 4 - 6 / 2')", "11.0"),
            ("evaluate_expression('((2 + 3) * (4 - 1)) / 5')", "3.0"),
            ("evaluate_expression('1 + 2 * 3 + 4 * 5 + 6')", "33.0"),
        ],
    },
    "frontier": {
        "name": "solve_constraints",
        "prompt": (
            "Write a function `solve_constraints(n: int, constraints: list[tuple[str, int, int]]) -> list[int]`\n\n"
            "You are assigning values 1..n to n slots (0-indexed). Each slot gets a unique value.\n"
            "Constraints are triples of (type, i, j) where i and j are slot indices:\n"
            "  ('lt', i, j) means slot[i] < slot[j]\n"
            "  ('diff', i, j) means |slot[i] - slot[j]| >= 2\n"
            "  ('adj', i, j) means |slot[i] - slot[j]| == 1\n\n"
            "Return any valid assignment as a list of n integers, or an empty list if impossible.\n\n"
            "Examples:\n"
            "  solve_constraints(3, [('lt', 0, 1), ('lt', 1, 2)]) -> [1, 2, 3]\n"
            "  solve_constraints(3, [('lt', 0, 1), ('lt', 1, 2), ('lt', 2, 0)]) -> []\n"
            "  solve_constraints(4, [('diff', 0, 1), ('adj', 2, 3)]) could return [1, 3, 2, 1]... "
            "wait, values must be unique. Could return [1, 3, 2, 4] -- but check: |1-3|>=2 yes, |2-4|==... "
            "no, |2-4|=2 != 1. Try [1, 4, 2, 3]: |1-4|>=2 yes, |2-3|==1 yes. Valid.\n"
        ),
        "tests": [
            # Simple ordering
            ("r = solve_constraints(3, [('lt', 0, 1), ('lt', 1, 2)]); assert len(r)==3 and len(set(r))==3 and all(1<=v<=3 for v in r) and r[0]<r[1]<r[2]; print(True)", "True"),
            # Cycle -> impossible
            ("r = solve_constraints(3, [('lt', 0, 1), ('lt', 1, 2), ('lt', 2, 0)]); print(r == [])", "True"),
            # diff constraint
            ("r = solve_constraints(4, [('diff', 0, 1)]); assert len(r)==4 and len(set(r))==4 and all(1<=v<=4 for v in r) and abs(r[0]-r[1])>=2; print(True)", "True"),
            # adj constraint
            ("r = solve_constraints(4, [('adj', 0, 1)]); assert len(r)==4 and len(set(r))==4 and all(1<=v<=4 for v in r) and abs(r[0]-r[1])==1; print(True)", "True"),
            # Mixed: lt + diff
            ("r = solve_constraints(4, [('lt', 0, 1), ('diff', 0, 1)]); assert len(r)==4 and len(set(r))==4 and all(1<=v<=4 for v in r) and r[0]<r[1] and abs(r[0]-r[1])>=2; print(True)", "True"),
            # Mixed: lt + adj
            ("r = solve_constraints(5, [('lt', 0, 1), ('adj', 0, 1), ('lt', 2, 3), ('adj', 2, 3)]); assert len(r)==5 and len(set(r))==5 and all(1<=v<=5 for v in r) and r[0]<r[1] and abs(r[0]-r[1])==1 and r[2]<r[3] and abs(r[2]-r[3])==1; print(True)", "True"),
            # Impossible: adj + diff on same pair
            ("r = solve_constraints(3, [('adj', 0, 1), ('diff', 0, 1)]); print(r == [])", "True"),
            # Larger: chain of lt
            ("r = solve_constraints(6, [('lt', i, i+1) for i in range(5)]); assert len(r)==6 and len(set(r))==6 and all(1<=v<=6 for v in r) and all(r[i]<r[i+1] for i in range(5)); print(True)", "True"),
            # diff forces spread: 3 slots, all pairs diff>=2, values 1..3 -> impossible (max spread 2 with 3 unique values from {1,2,3})
            ("r = solve_constraints(3, [('diff', 0, 1), ('diff', 1, 2), ('diff', 0, 2)]); print(r == [])", "True"),
            # 4 slots, all adjacent pairs must be adj
            ("r = solve_constraints(4, [('adj', 0, 1), ('adj', 1, 2), ('adj', 2, 3)]); assert len(r)==4 and len(set(r))==4 and all(1<=v<=4 for v in r) and all(abs(r[i]-r[i+1])==1 for i in range(3)); print(True)", "True"),
        ],
    },
}
