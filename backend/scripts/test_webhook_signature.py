#!/usr/bin/env python3
"""
Generate a valid X-Hub-Signature-256 and print a ready-to-paste curl command
for testing the local webhook endpoint.

Usage
-----
# With a specific secret:
GITHUB_WEBHOOK_SECRET=my-secret python scripts/test_webhook_signature.py

# Falls back to "test-secret" if the env var is not set.
python scripts/test_webhook_signature.py

# Optionally override the PR action (default: opened):
WEBHOOK_ACTION=synchronize python scripts/test_webhook_signature.py
"""
import hashlib
import hmac
import json
import os
import sys
import time

# ── Sample payload ─────────────────────────────────────────────────────────────
# Mirrors the minimal structure that the webhook endpoint reads.
def build_payload(action: str = "opened") -> dict:
    return {
        "action": action,
        "number": 42,
        "pull_request": {
            "number": 42,
            "title": "chore: add test feature",
            "state": "open",
            "head": {"sha": "abc123def456", "ref": "feat/test-branch"},
            "base": {"sha": "000000000000", "ref": "main"},
            "user": {"login": "testuser"},
            "additions": 15,
            "deletions": 3,
            "changed_files": 2,
        },
        "repository": {
            "full_name": "testorg/testrepo",
            "name": "testrepo",
            "private": False,
        },
        "sender": {"login": "testuser"},
    }


def sign_payload(payload_bytes: bytes, secret: str) -> str:
    mac = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    )
    return f"sha256={mac.hexdigest()}"


def main() -> None:
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        print("⚠️  GITHUB_WEBHOOK_SECRET not set — using 'test-secret'.")
        print("   Make sure backend/.env also has: GITHUB_WEBHOOK_SECRET=test-secret\n")
        secret = "test-secret"

    action = os.environ.get("WEBHOOK_ACTION", "opened")
    valid_actions = {"opened", "synchronize", "reopened"}
    if action not in valid_actions:
        print(f"ERROR: WEBHOOK_ACTION must be one of {valid_actions}, got '{action}'", file=sys.stderr)
        sys.exit(1)

    payload = build_payload(action)
    # Use compact JSON (no extra spaces) — matches how GitHub serialises payloads.
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = sign_payload(payload_bytes, secret)
    delivery_id = f"test-delivery-{int(time.time())}"
    payload_str = payload_bytes.decode("utf-8")

    print("=" * 60)
    print(f"  Event  : pull_request")
    print(f"  Action : {action}")
    print(f"  Secret : {'*' * len(secret)}  (masked)")
    print(f"  Sig    : {signature}")
    print("=" * 60)
    print()
    print("-- curl command ------------------------------------------")
    print(
        f"curl -s -X POST http://localhost:8000/webhooks/github \\\n"
        f'  -H "Content-Type: application/json" \\\n'
        f'  -H "X-GitHub-Event: pull_request" \\\n'
        f'  -H "X-GitHub-Delivery: {delivery_id}" \\\n'
        f'  -H "X-Hub-Signature-256: {signature}" \\\n'
        f"  -d '{payload_str}' | python -m json.tool"
    )
    print()
    print("-- expected response --------------------------------------")
    print(json.dumps({
        "status": "accepted",
        "event": "pull_request",
        "action": action,
        "delivery_id": delivery_id,
        "repository": "testorg/testrepo",
        "pull_request": 42,
    }, indent=2))


if __name__ == "__main__":
    main()
