"""
ORM model registry.

Importing this package registers all models with SQLAlchemy's metadata so
Alembic can discover them for autogenerate and the engine can create tables.
"""
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review_finding import ReviewFinding
from app.models.review_job import ReviewJob
from app.models.review_submission import ReviewSubmission
from app.models.review_summary import ReviewSummary

__all__ = [
    "PullRequest",
    "Repository",
    "ReviewFinding",
    "ReviewJob",
    "ReviewSubmission",
    "ReviewSummary",
]
