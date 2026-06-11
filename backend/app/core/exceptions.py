"""
Typed domain exceptions used across the application.

Keeping exceptions here avoids circular imports between service modules
and gives callers a single import path for error handling.
"""


class GitHubAPIError(Exception):
    """GitHub REST API returned a non-2xx response."""

    def __init__(self, status_code: int, message: str, url: str = "") -> None:
        self.status_code = status_code
        self.message = message
        self.url = url
        detail = f"GitHub API {status_code}: {message}"
        if url:
            detail += f" [{url}]"
        super().__init__(detail)


class GitHubAuthError(Exception):
    """Failed to generate a GitHub App JWT or exchange it for an installation token."""


class DeliveryNotFoundError(Exception):
    """Webhook delivery ID was not found in Redis (expired or never stored)."""

    def __init__(self, delivery_id: str) -> None:
        self.delivery_id = delivery_id
        super().__init__(f"No webhook payload found for delivery_id '{delivery_id}'")


class MissingInstallationError(Exception):
    """Webhook payload did not contain an installation.id field."""

    def __init__(self, delivery_id: str) -> None:
        self.delivery_id = delivery_id
        super().__init__(
            f"Webhook payload for '{delivery_id}' is missing installation.id. "
            "Ensure the event was sent by a GitHub App installation, not a raw repo webhook."
        )


class AIProviderConfigError(Exception):
    """AI provider is misconfigured — missing key, unsupported provider name, model not found."""


class AIReviewError(Exception):
    """The AI review pipeline encountered a fatal error after all retries were exhausted."""
