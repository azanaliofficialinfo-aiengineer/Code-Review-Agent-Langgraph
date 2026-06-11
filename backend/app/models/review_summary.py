import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReviewSummary(Base):
    __tablename__ = "review_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_job_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("review_jobs.id"),
        nullable=False,
    )
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    severity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_text: Mapped[str] = mapped_column(String, nullable=False)
    total_findings: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    critical_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    high_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    medium_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    low_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        UniqueConstraint("review_job_id", name="uq_review_summaries_review_job_id"),
        Index("ix_review_summaries_review_job_id", "review_job_id"),
    )
