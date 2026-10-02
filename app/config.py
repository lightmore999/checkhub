from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения. Читаются из переменных окружения с префиксом CHECKHUB_."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CHECKHUB_")

    database_url: str = "postgresql+asyncpg://checkhub:checkhub@localhost:5432/checkhub"
    redis_url: str = "redis://localhost:6379/0"
    # Список ключей в виде JSON: CHECKHUB_API_KEYS='["key1", "key2"]'
    api_keys: list[str] = ["dev-key"]
    rate_limit_per_minute: int = 30

    # Внешние поставщики данных. По умолчанию — встроенные заглушки (/mock).
    providers_base_url: str = "http://localhost:8000/mock"
    provider_timeout_seconds: float = 3.0
    provider_retries: int = 2
    retry_backoff_seconds: float = 0.2
    breaker_threshold: int = 3
    breaker_cooldown_seconds: float = 30.0
    cache_ttl_seconds: int = 3600

    # Поведение заглушек поставщиков.
    mock_latency_seconds: float = 0.4
    mock_failure_rate: float = 0.15

    # Для локального запуска без миграций и для тестов.
    auto_create_tables: bool = False
