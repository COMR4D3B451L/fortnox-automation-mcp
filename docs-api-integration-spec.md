# Fortnox Python Wrapper — API Integration Layer Specification

Research date: 2026-07-19
Scope: design-only implementation specification for a production-quality typed Python wrapper; no credentials used; no implementation code included.

## Official sources used

- Developer home: https://www.fortnox.se/developer
- Authorization overview: https://www.fortnox.se/developer/authorization
- Authorization code request: https://www.fortnox.se/developer/authorization/get-authorization-code
- Access token exchange: https://www.fortnox.se/developer/authorization/get-access-token
- Client credentials token flow: https://www.fortnox.se/developer/authorization/get-access-token-using-client-credentials
- Refresh token: https://www.fortnox.se/developer/authorization/get-refresh-token
- Make API request: https://www.fortnox.se/developer/authorization/make-request
- Revoke refresh token: https://www.fortnox.se/developer/authorization/revoke-access-token
- Rate limits: https://www.fortnox.se/developer/guides-and-good-to-know/rate-limits-for-fortnox-api
- Parameters, filtering, sorting, limit/offset, pagination: https://www.fortnox.se/developer/guides-and-good-to-know/parameters
- Responses: https://www.fortnox.se/developer/guides-and-good-to-know/responses
- Errors: https://www.fortnox.se/developer/guides-and-good-to-know/errors
- Header fields: https://www.fortnox.se/developer/guides-and-good-to-know/header-fields
- Scopes: https://www.fortnox.se/developer/guides-and-good-to-know/scopes
- OpenAPI/Redoc API reference: https://apps.fortnox.se/apidocs

## Design goals

1. Maintainable typed Python client usable without credentials in unit tests and connectable later to Hermes tools/agents.
2. Separate concerns: auth/token lifecycle, HTTP transport, rate limiting/retries, resource clients, typed models, and test fixtures.
3. No hard dependency on live Fortnox accounts for normal CI.
4. Preserve raw Fortnox details where needed: HTTP status, error code/message, response envelope, pagination metadata, and tenant context.
5. Avoid hiding Fortnox-specific behaviors: mixed `/3/...` and `/api/...` paths, envelope-style JSON, scope/license requirements, service-account client credentials flow, and per-token rate limits.

## Fortnox API basics

- Base API server in OpenAPI: `https://api.fortnox.se`.
- Main legacy/business endpoints are under `/3/...`.
- Newer/module endpoints appear under `/api/...`, for example file attachments, warehouse, time reporting, and integration partner/developer endpoints.
- API requests use an `Authorization: Bearer <access token>` header; Fortnox’s header docs show `Accept: application/json` and `Content-Type: application/json` for JSON requests. File/archive/inbox uploads use `multipart/form-data` with `Accept: application/json`.
- Fortnox says the API is generally REST/resource-oriented and uses HTTP status codes and verbs. The API documentation examples are JSON, although the docs mention XML support.

## Authentication model

### Authorization Code Flow

Fortnox authorizes customer account access with OAuth2 Authorization Code Flow.

Authorization endpoint:

- `GET https://apps.fortnox.se/oauth-v1/auth`

Required query parameters:

- `client_id`: public app identifier.
- `response_type=code`.
- `state`: returned unmodified; must be used by wrapper/app integrations for CSRF protection and request correlation.
- `scope`: URL-encoded, space-delimited, case-sensitive scope list.

Optional query parameters:

- `redirect_uri`: URL-encoded URI; must match Developer Portal redirect URI. If omitted, defaults to registered redirect URI.
- `access_type=offline`: allows refresh tokens when user is not present.
- `account_type=service`: requests a service account. Service account must be enabled in Developer Portal, only customer system administrators can authorize it, it is not tied to a specific user, and Fortnox allows only one service account per `client_id` and customer.

Successful redirect shape:

- `https://your-redirect.example/callback?code=<Authorization-Code>&state=<state>`

Token endpoint for authorization code exchange:

- `POST https://apps.fortnox.se/oauth-v1/token`
- Header: `Authorization: Basic <base64(client_id:client_secret)>`
- Header: `Content-Type: application/x-www-form-urlencoded`
- Body: `grant_type=authorization_code`, `code`, and matching `redirect_uri` when redirect URI was supplied during authorization.
- Response contains `access_token`, `refresh_token`, `scope`, `expires_in` (official examples show `3600`), and `token_type` (`bearer`).

### Refresh Token Flow

Token endpoint:

