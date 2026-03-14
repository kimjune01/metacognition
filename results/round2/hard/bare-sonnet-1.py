def evaluate_expression(expr: str) -> float:
    def parse_number(s, i):
        j = i
        while j < len(s) and (s[j].isdigit() or s[j] == '.'):
            j += 1
        return float(s[i:j]), j
    
    def parse_factor(s, i):
        while i < len(s) and s[i] == ' ':
            i += 1
        
        if s[i] == '(':
            i += 1
            result, i = parse_addition(s, i)
            while i < len(s) and s[i] == ' ':
                i += 1
            i += 1  # skip ')'
            return result, i
        else:
            return parse_number(s, i)
    
    def parse_multiplication(s, i):
        left, i = parse_factor(s, i)
        
        while i < len(s):
            while i < len(s) and s[i] == ' ':
                i += 1
            
            if i >= len(s) or s[i] not in '*/' :
                break
            
            op = s[i]
            i += 1
            right, i = parse_factor(s, i)
            
            if op == '*':
                left = left * right
            else:
                left = left / right
        
        return left, i
    
    def parse_addition(s, i):
        left, i = parse_multiplication(s, i)
        
        while i < len(s):
            while i < len(s) and s[i] == ' ':
                i += 1
            
            if i >= len(s) or s[i] not in '+-':
                break
            
            op = s[i]
            i += 1
            right, i = parse_multiplication(s, i)
            
            if op == '+':
                left = left + right
            else:
                left = left - right
        
        return left, i
    
    result, _ = parse_addition(expr, 0)
    return result