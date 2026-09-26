# Fortnox Automation and MCP

A small, dependency-free Python integration for Fortnox Open API and Model Context Protocol (MCP) clients.

This repository is designed for public review. It contains no Fortnox credentials, access tokens, refresh tokens, customer data, accounting exports, or production audit logs.

## What it provides

- A typed, injectable Fortnox HTTP client.
- OAuth authorization URL helpers.
- Bounded read tools for invoices and customers.
- Receipt validation and balanced voucher previews.
- Optional write tools behind two independent gates:
  - `FORTNOX_ENABLE_WRITES=1`.
  - A secret `FORTNOX_APPROVAL_TOKEN` that matches the per-call approval token.
- Safe-read and preview tools through a stdio MCP server.
- Pagination, bounded `max_items`, refresh-token rotation, retry limits, and structured Fortnox errors.
- Offline tests with fake transports. Tests never call Fortnox.

## Important safety boundary

This is an integration skeleton, not an accounting authority. It does not decide Swedish tax treatment, prove a business purpose, or replace an accountant.

Financial mutations require a separate review and explicit approval of the exact proposed operation. Do not enable write tools until the deployment has secure secret storage, an audit policy, source-document handling, and a tested approval workflow.

Fortnox OAuth scopes can grant write capability. Treat every granted scope as write-capable even when the application currently exposes only reads.

## Requirements

- Python 3.11 or newer.
- No runtime dependency outside the Python standard library.
- Fortnox developer application credentials for live OAuth/API use.
- An MCP-capable host, such as Hermes, for MCP use.

## Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
cp .env.example .env
python -m unittest discover -s tests -v
```

Keep `.env` outside version control. Use file mode `600` for local secret files:

```bash
chmod 600 .env
```

For a real deployment, prefer a secret manager or an environment file outside the checkout.

## Configuration

The public template contains names only. Set these out of band:

```text
FORTNOX_CLIENT_ID
FORTNOX_CLIENT_SECRET
FORTNOX_ACCESS_TOKEN
FORTNOX_REFRESH_TOKEN
FORTNOX_COMPANY_ID
FORTNOX_BASE_URL=https://api.fortnox.se
FORTNOX_ENV_FILE=./.env
FORTNOX_AUDIT_LOG=./data/audit.jsonl
FORTNOX_ENABLE_WRITES=0
FORTNOX_APPROVAL_TOKEN=<long random secret, only when writes are deliberately enabled>
```

The default is fail-closed: writes are not exposed unless `FORTNOX_ENABLE_WRITES=1`, and every write still requires the configured approval token. There is no built-in token such as `APPROVED`.

## CLI

The CLI can create a plan without contacting Fortnox:

```bash
PYTHONPATH=. python -m fortnox_automation.cli plan "Show unpaid customer invoices"
```

## MCP server

The server uses newline-delimited JSON-RPC over stdin/stdout:

```bash
PYTHONPATH=. python -m fortnox_automation.mcp_server
```

Register it with an MCP host using an absolute path and an environment file managed by that host. Do not put credentials in the MCP registration JSON. Example shape:

```json
{
  "mcpServers": {
    "fortnox": {
      "command": "python3",
      "args": ["-m", "fortnox_automation.mcp_server"],
      "cwd": "/path/to/fortnox-automation",
      "env": {
        "FORTNOX_ENV_FILE": "/secure/path/fortnox.env"
      }
    }
  }
}
```

Start a new MCP client session after changing tool schemas or environment configuration.

### Read tools

Available by default:

- `fortnox_list_invoices`
- `fortnox_list_customers`
- `fortnox_preview_receipt`

List operations require an explicit `max_items` bound. The preview tool validates accounting arithmetic but does not write.

### Write tools

Write tools are hidden unless `FORTNOX_ENABLE_WRITES=1`. When exposed, each write call requires an approval token supplied by the caller and checked with a constant-time comparison. The repository does not provide that secret.

Do not use a write call as a connectivity test. Verify a safe read first, present a complete preview, obtain approval, then execute one bounded operation and verify its Fortnox identifier.

## OAuth

This repository contains only authorization URL construction. A production deployment must add a server-side callback that:

1. Generates and stores a random `state`.
2. Validates `state` with constant-time comparison.
3. Exchanges the code server-side over HTTPS.
4. Stores access and refresh tokens atomically with restrictive permissions.
5. Handles refresh-token rotation.
6. Never returns tokens, codes, or secrets in a browser response or log.

Use the exact redirect URI registered in the Fortnox developer portal. See [`docs/oauth-and-deployment.md`](docs/oauth-and-deployment.md).

## API behavior

- Safe reads may retry on `429` and server errors with bounded backoff.
- Mutating requests are not automatically retried.
- Refresh-token rotation is persisted only to the configured local secret file.
- List operations support pagination and a caller-supplied maximum item count.
- Fortnox error information is preserved in `FortnoxAPIError`.
- Attachment uploads are limited to 50 MiB and are not automatically retried.

## Repository security

Before every public push:

```bash
python3 scripts/scan_public.py
python3 -m unittest discover -s tests -v
```

The scanner checks the working tree for private keys, common credential formats, token assignments, and ignored sensitive files. It is a safety net, not a replacement for secret management or code review.

Never commit:

- `.env` or secret files.
- Tokens, client secrets, passwords, private keys, or cookies.
- Fortnox customer, invoice, voucher, bank, or audit exports.
- Local previews, attachments, spreadsheets, or generated reports.
- Production MCP configuration containing environment values.

If a secret was ever committed, rotate it first. Removing it from the latest commit is not enough because Git history may retain it.

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — components and trust boundaries.
- [`SECURITY.md`](SECURITY.md) — threat model and reporting process.
- [`docs/mcp-setup.md`](docs/mcp-setup.md) — safe MCP setup.
- [`docs/oauth-and-deployment.md`](docs/oauth-and-deployment.md) — OAuth and secret storage requirements.
- [`docs/accounting-safety.md`](docs/accounting-safety.md) — approval and accounting boundaries.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — public contribution rules.

## License

MIT. See [`LICENSE`](LICENSE).