- `POST https://apps.fortnox.se/oauth-v1/token`
- Basic client authentication as above.
- Body: `grant_type=refresh_token&refresh_token=<Refresh-Token>`.
- Response contains a new `access_token`, `refresh_token`, `scope`, `expires_in`, and `token_type`.

Design implication: store refreshed refresh tokens atomically; assume refresh token rotation.

### Client Credentials Flow / service accounts

Fortnox supports obtaining an access token with client credentials only after the customer has consented through the authorization flow.

Important Fortnox-specific requirements:

- Consent must be created using `account_type=service` in the authorization request.
- Client credentials token request requires `TenantId` header as a numeric value.
- Tenant ID must be stored by the integration.
- Fortnox recommends consuming webhook events for `consent created` and `consent revoked` to obtain/update tenant consent state.
- Alternative tenant ID discovery after activation: exchange auth code and call `/3/companyinformation` or `/3/settings/company` and use the `DatabaseNumber` field; this requires the `companyinformation` scope.
- Existing customers may have tenant ID included as a JWT claim.

Token endpoint:

- `POST https://apps.fortnox.se/oauth-v1/token`
- Headers: Basic auth, `Content-Type: application/x-www-form-urlencoded`, `TenantId: <numeric tenant id>`.
- Body: `grant_type=client_credentials`; optional `scope`. If scope is omitted, Fortnox uses scopes from user consent.
- Response contains `access_token`, `scope`, `expires_in`, and `token_type`; no refresh token is shown in Fortnox’s client credentials example.

### Revocation

Revocation endpoint:

- `POST https://apps.fortnox.se/oauth-v1/revoke`
- Basic client authentication and `Content-Type: application/x-www-form-urlencoded`.
- Fortnox states access-token revocation is not supported for Authorization Code Flow due to short access-token lifetime; revoke the refresh token instead.
- Body: `token_type_hint=refresh_token&token=<Refresh-Token>`.
- Response example: `{"revoked": true}`.

## Scope and license model

- Scopes determine access to endpoints.
- Fortnox states all access tokens have at least one scope.
- Scopes grant both read and write access; Fortnox does not provide read-only API scopes.
- A company must also have an active Fortnox license for the requested resource.
- Changing scopes in the app requires obtaining a new authorization code; existing connections are not automatically affected.
- Wrapper should model scopes as string enum-like constants generated/maintained from the official Scopes page, but must allow arbitrary strings for forward compatibility.

## Rate limits and retry strategy

Official Fortnox rate limit:

- `300 requests per minute per client-id and tenant`.
- Implemented as a sliding window with period of 5 seconds.
- Effective burst limit: `25 requests per 5 seconds`.
- Fortnox returns HTTP `429 Too Many Requests` when enforced.
- Fortnox notes rate limit scales by tenant/access token, not external IP address.

Client design:

- Rate limiter key: `(client_id, tenant_id/access_token subject)`. If tenant ID is unavailable, key by access-token identity in token store metadata.
- Default limiter: token-bucket or sliding-window approximation capped at 25/5s and 300/minute; configurable and disableable for tests.
- Retry policy:
  - Retry `429`, transient network failures, and selected `5xx` with exponential backoff plus jitter.
  - Respect `Retry-After` if Fortnox begins sending it; otherwise use limiter/backoff delay.
  - Do not automatically retry non-idempotent methods (`POST`, action `PUT`s) unless caller explicitly marks request as retry-safe or an idempotency strategy is in place.
  - Safe automatic retries: `GET`, possibly `DELETE` only when Fortnox endpoint semantics are known to tolerate repeat deletion; default `DELETE` should not be retried after write uncertainty.

## Pagination, filtering, sorting, and list responses

Official parameter behavior:

- Search is limited to documented query parameters for each resource.
- Only one resource-specific filter can be used at a time, but it can be combined with a global parameter such as `lastmodified`.
- Global search parameters include:
  - `lastmodified`: records since timestamp, example `2019-03-10 12:30`.
  - `financialyear`.
  - `financialyeardate`.
  - `fromdate` and `todate` for invoices, orders, offers, vouchers, and supplier invoices.
- Sorting uses `sortby` and `sortorder`; Fortnox example uses `sortorder=ascending`.
- `limit` defaults to `100`; minimum `1`; maximum `500`.
- `offset` defaults to `0`.
- Page pagination uses `page=<number>`.

OpenAPI list response metadata:

- Many list wrappers include `MetaInformation` with `@CurrentPage`, `@TotalPages`, and `@TotalResources`.

Client design:

