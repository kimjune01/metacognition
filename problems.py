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
    "pipeline": {
        "name": "stabilize_board",
        "prompt": (
            "Write a function `stabilize_board(grid: list[list[str]]) -> list[list[str]]`\n\n"
            "You are given an m×n grid of symbols. Each cell contains a single uppercase "
            "letter ('A'-'Z'), a wildcard '*', a blocker '#', or empty '.'\n\n"
            "Simulate a match-3 game to stability:\n\n"
            "1. **Detect**: Find all horizontal or vertical runs of 3+ identical symbols. "
            "Wildcards '*' match any symbol and extend runs, but a run must contain at "
            "least one non-wildcard. Blockers '#' break runs and never match. "
            "All runs are detected SIMULTANEOUSLY before any deletion.\n\n"
            "2. **Delete**: Remove all cells that are part of any detected run by replacing "
            "them with '.'. Wildcards that participated in a run are also deleted. "
            "Blockers are never deleted.\n\n"
            "3. **Gravity**: For each column independently, non-empty cells fall down to "
            "fill gaps (empty '.' cells). Blockers '#' also fall. The relative order of "
            "falling cells within a column is preserved.\n\n"
            "4. **Repeat** steps 1-3 until no runs are detected (stable).\n\n"
            "Return the final stable grid. Do not modify the input.\n\n"
            "Examples:\n"
            "  stabilize_board([['A','A','A']]) -> [['.','.','.']]\n"
            "  stabilize_board([['A','B','A']]) -> [['A','B','A']]  # no run\n"
            "  stabilize_board([['A','*','A']]) -> [['.','.','.']]\n"
            "  # wildcard bridges the A's into a run of 3\n"
        ),
        "tests": [
            # Basic horizontal match
            ("g = stabilize_board([['A','A','A']]); print(g)", "[['.', '.', '.']]"),
            # No match
            ("g = stabilize_board([['A','B','A']]); print(g)", "[['A', 'B', 'A']]"),
            # Wildcard bridges
            ("g = stabilize_board([['A','*','A']]); print(g)", "[['.', '.', '.']]"),
            # Blocker breaks run
            ("g = stabilize_board([['A','#','A','A','A']]); print(g)", "[['A', '#', '.', '.', '.']]"),
            # Vertical match
            ("g = stabilize_board([['A'],['A'],['A']]); print(g)", "[['.'], ['.'], ['.']]"),
            # Gravity: match bottom row, top falls
            (
                "g = stabilize_board([['B','C','D'],['A','A','A']]); print(g)",
                "[['.', '.', '.'], ['B', 'C', 'D']]",
            ),
            # Chain reaction: match causes new match after gravity
            (
                "g = stabilize_board([['A','B','B'],['C','B','B'],['C','A','A'],['C','A','A']]); print(g)",
                # Column 0: C,C,C matches -> gravity drops A. Cols 1-2: after C's gone, check again
                # Let me trace: Original:
                # A B B
                # C B B
                # C A A
                # C A A
                # Col 0 vertical: C,C,C at rows 1,2,3 -> delete
                # No horizontal runs initially (A,B,B / C,B,B / C,A,A / C,A,A)
                # After delete col0 C's:
                # A B B
                # . B B
                # . A A
                # . A A
                # Gravity on col 0: A falls to bottom
                # . B B
                # . B B
                # . A A
                # A A A  <- row 3
                # Now row 3 has A,A,A -> match! Also col 1: B,B,A,A no. col2: B,B,A,A no.
                # Delete row 3:
                # . B B
                # . B B
                # . A A
                # . . .
                # Gravity: col1: B,B,A fall. col2: B,B,A fall.
                # . . .
                # . B B
                # . B B
                # . A A
                # Now col1 has B,B -> no (only 2). col2 has B,B -> no.
                # Stable.
                "[['.', '.', '.'], ['.', 'B', 'B'], ['.', 'B', 'B'], ['.', 'A', 'A']]",
            ),
            # Wildcard-only run should NOT match (need at least 1 non-wildcard)
            ("g = stabilize_board([['*','*','*']]); print(g)", "[['*', '*', '*']]"),
            # Simultaneous detection: overlapping runs
            (
                # T-shape: horizontal AAA on row 0, vertical A on col 1 rows 0-2
                "g = stabilize_board([['A','A','A'],['B','A','B'],['C','A','C']]); print(g)",
                # Horizontal AAA on row 0, vertical AAA on col 1
                # Delete all 5 A's simultaneously
                # . . .    gravity:   . . .
                # B . B    ->         . . .
                # C . C               B . B  wait...
                # Actually gravity: col0: B,C fall (already at bottom). col1: empty. col2: B,C fall.
                # After gravity:
                # . . .
                # B . B
                # C . C
                # That's already gravity-applied (B and C were already in rows 1,2)
                "[['.', '.', '.'], ['B', '.', 'B'], ['C', '.', 'C']]",
            ),
            # Blocker falls with gravity
            (
                "g = stabilize_board([['#','B','C'],['A','A','A']]); print(g)",
                "[['.', '.', '.'], ['#', 'B', 'C']]",
            ),
        ],
    },
}
