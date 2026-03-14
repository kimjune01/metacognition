def balanced_brackets(s: str) -> bool:
    stack = []
    bracket_map = {')': '(', ']': '[', '}': '{'}
    
    for char in s:
        if char in '([{':
            stack.append(char)
        elif char in ')]}':
            if not stack or stack[-1] != bracket_map[char]:
                return False
            stack.pop()
    
    return len(stack) == 0