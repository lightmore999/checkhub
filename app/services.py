"""Выполнение проверки: параллельный опрос поставщиков и сборка отчёта."""

import asyncio
import logging
import uuid

from fastapi import FastAPI

from app.cache import JsonCache
from app.models import Check, CheckStatus, ProviderCall, utcnow
from app.providers import PROVIDERS, CircuitBreaker, ProviderClient
from app.risk import compute_risk

logger = logging.getLogger(__name__)


def build_clients(app: FastAPI) -> list[ProviderClient]:
    state = app.state
    settings = state.settings
    cache = JsonCache(state.redis, settings.cache_ttl_seconds)
    clients = []
    for spec in PROVIDERS:
        breaker = state.breakers.setdefault(
            spec.name,
            CircuitBreaker(settings.breaker_threshold, settings.breaker_cooldown_seconds),
        )
        clients.append(ProviderClient(spec, state.http, cache, breaker, settings))
    return clients


async def run_check(app: FastAPI, check_id: uuid.UUID) -> None:
    async with app.state.sessionmaker() as session:
        check = await session.get(Check, check_id)
        if check is None:
            return
        check.status = CheckStatus.RUNNING
        await session.commit()

        try:
            # Поставщики опрашиваются параллельно: время проверки ≈ время самого медленного.
            results = await asyncio.gather(*(c.fetch(check.inn) for c in build_clients(app)))

            report = {r.provider: r.data for r in results}
            score, level, factors = compute_risk(report)

            session.add_all(
                ProviderCall(
                    check_id=check.id,
                    provider=r.provider,
                    status=r.status,
                    attempts=r.attempts,
                    duration_ms=r.duration_ms,
                    cost_kop=r.cost_kop,
                    error=r.error,
                )
                for r in results
            )
            check.report = {
                **report,
                "failed_providers": [r.provider for r in results if r.data is None],
            }
            check.risk_score, check.risk_level, check.risk_factors = score, level, factors
            check.total_cost_kop = sum(r.cost_kop for r in results)
            check.status = CheckStatus.DONE
        except Exception:
            logger.exception("Check %s failed", check_id)
            check.status = CheckStatus.FAILED
        check.finished_at = utcnow()
        await session.commit()
