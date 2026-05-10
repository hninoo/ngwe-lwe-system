from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def normalize_money(value, places: int = 2) -> float:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid money amount.") from exc
    if not decimal_value.is_finite():
        raise ValueError("Invalid money amount.")
    quantum = Decimal("1") if places == 0 else Decimal("1").scaleb(-places)
    return float(decimal_value.quantize(quantum, rounding=ROUND_HALF_UP))

