from __future__ import annotations

from .agents import AccountingAgent, IntegrationAgent
from .audit import AuditLog


class Orchestrator:
    """Coordinates the specialist agents and enforces the approval boundary."""
    def __init__(self, client, audit: AuditLog | None = None):
        self.accounting = AccountingAgent()
        self.integration = IntegrationAgent(client)
        self.audit = audit or AuditLog()

    def plan(self, request: str):
        intent = self.accounting.analyze(request)
        self.audit.record(event="plan", request=request, intent=intent, status="ok")
        return intent

    def run(self, request: str, *, approval_token: str | None = None):
        intent = self.plan(request)
        try:
            result = self.integration.execute(intent, approval_token=approval_token)
        except Exception as exc:
            self.audit.record(event="execute", request=request, intent=intent,
                              status="blocked" if isinstance(exc, PermissionError) else "error",
                              detail=str(exc))
            raise
        self.audit.record(event="execute", request=request, intent=intent, status="ok")
        return result
