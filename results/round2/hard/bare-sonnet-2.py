def evaluate_expression(expr: str) -> float:
    expr = expr.replace(' ', '')
    
    def parse_expression(s, pos):
        left, pos = parse_term(s, pos)
        
        while pos < len(s) and s[pos] in '+-':
            op = s[pos]
            pos += 1
            right, pos = parse_term(s, pos)
            if op == '+':
                left = left + right
            else:
                left = left - right
        
        return left, pos
    
    def parse_term(s, pos):
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
    
    def parse_factor(s, pos):
        if s[pos] == '(':
            pos += 1
            result, pos = parse_expression(s, pos)
            pos += 1  # skip ')'
            return result, pos
        elif s[pos] == '-':
            pos += 1
            result, pos = parse_factor(s, pos)
            return -result, pos
        elif s[pos] == '+':
            pos += 1
            return parse_factor(s, pos)
        else:
            start = pos
            while pos < len(s) and (s[pos].isdigit() or s[pos] == '.'):
                pos += 1
            return float(s[start:pos]), pos
    
    result, _ = parse_expression(expr, 0)
    return result