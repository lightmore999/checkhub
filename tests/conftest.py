from collections.abc import AsyncIterator, Callable

import httpx
import pytest
from fakeredis import FakeAsyncRedis

from app.config import Settings
from app.main import create_app

API_KEY = "test-key"
ClientFactory = Callable[..., AsyncIterator[httpx.AsyncClient]]


@pytest.fixture
def make_client(tmp_path) -> ClientFactory:
    """Поднимает приложение с SQLite и fakeredis. Поставщики-заглушки вызываются через ASGI."""

    async def factory(**overrides) -> AsyncIterator[httpx.AsyncClient]:
        defaults = {
            "database_url": f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
            "api_keys": [API_KEY],
            "auto_create_tables": True,
            "mock_latency_seconds": 0,
            "mock_failure_rate": 0,
            "retry_backoff_seconds": 0,
            "rate_limit_per_minute": 1000,
        }
        settings = Settings(**(defaults | overrides))
        app = create_app(
            settings,
            redis=FakeAsyncRedis(decode_responses=True),
            http_client_factory=lambda a: httpx.AsyncClient(
                transport=httpx.ASGITransport(app=a), base_url="http://test/mock"
            ),
        )
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test", headers={"X-API-Key": API_KEY}
            ) as client:
                yield client

    return factory


@pytest.fixture
async def client(make_client) -> AsyncIterator[httpx.AsyncClient]:
    async for c in make_client():
        yield c
