from datetime import date

from app.risk import compute_risk

TODAY = date(2026, 10, 1)

CLEAN = {
    "registry": {"status": "active", "registered_at": "2015-03-01", "mass_address": False},
    "courts": {"cases_total": 1, "as_defendant": 0, "claims_sum": 50_000},
    "bankruptcy": {"has_bankruptcy": False, "messages": 0},
    "debts": {"enforcement_count": 0, "debt_sum": 0},
}


def test_clean_company_is_low_risk():
    score, level, factors = compute_risk(CLEAN, TODAY)
    assert (score, level, factors) == (0, "low", [])


def test_liquidated_and_bankrupt_is_high_risk_and_capped():
    report = {
        **CLEAN,
        "registry": {**CLEAN["registry"], "status": "liquidated"},
        "bankruptcy": {"has_bankruptcy": True, "messages": 3},
    }
    score, level, factors = compute_risk(report, TODAY)
    assert score == 100
    assert level == "high"
    assert "Организация ликвидирована" in factors


def test_missing_registry_is_a_risk_factor():
    score, level, factors = compute_risk({**CLEAN, "registry": None}, TODAY)
    assert score == 20
    assert level == "low"
    assert factors == ["Нет данных из реестра — проверка неполная"]


def test_young_company_with_debts_is_medium():
    report = {
        **CLEAN,
        "registry": {**CLEAN["registry"], "registered_at": "2026-05-01"},
        "debts": {"enforcement_count": 2, "debt_sum": 600_000},
    }
    score, level, _ = compute_risk(report, TODAY)
    assert (score, level) == (40, "medium")
