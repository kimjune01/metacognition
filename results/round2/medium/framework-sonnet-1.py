def balanced_brackets(s: str) -> bool:
    stack = []
    matching = {'(': ')', '[': ']', '{': '}'}
    
    for char in s:
        if char in matching:
            stack.append(char)
        elif char in matching.values():
            if not stack or matching[stack.pop()] != char:
                return False
    
    return len(stack) == 0