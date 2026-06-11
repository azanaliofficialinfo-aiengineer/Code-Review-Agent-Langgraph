"""Fix redundant indexes and add useful composite indexes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-11

Changes
-------
Drop (redundant or useless):
  ix_repositories_full_name      — duplicate of UNIQUE constraint btree
  ix_review_jobs_delivery_id     — duplicate of UNIQUE constraint btree
  ix_pull_requests_pr_number     — pr_number alone is meaningless across repos
  ix_review_findings_review_job_id — replaced by composite below

Add (useful for dashboard queries):
  ix_review_jobs_repo_created    — (repository_id, created_at)  per-repo time series
  ix_review_jobs_status_created  — (status, created_at)         queue-depth monitoring
  ix_review_findings_job_severity — (review_job_id, severity)   critical-findings per job
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL DROP INDEX IF EXISTS so the migration is idempotent —
    # safe to run against a fresh DB that never had these indexes.
    op.execute("DROP INDEX IF EXISTS ix_repositories_full_name")
    op.execute("DROP INDEX IF EXISTS ix_review_jobs_delivery_id")
    op.execute("DROP INDEX IF EXISTS ix_pull_requests_pr_number")
    op.execute("DROP INDEX IF EXISTS ix_review_findings_review_job_id")

    op.create_index(
        "ix_review_jobs_repo_created",
        "review_jobs",
        ["repository_id", "created_at"],
    )
    op.create_index(
        "ix_review_jobs_status_created",
        "review_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_review_findings_job_severity",
        "review_findings",
        ["review_job_id", "severity"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_findings_job_severity", table_name="review_findings")
    op.drop_index("ix_review_jobs_status_created", table_name="review_jobs")
    op.drop_index("ix_review_jobs_repo_created", table_name="review_jobs")

    # Restore the removed indexes for rollback parity with 0001.
    op.create_index("ix_review_findings_review_job_id", "review_findings", ["review_job_id"])
    op.create_index("ix_pull_requests_pr_number", "pull_requests", ["pr_number"])
    op.create_index("ix_review_jobs_delivery_id", "review_jobs", ["delivery_id"])
    op.create_index("ix_repositories_full_name", "repositories", ["full_name"])
