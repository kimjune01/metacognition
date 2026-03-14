def evaluate_expression(expr: str) -> float:
    s = expr.replace(" ", "")
    i = 0

    def parse_expression():
        nonlocal i
        value = parse_term()
        while i < len(s) and s[i] in "+-":
            op = s[i]
            i += 1
            rhs = parse_term()
            if op == "+":
                value += rhs
            else:
                value -= rhs
        return value

    def parse_term():
        nonlocal i
        value = parse_factor()
        while i < len(s) and s[i] in "*/":
            op = s[i]
            i += 1
            rhs = parse_factor()
            if op == "*":
                value *= rhs
            else:
                value /= rhs
        return value

    def parse_factor():
        nonlocal i
        if s[i] == "(":
            i += 1
            value = parse_expression()
            i += 1
            return value
        sign = 1
        if s[i] == "+":
            i += 1
        elif s[i] == "-":
            sign = -1
            i += 1
        if s[i] == "(":
            i += 1
            value = parse_expression()
            i += 1
            return sign * value
        start = i
        while i < len(s) and s[i].isdigit():
            i += 1
        return sign * float(s[start:i])

    return parse_expression()