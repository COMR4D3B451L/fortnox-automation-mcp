from __future__ import annotations

from .orchestrator import Orchestrator
from .security import require_approval


class ContactAgent:
    """User-facing facade intended for the Fortnox Automation Hermes thread."""
    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator

    def handle(self, request: str, *, approval_token: str | None = None) -> str:
        intent = self.orchestrator.plan(request)
        if intent.action == "review":
            return ("I need to clarify this before touching Fortnox. "
                    "Financial writes require a specific proposed operation and your explicit approval.")
        if intent.requires_approval:
            try:
                require_approval(approval_token)
            except PermissionError:
                return "This operation requires explicit approval before execution."
        result = self.orchestrator.run(request, approval_token=approval_token)
        return str(result)
