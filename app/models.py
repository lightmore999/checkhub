import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class CheckStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Check(Base):
    """Одна проверка контрагента: итоговый отчёт и оценка риска."""

    __tablename__ = "checks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    inn: Mapped[str] = mapped_column(String(12), index=True)
    status: Mapped[str] = mapped_column(String(16), default=CheckStatus.PENDING)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    risk_level: Mapped[str | None] = mapped_column(String(16))
    risk_factors: Mapped[list[str] | None] = mapped_column(JSON)
    report: Mapped[dict | None] = mapped_column(JSON)
    # Деньги храним в копейках, чтобы не ловить ошибки округления float.
    total_cost_kop: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    calls: Mapped[list["ProviderCall"]] = relationship(
        back_populates="check", cascade="all, delete-orphan", order_by="ProviderCall.provider"
    )


class ProviderCall(Base):
    """Обращение к одному поставщику в рамках проверки — для аудита и статистики."""

    __tablename__ = "provider_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("checks.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(32), index=True)
    # ok — ответ получен, cached — взят из кэша, failed — не удалось, skipped — circuit breaker
    status: Mapped[str] = mapped_column(String(16))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_kop: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

    check: Mapped[Check] = relationship(back_populates="calls")