- `Page[T]`: items, current_page, total_pages, total_resources, raw envelope.
- `ListParams`: page, limit, offset, filter, sortby, sortorder, lastmodified, financialyear, financialyeardate, fromdate, todate, and `extra` dict for resource-specific query parameters.
- `iter_pages(...)`: yields `Page[T]` until `@CurrentPage >= @TotalPages` or no next page metadata exists.
- `iter_all(...)`: yields items across pages; default `limit=500` for efficiency unless caller overrides.
- Preserve Fortnox envelope names. Resource clients define their collection key, e.g. `Customers`, `Invoices`, `Articles`, rather than assuming uniform response shape.

## Error handling model

Official response statuses:

- Success: `200 OK` resource returned, `201 Created` resource created, `204 Success` resource removed.
- Failure examples: `400 Bad Request`, `403 Forbidden`, `404 Not Found`, `500 Internal Server Error`.
- Failed requests return `ErrorInformation` envelope:
  - `error`
  - `message`
  - `code`

Official common error examples include:

- `1000003`: system exception.
- `1000030`: invalid response type / Accept.
- `1000031`: invalid content type.
- `2000310` / `2000311`: client secret or access token missing/incorrect.
- `2000588`: invalid parameter.
- `2001103`: API license missing.
- `2001101`: no active license for desired scope.
- `2000663`: no access to current scope.
- OAuth errors include `error_missing_license`, `error_missing_app_license`, and `403 Forbidden` when attempting to exchange an authorization code against `/auth` instead of `/token`.

Exception hierarchy:

- `FortnoxError`: base class; carries message and optional cause.
- `FortnoxHTTPError`: status_code, method, url, response_headers, raw_body, parsed body.
- `FortnoxAPIError`: extends HTTP error with `fortnox_error`, `fortnox_code`, `fortnox_message` from `ErrorInformation`.
- `FortnoxAuthError`: token exchange/refresh/revoke failures and `401/403` auth failures.
- `FortnoxRateLimitError`: `429`; includes retry-after/backoff metadata.
- `FortnoxValidationError`: `400` with known validation codes.
- `FortnoxNotFoundError`: `404`.
- `FortnoxServerError`: `5xx` after retries exhausted.
- `FortnoxSerializationError`: invalid JSON/XML or unexpected response envelope.

Error handling requirements:

- Never drop the official Fortnox error code/message.
- Provide a stable mapping for known codes, but keep unknown codes as normal `FortnoxAPIError`.
- Redact Authorization, Basic credentials, access tokens, refresh tokens, client secrets, and tenant-specific sensitive IDs from exception string representations and logs.

## Idempotency strategy

I found no Fortnox official documentation or OpenAPI reference for an `Idempotency-Key` header or equivalent request-id mechanism in the retrieved docs. Therefore the wrapper must not advertise native Fortnox idempotency.

Recommended design:

1. Do not auto-retry non-idempotent write operations after a request body may have reached Fortnox unless caller explicitly opts in.
2. Provide caller-side idempotency helpers, not hidden retries:
   - `idempotency_key` accepted in wrapper operation options for caller bookkeeping only; do not send it as a Fortnox header unless official support appears later.
   - Optional `IdempotencyStore` interface records request fingerprint, resource type, natural key, and resulting Fortnox identifier.
   - Resource-specific `create_or_get_by_*` helpers can be added only where Fortnox has safe natural keys and query semantics, e.g. customer number, article number, account number, currency code.
3. For caller-supplied identifiers accepted by Fortnox, prefer explicit identifiers over server-generated IDs where business rules allow.
4. Expose action endpoints (bookkeep, cancel, send, release, void, warehouseready, etc.) as side-effecting methods with no automatic retries by default.
5. Integration tests should include simulated network timeout-after-send cases to ensure write retries are blocked unless explicitly configured.

## Resource endpoint coverage

OpenAPI source: https://apps.fortnox.se/apidocs. Extracted spec contained 233 paths and 82 tags at research time.

Initial wrapper should be layered so resource coverage can grow without destabilizing core transport/auth. Prioritize common accounting/sales/purchase resources first.

### Phase 1 resource clients

