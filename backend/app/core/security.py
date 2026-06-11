import hashlib
import hmac


def verify_github_signature(
    payload_body: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """
    Validate a GitHub webhook HMAC-SHA256 signature.

    Fails closed on any missing or malformed input — a misconfigured secret
    must never silently allow requests through.

    Args:
        payload_body:     Raw (un-decoded) request body bytes.
        signature_header: Value of the X-Hub-Signature-256 header.
        secret:           GITHUB_WEBHOOK_SECRET from settings.

    Returns:
        True only when the computed digest matches the header exactly.
    """
    # Fail closed: missing secret means misconfigured environment.
    if not secret or not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison prevents timing-based signature oracle attacks.
    return hmac.compare_digest(expected, signature_header)
