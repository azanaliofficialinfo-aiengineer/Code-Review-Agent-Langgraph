import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReviewJob(Base):
    __tablename__ = "review_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    delivery_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    repository_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("repositories.id"), nullable=False
    )
    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        # ix_review_jobs_delivery_id removed — unique=True on delivery_id already
        # creates a BTree index via the UNIQUE constraint.
        Index("ix_review_jobs_status", "status"),
        Index("ix_review_jobs_created_at", "created_at"),
        Index("ix_review_jobs_repository_id", "repository_id"),
        Index("ix_review_jobs_pull_request_id", "pull_request_id"),
        # Composite indexes for dashboard queries (added in migration 0002).
        Index("ix_review_jobs_repo_created", "repository_id", "created_at"),
        Index("ix_review_jobs_status_created", "status", "created_at"),
    )
