"""
Provider abstraction layer for AI code review.

Adding a new provider (e.g. NVIDIA, Anthropic) requires only:
  1. A new class that extends AIReviewProvider.
  2. A new branch in get_ai_provider().

No other files need to change.
"""
from abc import ABC, abstractmethod

from app.schemas.pr_context import PRContext
from app.schemas.review_result import ReviewResult


class AIReviewProvider(ABC):
    @abstractmethod
    async def review_pr(self, pr_context: PRContext) -> ReviewResult:
        """Run AI review on the given PR context and return structured findings."""


def get_ai_provider() -> AIReviewProvider:
    """
    Factory that returns the configured AI provider instance.

    Reads AI_PROVIDER from settings at call time so tests can override it.
    Imports are deferred to avoid loading heavy SDK dependencies at startup
    when the provider is not yet configured.

    Raises:
        AIProviderConfigError: provider name is not supported.
    """
    from app.core.config import settings  # noqa: PLC0415
    from app.core.exceptions import AIProviderConfigError  # noqa: PLC0415

    provider = settings.AI_PROVIDER

    if provider == "groq":
        from app.services.groq_reviewer import GroqReviewProvider  # noqa: PLC0415
        return GroqReviewProvider()

    # Extend here for "nvidia" and "anthropic" in future phases.
    raise AIProviderConfigError(
        f"Unsupported AI_PROVIDER: {provider!r}. "
        f"Currently supported: 'groq'."
    )
