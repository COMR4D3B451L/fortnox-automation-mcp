"""Fortnox OAuth authorization-code helpers."""
from __future__ import annotations

import os
import secrets
import urllib.parse


def authorization_url(*, client_id: str | None = None, redirect_uri: str, scopes: list[str], state: str | None = None) -> tuple[str, str]:
    client_id = client_id or os.environ["FORTNOX_CLIENT_ID"]
    state = state or secrets.token_urlsafe(32)
    query = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "state": state,
        "scope": " ".join(scopes),
        "redirect_uri": redirect_uri,
        "access_type": "offline",
    })
    return "https://apps.fortnox.se/oauth-v1/auth?" + query, state