- Company/user: `/3/companyinformation`, `/3/settings/company`, `/3/me`.
- Customers: `/3/customers`, `/3/customers/{CustomerNumber}`.
- Articles/prices: `/3/articles`, `/3/pricelists`, `/3/prices`.
- Invoices and payments: `/3/invoices`, invoice action endpoints, `/3/invoicepayments`, `/3/invoiceaccruals`.
- Suppliers and supplier invoices/payments: `/3/suppliers`, `/3/supplierinvoices`, `/3/supplierinvoicepayments`, `/3/supplierinvoiceaccruals`.
- Bookkeeping: `/3/accounts`, `/3/accountcharts`, `/3/financialyears`, `/3/vouchers`, `/3/voucherseries`, `/3/costcenters`, `/3/projects`, `/3/currencies`.
- Terms/settings reference data: `/3/termsofpayments`, `/3/termsofdeliveries`, `/3/wayofdeliveries`, `/3/modesofpayments`, `/3/units`, `/3/printtemplates`, `/3/predefinedaccounts`, `/3/predefinedvoucherseries`, `/3/settings/lockedperiod`.

### Phase 2 resource clients

- Offers, orders, contracts, contract templates/accruals.
- Archive/inbox/files and file/url connections.
- Salary/time: employees, salary transactions, absence/attendance transactions, expenses, schedule times, vacation debt basis, `/api/time/...`.
- Assets and asset types.
- Finance invoices.

### Phase 3 resource clients

- Warehouse `/api/warehouse/...` resources: stock points, stock balance/status, incoming goods, purchase orders, production orders, stocktaking, stock transfers, deliveries, custom documents, tenants.
- File attachments `/api/fileattachments/attachments-v1`.
- Integration partner/developer endpoints.

## Proposed package structure

`fortnox/`

- `__init__`: public exports and version.
- `client`: top-level `FortnoxClient` composition root.
- `config`: `FortnoxConfig` with base URLs, timeouts, user agent, retry/rate-limit options.
- `auth/`
  - `oauth`: authorization URL builder, token exchange, refresh, revoke, client credentials.
  - `tokens`: token dataclasses/protocols, expiry logic, token store interfaces.
  - `providers`: access-token provider implementations: static token, refresh-token provider, client-credentials provider, custom provider.
- `transport/`
  - `http`: sync transport abstraction over `httpx.Client`.
  - `async_http`: async transport abstraction over `httpx.AsyncClient` if async support is included.
  - `request`: request options, query serialization, JSON/form/multipart body handling.
  - `response`: envelope parsing and raw response wrappers.
  - `retry`: retry policy and backoff.
  - `rate_limit`: per-tenant/client limiter.
- `models/`
  - `common`: `MetaInformation`, `Page`, enums/constants, date/time types.
  - `errors`: `ErrorInformation` model.
  - resource model modules generated or curated from OpenAPI.
- `resources/`
  - `base`: base resource client, envelope extraction, typed CRUD helpers.
  - `company`, `customers`, `articles`, `invoices`, `suppliers`, `bookkeeping`, `reference_data`, etc.
  - `raw`: generic raw endpoint client for uncovered endpoints.
- `webhooks/`
  - models and validators for consent created/revoked events when official schemas are confirmed.
- `testing/`
  - mock transport, response builders, fixtures, fake token providers, contract-test helpers.
- `py.typed`: package typing marker.

## Public interfaces, conceptually

No implementation code is prescribed here; names describe stable API contracts.

### Composition root

- `FortnoxClient(config, token_provider, transport=None)`
- Exposes resources as properties: `client.customers`, `client.invoices`, `client.suppliers`, `client.accounts`, `client.raw`, etc.
- Lifecycle: context-manager support to close HTTP transport.
- Cross-cutting request options per call: timeout, retry override, rate-limit override, idempotency metadata, headers, raw response inclusion.

### Auth interfaces

- `AuthorizationUrlBuilder`: builds the `/oauth-v1/auth` URL with client_id, scopes, state, redirect_uri, access_type, account_type.
- `OAuthClient`: token exchange, refresh, client credentials, revoke refresh token.
- `TokenProvider`: returns valid access token metadata; may refresh internally.
- `TokenStore`: load/save per tenant/customer connection; atomic update after refresh.
- `TenantResolver`: maps customer/connection to tenant ID for service-account client credentials.

### Transport interfaces

- `Transport`: send prepared request and return response.
- `RequestExecutor`: applies auth header, content negotiation, rate limiting, retry, error mapping, and parsing.
- `RateLimiter`: acquire permit for key `(client_id, tenant_id/token_subject)`.
- `RetryPolicy`: determines retryability from method, status, exception, and request options.

### Resource interfaces

Every resource client should have predictable operations where supported by OpenAPI:

