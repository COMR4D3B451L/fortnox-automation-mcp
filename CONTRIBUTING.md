# Contributing

## Before a pull request

```bash
python3 scripts/scan_public.py
python3 -m unittest discover -s tests -v
```

Do not add live API calls to tests. Use fake transports and synthetic payloads.

## Public-repository rules

- Never commit credentials, tokens, private keys, or local environment files.
- Never commit customer, invoice, voucher, bank, or audit data.
- Keep write tools disabled by default.
- Add tests for validation and approval gates.
- Do not automatically retry a mutation.
- Document units, Fortnox endpoint behavior, and side effects.
- Keep accounting classifications as suggestions unless confirmed by an accountant.

## Changes to MCP tools

Document whether a tool is read-only, preview-only, or mutating. Mutating tools must require exact-operation approval and must not use a hard-coded token.
