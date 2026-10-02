import pytest

from app.inn import is_valid_inn


@pytest.mark.parametrize("inn", ["7707083893", "7736207543", "500100732259"])
def test_valid_inn(inn):
    assert is_valid_inn(inn)


@pytest.mark.parametrize(
    "inn",
    [
        "7707083894",  # неверная контрольная цифра
        "500100732258",
        "770708389",  # 9 цифр
        "77070838931",  # 11 цифр
        "77O7083893",  # буква вместо цифры
        "",
    ],
)
def test_invalid_inn(inn):
    assert not is_valid_inn(inn)
