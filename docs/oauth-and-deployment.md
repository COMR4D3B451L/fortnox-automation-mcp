# OAuth and deployment requirements

This repository does not include a callback web service. A production integration must add one or use a separately reviewed service.

## Required callback behavior

- `GET /fortnox/authorize` creates a cryptographically random state and stores it server-side.
- `GET /fortnox/callback` validates state before exchanging the code.
- The registered redirect URI matches exactly, including scheme, host, path, and trailing slash.
- Access and refresh tokens are stored atomically with mode `600`, or in a secret manager.
- Refresh-token rotation replaces the stored refresh token.
- Callback responses are generic and do not render codes or tokens.
- Access logs do not record query strings containing OAuth codes or state.
- `/fortnox/status` reports only configured/connected booleans.

## Fortnox endpoints

- Authorization: `https://apps.fortnox.se/oauth-v1/auth`
- Token exchange and refresh: `https://apps.fortnox.se/oauth-v1/token`
- Revoke: `https://apps.fortnox.se/oauth-v1/revoke`
- API base: `https://api.fortnox.se`

## Deployment checks

1. Use HTTPS.
2. Route only the callback path to the callback service.
3. Keep token storage outside the repository.
4. Verify a safe `companyinformation` read before any write.
5. Test invalid and missing state.
6. Confirm no secret appears in service, proxy, CI, or audit logs.
7. Keep financial writes disabled until exact-operation approval is implemented.
