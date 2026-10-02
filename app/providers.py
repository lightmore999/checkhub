"""Клиенты внешних поставщиков данных: ретраи, кэш и circuit breaker."""

import asyncio
import time
from dataclasses import dataclass

import httpx

from app.cache import JsonCache
from app.config import Settings


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    title: str
    cost_kop: int  # цена одного успешного запроса


# Стоимость условная, но порядок цен как у реальных сервисов проверки контрагентов.
PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("registry", "Реестр юрлиц и ИП", 150),
    ProviderSpec("courts", "Арбитражные дела", 300),
    ProviderSpec("bankruptcy", "Сообщения о банкротстве", 100),
    ProviderSpec("debts", "Исполнительные производства", 200),
)


@dataclass
class ProviderResult:
    provider: str
    status: str  # ok | cached | failed | skipped
    data: dict | None
    attempts: int
    duration_ms: int
    cost_kop: int
    error: str | None = None


class CircuitBreaker:
    """После N неудач подряд перестаём дёргать поставщика на время cooldown.

    Так мы не тратим время пользователя и лимиты на заведомо лежащий сервис.
    Состояние хранится в памяти процесса — для нескольких реплик его стоит вынести в Redis.
    """

    def __init__(self, threshold: int, cooldown_seconds: float) -> None:
        self.threshold = threshold
        self.cooldown = cooldown_seconds
        self.failures = 0
        self.opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        # По истечении cooldown пропускаем пробный запрос (half-open).
        return time.monotonic() - self.opened_at >= self.cooldown

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


class ProviderClient:
    def __init__(
        self,
        spec: ProviderSpec,
        http: httpx.AsyncClient,
        cache: JsonCache,
        breaker: CircuitBreaker,
        settings: Settings,
    ) -> None:
        self.spec = spec
        self._http = http
        self._cache = cache
        self._breaker = breaker
        self._settings = settings

    async def fetch(self, inn: str) -> ProviderResult:
        started = time.perf_counter()

        def result(status: str, data: dict | None = None, attempts: int = 0, cost: int = 0,
                   error: str | None = None) -> ProviderResult:
            elapsed = int((time.perf_counter() - started) * 1000)
            return ProviderResult(self.spec.name, status, data, attempts, elapsed, cost, error)

        cache_key = f"provider:{self.spec.name}:{inn}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return result("cached", cached)

        if not self._breaker.allow():
            return result("skipped", error="circuit breaker open")

        max_attempts = self._settings.provider_retries + 1
        error = None
        attempt = 0
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._http.get(
                    f"/{self.spec.name}/{inn}", timeout=self._settings.provider_timeout_seconds
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                error = f"HTTP {exc.response.status_code}"
                if exc.response.status_code < 500:
                    break  # ошибка в запросе — повтор не поможет
            except httpx.TimeoutException:
                error = "timeout"
            except httpx.TransportError as exc:
                error = f"transport error: {type(exc).__name__}"
            else:
                self._breaker.record_success()
                await self._cache.set(cache_key, data)
                return result("ok", data, attempt, self.spec.cost_kop)

            if attempt < max_attempts:
                # Экспоненциальная задержка: 0.2с, 0.4с, 0.8с...
                await asyncio.sleep(self._settings.retry_backoff_seconds * 2 ** (attempt - 1))

        self._breaker.record_failure()
        return result("failed", attempts=attempt, error=error)
