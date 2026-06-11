"""create review persistence tables

Revision ID: 0001
Revises:
Create Date: 2026-06-10

Creates the full Phase 7 PostgreSQL schema:
  repositories, pull_requests, review_jobs, review_findings,
  review_summaries, review_submissions
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── repositories ──────────────────────────────────────────────────────────
    op.create_table(
        "repositories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("github_repo_id", sa.Integer(), nullable=True),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(511), nullable=False),
        sa.Column("installation_id", sa.Integer(), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repositories")),
        sa.UniqueConstraint("full_name", name=op.f("uq_repositories_full_name")),
    )
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"])

    # ── pull_requests ─────────────────────────────────────────────────────────
    op.create_table(
        "pull_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(1023), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("base_branch", sa.String(255), nullable=True),
        sa.Column("head_branch", sa.String(255), nullable=True),
        sa.Column("base_sha", sa.String(40), nullable=True),
        sa.Column("head_sha", sa.String(40), nullable=True),
        sa.Column("html_url", sa.String(2048), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_pull_requests_repository_id_repositories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pull_requests")),
        sa.UniqueConstraint(
            "repository_id", "pr_number", name="uq_pull_requests_repo_pr"
        ),
    )
    op.create_index("ix_pull_requests_repository_id", "pull_requests", ["repository_id"])
    op.create_index("ix_pull_requests_pr_number", "pull_requests", ["pr_number"])

    # ── review_jobs ───────────────────────────────────────────────────────────
    op.create_table(
        "review_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_id", sa.String(255), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pull_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("event_action", sa.String(50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name=op.f("fk_review_jobs_repository_id_repositories"),
        ),
        sa.ForeignKeyConstraint(
            ["pull_request_id"],
            ["pull_requests.id"],
            name=op.f("fk_review_jobs_pull_request_id_pull_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_jobs")),
        sa.UniqueConstraint("delivery_id", name=op.f("uq_review_jobs_delivery_id")),
    )
    op.create_index("ix_review_jobs_delivery_id", "review_jobs", ["delivery_id"])
    op.create_index("ix_review_jobs_status", "review_jobs", ["status"])
    op.create_index("ix_review_jobs_created_at", "review_jobs", ["created_at"])
    op.create_index("ix_review_jobs_repository_id", "review_jobs", ["repository_id"])
    op.create_index(
        "ix_review_jobs_pull_request_id", "review_jobs", ["pull_request_id"]
    )

    # ── review_findings ───────────────────────────────────────────────────────
    op.create_table(
        "review_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("suggestion", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "should_comment",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["review_job_id"],
            ["review_jobs.id"],
            name=op.f("fk_review_findings_review_job_id_review_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_findings")),
    )
    op.create_index(
        "ix_review_findings_review_job_id", "review_findings", ["review_job_id"]
    )
    op.create_index("ix_review_findings_severity", "review_findings", ["severity"])

    # ── review_summaries ──────────────────────────────────────────────────────
    op.create_table(
        "review_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verdict", sa.String(50), nullable=False),
        sa.Column("risk_level", sa.String(50), nullable=False),
        sa.Column("severity_score", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.String(), nullable=False),
        sa.Column(
            "total_findings", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "critical_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "high_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "medium_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "low_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["review_job_id"],
            ["review_jobs.id"],
            name=op.f("fk_review_summaries_review_job_id_review_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_summaries")),
        sa.UniqueConstraint(
            "review_job_id", name="uq_review_summaries_review_job_id"
        ),
    )
    op.create_index(
        "ix_review_summaries_review_job_id", "review_summaries", ["review_job_id"]
    )

    # ── review_submissions ────────────────────────────────────────────────────
    op.create_table(
        "review_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("commit_id", sa.String(40), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column(
            "comments_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "submitted_to_github",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("github_review_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["review_job_id"],
            ["review_jobs.id"],
            name=op.f("fk_review_submissions_review_job_id_review_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_submissions")),
        sa.UniqueConstraint(
            "review_job_id", name="uq_review_submissions_review_job_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("review_submissions")
    op.drop_table("review_summaries")
    op.drop_table("review_findings")
    op.drop_table("review_jobs")
    op.drop_table("pull_requests")
    op.drop_table("repositories")
