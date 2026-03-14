def evaluate_expression(expr: str) -> float:
    expr = expr.replace(' ', '')
    
    def parse_number(s, i):
        j = i
        if j < len(s) and s[j] in '+-':
            j += 1
        while j < len(s) and (s[j].isdigit() or s[j] == '.'):
            j += 1
        return float(s[i:j]), j
    
    def parse_factor(s, i):
        if s[i] == '(':
            val, i = parse_expr(s, i + 1)
            return val, i + 1
        else:
            return parse_number(s, i)
    
    def parse_term(s, i):
        left, i = parse_factor(s, i)
        while i < len(s) and s[i] in '*/':
            op = s[i]
            right, i = parse_factor(s, i + 1)
            if op == '*':
                left = left * right
            else:
                left = left / right
        return left, i
    
    def parse_expr(s, i):
        left, i = parse_term(s, i)
        while i < len(s) and s[i] in '+-':
            op = s[i]
            right, i = parse_term(s, i + 1)
            if op == '+':
                left = left + right
            else:
                left = left - right
        return left, i
    
    result, _ = parse_expr(expr, 0)
    return result