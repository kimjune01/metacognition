def evaluate_expression(expr: str) -> float:
    s = expr
    n = len(s)
    i = 0

    def skip_spaces():
        nonlocal i
        while i < n and s[i].isspace():
            i += 1

    def parse_expression():
        value = parse_term()
        while True:
            skip_spaces()
            if i < n and s[i] in "+-":
                op = s[i]
                advance()
                rhs = parse_term()
                value = value + rhs if op == "+" else value - rhs
            else:
                break
        return value

    def parse_term():
        value = parse_factor()
        while True:
            skip_spaces()
            if i < n and s[i] in "*/":
                op = s[i]
                advance()
                rhs = parse_factor()
                value = value * rhs if op == "*" else value / rhs
            else:
                break
        return value

    def parse_factor():
        skip_spaces()
        sign = 1.0
        while i < n and s[i] in "+-":
            if s[i] == "-":
                sign *= -1.0
            advance()
            skip_spaces()

        if i < n and s[i] == "(":
            advance()
            value = parse_expression()
            skip_spaces()
            advance()  # consume ')'
            return sign * value

        start = i
        while i < n and s[i].isdigit():
            advance()
        return sign * float(int(s[start:i]))

    def advance():
        nonlocal i
        i += 1

    return parse_expression()