"""Оценка риска контрагента по сводному отчёту. Правила простые и объяснимые."""

from datetime import date


def compute_risk(
    report: dict[str, dict | None], today: date | None = None
) -> tuple[int, str, list[str]]:
    """Возвращает (балл 0–100, уровень low/medium/high, список причин)."""
    today = today or date.today()
    score = 0
    factors: list[str] = []

    def add(points: int, reason: str) -> None:
        nonlocal score
        score += points
        factors.append(reason)

    registry = report.get("registry")
    if registry is None:
        add(20, "Нет данных из реестра — проверка неполная")
    else:
        if registry.get("status") == "liquidated":
            add(60, "Организация ликвидирована")
        registered = date.fromisoformat(registry["registered_at"])
        if (today - registered).days < 365:
            add(15, "Зарегистрирована меньше года назад")
        if registry.get("mass_address"):
            add(10, "Адрес массовой регистрации")

    courts = report.get("courts")
    if courts:
        if courts.get("as_defendant", 0) >= 5:
            add(15, f"Ответчик по {courts['as_defendant']} арбитражным делам")
        if courts.get("claims_sum", 0) > 1_000_000:
            add(10, "Сумма исков больше 1 млн ₽")

    bankruptcy = report.get("bankruptcy")
    if bankruptcy and bankruptcy.get("has_bankruptcy"):
        add(50, "Есть сообщения о банкротстве")

    debts = report.get("debts")
    if debts:
        if debts.get("enforcement_count", 0) > 0:
            add(10, f"Исполнительных производств: {debts['enforcement_count']}")
        if debts.get("debt_sum", 0) > 500_000:
            add(15, "Долги по исполнительным производствам больше 500 тыс. ₽")

    score = min(score, 100)
    level = "low" if score < 25 else "medium" if score < 50 else "high"
    return score, level, factors
