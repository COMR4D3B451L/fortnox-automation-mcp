from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: str | None = None):
        self.path = Path(path or os.getenv("FORTNOX_AUDIT_LOG", "./data/audit.jsonl"))

    def record(self, *, event: str, request: str, intent: Any, status: str, detail: Any = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event,
               "request": request, "intent": getattr(intent, "__dict__", intent),
               "status": status, "detail": detail}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
