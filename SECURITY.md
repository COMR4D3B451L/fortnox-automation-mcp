# Security policy

## Supported versions

Only the latest published revision is supported for security fixes.

## Security design

- Secrets are read from environment variables or a secret file outside public source control.
- Write tools are disabled by default.
- Write approval uses `FORTNOX_APPROVAL_TOKEN`; no default token exists.
- Approval comparison uses a constant-time function.
- Read retries are bounded. Mutations are not automatically retried.
- List tools require a maximum-item bound.
- API errors are preserved without logging Authorization headers.
- Runtime reports, audit logs, accounting documents, and bank exports are ignored by Git.

## Do not report secrets in an issue

Do not include client IDs with secrets, access tokens, refresh tokens, approval tokens, passwords, private keys, OAuth codes, customer data, invoice data, or bank data in a public issue or pull request.

If a credential may have been exposed:

1. Revoke or rotate it immediately in Fortnox or the relevant provider.
2. Remove local copies from logs and shared folders.
3. Then report the code issue privately to the repository maintainer.

## Scope

This project is a local integration library. It is not a hosted service and does not promise protection from a compromised host, compromised MCP client, malicious local user, or misconfigured secret manager.

Before production use, add a server-side OAuth callback, encrypted or managed token storage, append-only audit controls, deployment isolation, and an independent accounting review.