- `list(params=None, **resource_filters)` returns `Page[SummaryModel]`.
- `iter(params=None, **resource_filters)` yields all items.
- `get(identifier)` returns detailed model.
- `create(payload, options=None)` returns created model.
- `update(identifier, payload, options=None)` returns updated model.
- `delete(identifier, options=None)` handles `204` or documented response.
- Action methods use explicit verb names: `bookkeep_invoice`, `cancel_invoice`, `send_invoice`, `release_warehouse_document`, etc.

For resources where Fortnox uses compound identifiers, expose typed identifier value objects or clearly named parameters, e.g. voucher series + voucher number + financial year.

### Raw client

- Needed for uncovered endpoints and early Hermes integrations.
- Supports `request(method, path, query=None, json=None, data=None, files=None, expected_envelope=None)`.
- Still applies auth, rate limit, retry, error mapping, redaction, and configured base URL validation.

## Serialization and typing decisions

- Use `pydantic` v2 or dataclass-plus-adapter approach. Pydantic is recommended for robust alias handling because Fortnox response fields include names such as `@CurrentPage`.
- Preserve original field aliases for JSON round-trips; expose Pythonic properties for user ergonomics.
- Dates/times: Fortnox examples include `YYYY-MM-DD`, `YYYY-MM-DD HH:MM`; support `date`, `datetime`, and strings with explicit serializers.
- Unknown fields: allow/retain by default because Fortnox may add fields; optionally provide strict mode for tests.
- Envelope extraction must be resource-specific and OpenAPI-driven where possible.

## Testing strategy without credentials

### Unit tests

- Mock transport tests for every cross-cutting behavior:
  - Authorization header insertion.
  - Basic auth construction delegated to auth module with redacted logs.
  - Token refresh before expiry and atomic token-store update.
  - Client credentials request includes numeric `TenantId` header.
  - Rate limiter enforces 25/5s shape with fake clock.
  - Retry policy retries `GET` on `429/5xx` and refuses unsafe `POST` retry by default.
  - Error response envelope maps to exception with status/code/message preserved.
  - Pagination stops at `@TotalPages` and handles absent metadata gracefully.

### Contract-style tests from fixtures

- Store sanitized JSON fixtures copied from official examples/OpenAPI schemas, not real customer data.
- Generate fixture skeletons from OpenAPI for each resource list/get/create response envelope.
- Validate collection-key extraction (`Customers`, `Invoices`, `MetaInformation`, etc.).
- Validate common query serialization for `lastmodified`, `filter`, `sortby`, `sortorder`, `limit`, `offset`, `page`.

### Schema/OpenAPI drift tests

- Keep a pinned copy of Fortnox OpenAPI for generation tests.
- Optional scheduled/manual job downloads https://apps.fortnox.se/apidocs and extracts embedded OpenAPI to compare path/schema/tag drift.
- Drift report should identify new/removed paths, changed parameters, response envelope changes, and scope changes.

### Integration tests

- Disabled by default and never run in CI without explicit environment opt-in.
- Require user-provided credentials only outside this design task.
- Use a dedicated test tenant and fixtures; never mutate production accounts.
- Mark destructive tests separately.
- Prefer read-only smoke tests first: `/3/companyinformation`, `/3/me`, simple list endpoints with `limit=1`.

### Security tests

- Assert token/client secret redaction in exceptions, logs, reprs, and test failure snapshots.
- Assert no credentials are read from source-controlled fixture files.
- Assert redirect `state` is mandatory in authorization URL builder.

## Operational guidance for Hermes/tools integration later

- Hermes-facing tools should depend on `FortnoxClient` interfaces, not raw `httpx`.
- Tool layer should provide credential retrieval and token-store configuration externally; wrapper must not know Hermes secrets layout.
- Tools should request narrow scopes, but document that Fortnox scopes are read/write, not read-only.
- Tool operations that create/bookkeep/send/cancel documents must require explicit confirmation in agent workflows because Fortnox writes are business-side effects and native idempotency was not found.

## Open questions / follow-up before implementation

1. Confirm official webhook payload schemas for consent created/revoked events; the client-credentials doc mentions them but the schema was not captured in this pass.
2. Confirm whether Fortnox emits `Retry-After` on `429`; design supports it, but the retrieved rate-limit doc only states status `429`.
3. Decide generation strategy: fully generated models from OpenAPI vs curated models for Phase 1 resources. Recommendation: curated resource clients plus generated raw models/types for broad coverage.
4. Confirm packaging baseline: Python 3.10+ or 3.11+, sync-only first vs sync+async.
5. Confirm whether XML support is required. Recommendation: JSON-only initial wrapper unless a concrete user need arises.
