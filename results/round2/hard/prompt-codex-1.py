def evaluate_expression(expr: str) -> float:
    s = expr
    n = len(s)
    i = 0

    def skip_spaces():
        nonlocal i
        while i < n and s[i].isspace():
            i += 1

    def parse_expression() -> float:
        nonlocal i
        value = parse_term()
        while True:
            skip_spaces()
            if i < n and s[i] in "+-":
                op = s[i]
                i += 1
                rhs = parse_term()
                if op == "+":
                    value += rhs
                else:
                    value -= rhs
            else:
                break
        return value

    def parse_term() -> float:
        nonlocal i
        value = parse_factor()
        while True:
            skip_spaces()
            if i < n and s[i] in "*/":
                op = s[i]
                i += 1
                rhs = parse_factor()
                if op == "*":
                    value *= rhs
                else:
                    value /= rhs
            else:
                break
        return value

    def parse_factor() -> float:
        nonlocal i
        skip_spaces()

        sign = 1.0
        while i < n and s[i] in "+-":
            if s[i] == "-":
                sign *= -1.0
            i += 1
            skip_spaces()

        if i < n and s[i] == "(":
            i += 1
            value = parse_expression()
            skip_spaces()
            i += 1  # consume ')'
            return sign * value

        start = i
        while i < n and s[i].isdigit():
            i += 1
        return sign * float(s[start:i])

    result = parse_expression()
    skip_spaces()
    return result