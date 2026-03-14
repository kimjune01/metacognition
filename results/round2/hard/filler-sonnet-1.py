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
            val, i = parse_expr(s, i)
            while i < len(s) and s[i] == ' ':
                i += 1
            i += 1  # skip ')'
            return val, i
        else:
            return parse_number(s, i)
    
    def parse_term(s, i):
        val, i = parse_factor(s, i)
        
        while i < len(s):
            while i < len(s) and s[i] == ' ':
                i += 1
            if i >= len(s) or s[i] not in ('*', '/'):
                break
            op = s[i]
            i += 1
            right, i = parse_factor(s, i)
            if op == '*':
                val = val * right
            else:
                val = val / right
        
        return val, i
    
    def parse_expr(s, i):
        val, i = parse_term(s, i)
        
        while i < len(s):
            while i < len(s) and s[i] == ' ':
                i += 1
            if i >= len(s) or s[i] not in ('+', '-'):
                break
            op = s[i]
            i += 1
            right, i = parse_term(s, i)
            if op == '+':
                val = val + right
            else:
                val = val - right
        
        return val, i
    
    result, _ = parse_expr(expr, 0)
    return result