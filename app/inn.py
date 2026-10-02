"""Проверка ИНН по контрольным разрядам (алгоритм ФНС)."""

_W10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_W11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_W12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _control_digit(digits: list[int], weights: tuple[int, ...]) -> int:
    return sum(w * d for w, d in zip(weights, digits, strict=False)) % 11 % 10


def is_valid_inn(inn: str) -> bool:
    """10 цифр — юрлицо, 12 цифр — физлицо или ИП."""
    if not inn.isdigit() or len(inn) not in (10, 12):
        return False
    digits = [int(c) for c in inn]
    if len(digits) == 10:
        return _control_digit(digits, _W10) == digits[9]
    return _control_digit(digits, _W11) == digits[10] and _control_digit(digits, _W12) == digits[11]
