from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReviewFinding(BaseModel):
    file_path: str
    line: int | None = None
    severity: Literal["low", "medium", "high", "critical"]
    category: Literal[
        "security",
        "logic_bug",
        "performance",
        "maintainability",
        "test_coverage",
        "style",
    ]
    title: str
    description: str
    suggestion: str
    confidence: float = Field(ge=0.0, le=1.0)
    should_comment: bool = False

    @model_validator(mode="after")
    def enforce_should_comment(self) -> "ReviewFinding":
        """
        Enforce the comment-worthy rule centrally so no caller needs to replicate it.

        A finding should be commented iff:
          - confidence meets the configured threshold
          - severity is actionable (medium / high / critical)
          - category is not pure style (style findings are noisy; leave them out)
        """
        # Import here to avoid module-level circular at import time.
        from app.core.config import settings  # noqa: PLC0415

        self.should_comment = (
            self.confidence >= settings.AI_MIN_CONFIDENCE
            and self.severity in ("medium", "high", "critical")
            and self.category != "style"
        )
        return self


class ReviewSummary(BaseModel):
    verdict: Literal["approve", "comment", "request_changes"]
    risk_level: Literal["low", "medium", "high", "critical"]
    severity_score: int = Field(ge=0, le=100)
    summary_text: str
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


class ReviewResult(BaseModel):
    delivery_id: str
    repository: str
    pr_number: int
    provider: str
    model: str
    findings: list[ReviewFinding] = Field(default_factory=list)
    summary: ReviewSummary
    reviewed_files: list[str] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
