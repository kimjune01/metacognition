def evaluate_expression(expr: str) -> float:
    i = 0
    n = len(expr)

    def skip_spaces():
        nonlocal i
        while i < n and expr[i].isspace():
            i += 1

    def parse_number() -> float:
        nonlocal i
        skip_spaces()
        start = i
        while i < n and expr[i].isdigit():
            i += 1
        return float(expr[start:i])

    def parse_factor() -> float:
        nonlocal i
        skip_spaces()
        sign = 1.0
        while i < n and expr[i] in "+-":
            if expr[i] == "-":
                sign *= -1.0
            i += 1
            skip_spaces()
        if i < n and expr[i] == "(":
            i += 1
            value = parse_expression()
            skip_spaces()
            i += 1  # consume ')'
            return sign * value
        return sign * parse_number()

    def parse_term() -> float:
        nonlocal i
        value = parse_factor()
        while True:
            skip_spaces()
            if i < n and expr[i] in "*/":
                op = expr[i]
                i += 1
                rhs = parse_factor()
                if op == "*":
                    value *= rhs
                else:
                    value /= rhs
            else:
                break
        return value

    def parse_expression() -> float:
        nonlocal i
        value = parse_term()
        while True:
            skip_spaces()
            if i < n and expr[i] in "+-":
                op = expr[i]
                i += 1
                rhs = parse_term()
                if op == "+":
                    value += rhs
                else:
                    value -= rhs
            else:
                break
        return value

    return parse_expression()