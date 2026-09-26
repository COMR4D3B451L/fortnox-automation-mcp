#!/usr/bin/env python3
"""Fail when likely secrets or ignored sensitive files enter a public snapshot."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "bearer token": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~-]{20,}"),
    "credential assignment": re.compile(
        r"(?i)\b(?:client_secret|access_token|refresh_token|api_key|password)\s*[:=]\s*['\"]([A-Za-z0-9_./+=-]{16,})['\"]"
    ),
}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".ini", ".json", ".yaml", ".yml", ".txt", ".example"}
SKIP_NAMES = {"scan_public.py"}

def tracked_files() -> list[Path]:
    try:
        output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
        return [ROOT / line for line in output.splitlines() if line]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file()]

def main() -> int:
    failures: list[str] = []
    for path in tracked_files():
        if path.name in SKIP_NAMES or any(part in {".git", "__pycache__", ".venv"} for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".env", ".env.example", ".gitignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path.relative_to(ROOT)}: possible {label}")
    if failures:
        print("Public snapshot scan failed:", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Public snapshot scan passed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
