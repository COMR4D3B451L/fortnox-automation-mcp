from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .security import require_approval


@dataclass(frozen=True)
class Intent:
    action: str
    resource: str
    parameters: dict[str, Any]
    requires_approval: bool
    rationale: str


class AccountingAgent:
    """Read-only accounting/domain analyst."""
    WRITE_PREFIXES = ("create", "update", "delete", "send", "book", "pay", "cancel")

    def analyze(self, request: str) -> Intent:
        text = request.lower().strip()
        if any(word in text for word in ("unpaid", "overdue", "invoice list", "invoices")) and not any(
                word in text for word in self.WRITE_PREFIXES):
            return Intent("list", "invoices", {}, False, "Read-only invoice query")
        if "customer" in text and any(word in text for word in ("list", "show", "find")):
            return Intent("list", "customers", {}, False, "Read-only customer query")
        return Intent("review", "unknown", {"request": request}, True,
                      "The request needs a domain review before any accounting side effect")


class IntegrationAgent:
    """Maps approved intents to the Fortnox wrapper; it cannot bypass approval."""
    def __init__(self, client):
        self.client = client

    def execute(self, intent: Intent, *, approval_token: str | None = None) -> Any:
        if intent.requires_approval:
            require_approval(approval_token)
        if intent.action == "list" and intent.resource == "invoices":
            return self.client.list_invoices(**intent.parameters)
        if intent.action == "list" and intent.resource == "customers":
            return self.client.list_customers(**intent.parameters)
        raise ValueError(f"Unsupported intent: {intent.action}/{intent.resource}")
