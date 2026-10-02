import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api import health_router, router
from app.config import Settings
from app.db import Base, make_engine, make_sessionmaker
from app.mock_providers import router as mock_router

HttpClientFactory = Callable[[FastAPI], httpx.AsyncClient]


def create_app(
    settings: Settings | None = None,
    *,
    redis: Redis | None = None,
    http_client_factory: HttpClientFactory | None = None,
) -> FastAPI:
    """Фабрика приложения. Зависимости можно подменить — так устроены тесты."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url)
        if settings.auto_create_tables:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        app.state.settings = settings
        app.state.sessionmaker = make_sessionmaker(engine)
        app.state.redis = redis or Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.http = (
            http_client_factory(app)
            if http_client_factory
            else httpx.AsyncClient(base_url=settings.providers_base_url)
        )
        app.state.breakers = {}
        try:
            yield
        finally:
            await app.state.http.aclose()
            await app.state.redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="CheckHub",
        description="Проверка контрагентов по ИНН: один отчёт из нескольких платных источников.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    app.include_router(health_router)
    app.include_router(mock_router)
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
