import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.inn import is_valid_inn


class CheckCreate(BaseModel):
    inn: str = Field(examples=["7707083893"])

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, value: str) -> str:
        value = value.strip()
        if not is_valid_inn(value):
            raise ValueError("Некорректный ИНН: нужно 10 или 12 цифр с верной контрольной суммой")
        return value


class ProviderCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    status: str
    attempts: int
    duration_ms: int
    cost_kop: int
    error: str | None


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inn: str
    status: str
    risk_score: int | None
    risk_level: str | None
    risk_factors: list[str] | None
    report: dict | None
    total_cost_kop: int
    created_at: datetime
    finished_at: datetime | None
    calls: list[ProviderCallOut]

    @computed_field
    @property
    def total_cost_rub(self) -> float:
        return self.total_cost_kop / 100


class ProviderStats(BaseModel):
    provider: str
    calls: int
    ok: int
    cached: int
    failed: int
    avg_duration_ms: float
    cost_rub: float


class StatsOut(BaseModel):
    checks_total: int
    cost_total_rub: float
    cache_hit_rate: float
    providers: list[ProviderStats]
