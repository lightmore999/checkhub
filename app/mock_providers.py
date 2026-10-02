"""Заглушки внешних поставщиков, чтобы сервис работал «из коробки».

Данные детерминированы по ИНН, а задержки и сбои случайны — как у настоящих API.
"""

import asyncio
import random
from collections.abc import Callable
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/mock", tags=["mock providers"], include_in_schema=False)

_NAMES = ("Вектор", "Альфа", "Северный ветер", "Технопром", "Гранит", "Меридиан", "Ладога")
_FORMS = ("Строй", "Трейд", "Логистик", "Софт", "Агро", "Сервис")


def _registry(rng: random.Random, inn: str) -> dict:
    registered = date(2005, 1, 1) + timedelta(days=rng.randint(0, 7300))
    return {
        "inn": inn,
        "name": f"ООО «{rng.choice(_NAMES)} {rng.choice(_FORMS)}»",
        "status": rng.choices(["active", "liquidated"], weights=[9, 1])[0],
        "registered_at": registered.isoformat(),
        "mass_address": rng.random() < 0.1,
    }


def _courts(rng: random.Random, inn: str) -> dict:
    total = rng.randint(0, 20)
    return {
        "cases_total": total,
        "as_defendant": rng.randint(0, total),
        "claims_sum": rng.randint(0, 3_000_000),
    }


def _bankruptcy(rng: random.Random, inn: str) -> dict:
    has = rng.random() < 0.05
    return {"has_bankruptcy": has, "messages": rng.randint(1, 5) if has else 0}


def _debts(rng: random.Random, inn: str) -> dict:
    count = rng.choices([0, 1, 2, 5], weights=[6, 2, 1, 1])[0]
    return {"enforcement_count": count, "debt_sum": rng.randint(10_000, 900_000) if count else 0}


GENERATORS: dict[str, Callable[[random.Random, str], dict]] = {
    "registry": _registry,
    "courts": _courts,
    "bankruptcy": _bankruptcy,
    "debts": _debts,
}


@router.get("/{provider}/{inn}")
async def mock_provider(provider: str, inn: str, request: Request) -> dict:
    settings = request.app.state.settings
    generator = GENERATORS.get(provider)
    if generator is None:
        raise HTTPException(404, "Unknown provider")
    if settings.mock_latency_seconds:
        await asyncio.sleep(random.uniform(0, settings.mock_latency_seconds))
    if random.random() < settings.mock_failure_rate:
        raise HTTPException(503, "Provider temporarily unavailable")
    return generator(random.Random(f"{provider}:{inn}"), inn)
