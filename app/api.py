import hashlib
import secrets
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Check, ProviderCall
from app.rate_limit import hit_rate_limit
from app.schemas import CheckCreate, CheckOut, ProviderStats, StatsOut
from app.services import run_check


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_api_key(
    request: Request, x_api_key: Annotated[str | None, Header()] = None
) -> str:
    settings = request.app.state.settings
    if not x_api_key or not any(secrets.compare_digest(x_api_key, k) for k in settings.api_keys):
        raise HTTPException(401, "Неверный или отсутствующий API-ключ")
    # В Redis кладём не сам ключ, а его хэш.
    key_id = hashlib.sha256(x_api_key.encode()).hexdigest()[:16]
    if await hit_rate_limit(request.app.state.redis, key_id, settings.rate_limit_per_minute):
        raise HTTPException(429, "Слишком много запросов, попробуйте через минуту",
                            headers={"Retry-After": "60"})
    return key_id


router = APIRouter(prefix="/api/v1", tags=["checks"], dependencies=[Depends(require_api_key)])


@router.post("/checks", status_code=202, response_model=CheckOut)
async def create_check(
    payload: CheckCreate, request: Request, background: BackgroundTasks, session: SessionDep
) -> Check:
    """Создаёт проверку. Поставщики опрашиваются в фоне, результат — в GET /checks/{id}."""
    check = Check(inn=payload.inn, calls=[])
    session.add(check)
    await session.commit()
    background.add_task(run_check, request.app, check.id)
    return check


@router.get("/checks/{check_id}", response_model=CheckOut)
async def get_check(check_id: uuid.UUID, session: SessionDep) -> Check:
    check = await session.get(Check, check_id, options=[selectinload(Check.calls)])
    if check is None:
        raise HTTPException(404, "Проверка не найдена")
    return check


@router.get("/checks", response_model=list[CheckOut])
async def list_checks(
    session: SessionDep,
    inn: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Check]:
    query = select(Check).options(selectinload(Check.calls)).order_by(Check.created_at.desc())
    if inn:
        query = query.where(Check.inn == inn)
    return list((await session.scalars(query.limit(limit))).all())


@router.get("/stats", response_model=StatsOut)
async def stats(session: SessionDep) -> StatsOut:
    """Сколько стоили проверки и как часто выручает кэш — по каждому поставщику."""
    rows = (
        await session.execute(
            select(
                ProviderCall.provider,
                func.count(),
                func.sum(case((ProviderCall.status == "ok", 1), else_=0)),
                func.sum(case((ProviderCall.status == "cached", 1), else_=0)),
                func.sum(case((ProviderCall.status.in_(["failed", "skipped"]), 1), else_=0)),
                func.avg(ProviderCall.duration_ms),
                func.sum(ProviderCall.cost_kop),
            )
            .group_by(ProviderCall.provider)
            .order_by(ProviderCall.provider)
        )
    ).all()
    providers = [
        ProviderStats(
            provider=name,
            calls=calls,
            ok=ok,
            cached=cached,
            failed=failed,
            avg_duration_ms=round(float(avg or 0), 1),
            cost_rub=(cost or 0) / 100,
        )
        for name, calls, ok, cached, failed, avg, cost in rows
    ]
    total_calls = sum(p.calls for p in providers)
    cached_calls = sum(p.cached for p in providers)
    return StatsOut(
        checks_total=await session.scalar(select(func.count()).select_from(Check)) or 0,
        cost_total_rub=sum(p.cost_rub for p in providers),
        cache_hit_rate=round(cached_calls / total_calls, 3) if total_calls else 0,
        providers=providers,
    )


health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health(request: Request, session: SessionDep) -> dict:
    db_ok = redis_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    try:
        await request.app.state.redis.ping()
    except Exception:
        redis_ok = False
    return {"status": "ok" if db_ok and redis_ok else "degraded", "db": db_ok, "redis": redis_ok}
