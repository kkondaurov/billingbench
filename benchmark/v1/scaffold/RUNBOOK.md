# Runtime

This is infrastructure only. Implement the current business request and the API
contracts delivered with it. There is no preselected billing schema or architecture.

- `mix setup` fetches dependencies and creates/migrates PostgreSQL.
- `mix test` uses the separate test database.
- `PHX_SERVER=true mix phx.server` serves the application on PORT (default 4000).
- DATABASE_URL, TEST_DATABASE_URL and SECRET_KEY_BASE are supplied by the runtime.
- Decimal is available for exact money; Oban is supervised and migrated.
- OTP's `:httpc` HTTP client is started through `:inets` and `:ssl`.

The scaffold verifies bearer tokens or the `billing_token` browser cookie. The
authenticated identity is `conn.assigns.current_actor`, a map with string keys
tenant_id, role and customer_id, or nil. Your application must enforce the published
operation and resource permissions. The platform_admin identity can create tenants;
it is not an implicit tenant operator. `/_session` accepts a token for browser login.

For your own tests, sign JSON `{tenant_id,role,customer_id}` with these steps:
base64url encode its UTF-8 bytes without padding; HMAC-SHA256 that encoded string
using BILLING_AUTH_SECRET; append a dot and the base64url signature without padding.
The development secret defaults to `billingbench-local-development-only`. The
benchmark runtime supplies a separate secret and provisions its own actor tokens.
No user-management interface is required.
