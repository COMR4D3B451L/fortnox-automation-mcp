"""Minimal environment-file loader for local service processes."""
from __future__ import annotations

import os
from pathlib import Path


def load_project_env(path: str | None = None) -> None:
    p = Path(path or os.getenv("FORTNOX_ENV_FILE", ".env"))
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value
