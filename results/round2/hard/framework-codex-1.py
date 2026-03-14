def evaluate_expression(expr: str) -> float:
    i = 0
    n = len(expr)

    def skip_spaces():
        nonlocal i
        while i < n and expr[i].isspace():
            i += 1

    def parse_expression() -> float:
        value = parse_term()
        while True:
            skip_spaces()
            if i < n and expr[i] in "+-":
                op = expr[i]
                advance()
                rhs = parse_term()
                value = value + rhs if op == "+" else value - rhs
            else:
                break
        return value

    def parse_term() -> float:
        value = parse_factor()
        while True:
            skip_spaces()
            if i < n and expr[i] in "*/":
                op = expr[i]
                advance()
                rhs = parse_factor()
                value = value * rhs if op == "*" else value / rhs
            else:
                break
        return value

    def parse_factor() -> float:
        skip_spaces()
        sign = 1
        while i < n and expr[i] in "+-":
            if expr[i] == "-":
                sign *= -1
            advance()
            skip_spaces()

        if expr[i] == "(":
            advance()
            value = parse_expression()
            skip_spaces()
            advance()  # consume ')'
            return sign * value

        start = i
        while i < n and expr[i].isdigit():
            advance()
        return sign * float(expr[start:i])

    def advance():
        nonlocal i
        i += 1

    return parse_expression()