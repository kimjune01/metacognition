def balanced_brackets(s: str) -> bool:
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    openings = set(pairs.values())

    for ch in s:
        if ch in openings:
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack[-1] != pairs[ch]:
                return False
            stack.pop()

    return not stack