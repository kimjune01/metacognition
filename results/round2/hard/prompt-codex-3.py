def evaluate_expression(expr: str) -> float:
    s = expr
    n = len(s)
    i = 0

    def skip_spaces() -> None:
        nonlocal i
        while i < n and s[i].isspace():
            i += 1

    def parse_expression() -> float:
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

    def parse_term() -> float:
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

    def parse_factor() -> float:
        skip_spaces()
        if i < n and s[i] in "+-":
            op = s[i]
            advance()
            value = parse_factor()
            return value if op == "+" else -value

        if i < n and s[i] == "(":
            advance()
            value = parse_expression()
            skip_spaces()
            advance()  # consume ')'
            return value

        return parse_number()

    def parse_number() -> float:
        nonlocal i
        skip_spaces()
        start = i
        while i < n and s[i].isdigit():
            i += 1
        return float(s[start:i])

    def advance() -> None:
        nonlocal i
        i += 1

    return parse_expression()