def balanced_brackets(s: str) -> bool:
    stack = []
    brackets = {'(': ')', '[': ']', '{': '}'}
    closing = set(brackets.values())
    
    for char in s:
        if char in brackets:
            stack.append(char)
        elif char in closing:
            if not stack or brackets[stack.pop()] != char:
                return False
    
    return len(stack) == 0