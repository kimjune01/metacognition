def evaluate_expression(expr: str) -> float:
    expr = expr.replace(' ', '')
    
    def parse_number(s, pos):
        start = pos
        if pos < len(s) and s[pos] in '+-':
            pos += 1
        while pos < len(s) and (s[pos].isdigit() or s[pos] == '.'):
            pos += 1
        return float(s[start:pos]), pos
    
    def parse_factor(s, pos):
        if s[pos] == '(':
            pos += 1
            result, pos = parse_additive(s, pos)
            pos += 1  # skip ')'
            return result, pos
        elif s[pos] == '-':
            pos += 1
            val, pos = parse_factor(s, pos)
            return -val, pos
        elif s[pos] == '+':
            pos += 1
            return parse_factor(s, pos)
        else:
            return parse_number(s, pos)
    
    def parse_multiplicative(s, pos):
        left, pos = parse_factor(s, pos)
        
        while pos < len(s) and s[pos] in '*/':
            op = s[pos]
            pos += 1
            right, pos = parse_factor(s, pos)
            if op == '*':
                left = left * right
            else:
                left = left / right
        
        return left, pos
    
    def parse_additive(s, pos):
        left, pos = parse_multiplicative(s, pos)
        
        while pos < len(s) and s[pos] in '+-':
            op = s[pos]
            pos += 1
            right, pos = parse_multiplicative(s, pos)
            if op == '+':
                left = left + right
            else:
                left = left - right
        
        return left, pos
    
    result, _ = parse_additive(expr, 0)
    return result