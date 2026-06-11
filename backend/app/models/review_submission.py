import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReviewSubmission(Base):
    __tablename__ = "review_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    review_job_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("review_jobs.id"),
        nullable=False,
    )
    event: Mapped[str] = mapped_column(String(50), nullable=False)
    commit_id: Mapped[str] = mapped_column(String(40), nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    comments_json: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    dry_run: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    submitted_to_github: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    github_review_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        UniqueConstraint("review_job_id", name="uq_review_submissions_review_job_id"),
    )
