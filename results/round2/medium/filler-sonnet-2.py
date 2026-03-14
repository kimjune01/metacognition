def balanced_brackets(s: str) -> bool:
    stack = []
    matching = {'(': ')', '[': ']', '{': '}'}
    opening = set(matching.keys())
    closing = set(matching.values())
    
    for char in s:
        if char in opening:
            stack.append(char)
        elif char in closing:
            if not stack:
                return False
            if matching[stack.pop()] != char:
                return False
    
    return len(stack) == 0