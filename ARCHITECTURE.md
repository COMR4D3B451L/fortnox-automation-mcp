# Architecture

## Components

- `client.py` — injectable HTTP transport, Fortnox requests, pagination, refresh, and error handling.
- `oauth.py` — authorization URL construction only. It does not store state or exchange codes.
- `receipts.py` — receipt validation, balanced voucher preview, and approval-gated booking.
- `security.py` — fail-closed constant-time approval-token check.
- `mcp_server.py` — stdio MCP adapter. It exposes reads and previews by default.
- `agents.py`, `orchestrator.py`, `contact.py` — planning and routing layers.
- `audit.py` — local JSONL audit sink. Keep the path outside the public checkout when it contains business data.

## Trust boundaries

1. The MCP host is an untrusted caller for financial mutations.
2. Environment files and secret managers are trusted configuration sources.
3. The Fortnox API is an external service. Preserve its status and error envelope.
4. The local audit file may contain business data. It must not be committed or sent to public logs.

## Write path

A write requires all of these conditions:

1. The write feature flag is enabled before tool discovery.
2. The caller supplies the configured approval token.
3. The operation-specific workflow validates its payload.
4. The caller has separately reviewed the exact company, date, accounts, VAT, amount, and external effect.
5. The result is checked after the API call.

Authentication does not equal authorization. An OAuth token is not an approval to book, send, pay, cancel, or delete.

## Deliberate limitations

- No web OAuth callback server is included.
- No persistent state store for OAuth `state` is included.
- No accounting classification engine is included.
- No automatic bank reconciliation is included.
- No automatic retries are used for mutations.
- No production deployment configuration is included.
