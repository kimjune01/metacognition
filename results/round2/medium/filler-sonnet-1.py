def balanced_brackets(s: str) -> bool:
    stack = []
    brackets = {'(': ')', '[': ']', '{': '}'}
    
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in brackets.values():
            if not stack or brackets[stack.pop()] != char:
                return False
    
    return len(stack) == 0