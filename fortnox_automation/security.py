"""Security helpers for approval-gated financial mutations."""
from __future__ import annotations

import hmac
import os


class ApprovalError(PermissionError):
    """Raised when a financial mutation lacks the configured approval token."""


def require_approval(token: str | None, *, configured: str | None = None) -> None:
    """Require a configured, out-of-band approval token.

    The token is never included in an exception. Comparison uses a constant-time
    function. No default token exists, so a missing configuration fails closed.
    """
    expected = configured if configured is not None else os.getenv("FORTNOX_APPROVAL_TOKEN")
    if not expected:
        raise ApprovalError("Financial writes are disabled: FORTNOX_APPROVAL_TOKEN is not configured")
    supplied = token or ""
    if not hmac.compare_digest(supplied, expected):
        raise ApprovalError("Explicit approval token required for this operation")
