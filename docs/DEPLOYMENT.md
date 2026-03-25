# Deployment Strategy

The deployment separates the always-on orchestration runtime from the public web app so long-running agent work survives beyond serverless request limits.

## Recommended Topology

### 1. Vercel (`web`)
- **Role**: Public Next.js UI, Clerk auth boundary, backend proxy routes.
- **Domain**: `agents.blakelinde.com`
- **Runtime**: Standard Next.js deployment from the `web` directory.

### 2. Render or Railway (`agent`)
- **Role**: Always-on FastAPI service for LLM execution, tool orchestration, approvals, and persistence.
- **Domain**: Internal URL or protected subdomain such as `api.blakelinde.com`
- **Runtime**: Docker deploy using [`agent/Dockerfile`](../agent/Dockerfile)

### 3. Supabase (Postgres)
- **Role**: Durable storage for threads, approvals, context state, action audit, finance data, and agent memory/storage tables.

## Deployment Order

1. Provision Supabase and obtain `DATABASE_URL`.
2. Apply all SQL migrations in [`supabase/migrations`](../supabase/migrations).
3. Deploy the FastAPI service from [`agent`](../agent) with production env vars.
4. Deploy the Next.js app from [`web`](../web) with matching auth and backend env vars.
5. Configure Clerk allowed origins/redirects for `agents.blakelinde.com`.
6. Run the manual acceptance pass from [`docs/LAUNCH_CHECKLIST.md`](./LAUNCH_CHECKLIST.md).

## Environment Variables

Use [`.env.example`](../.env.example) as the master reference.

### Required on both web and backend
- `INTERNAL_SERVICE_KEY_SIGNER`
  Must match exactly in Vercel and the Python service. This is what prevents public traffic from calling the backend directly.
- `DATABASE_URL`
  Required by the backend. Keep this server-side only.

### Required on Vercel (`web`)
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `BACKEND_API_URL`
  Example: `https://api.blakelinde.com`
- `INTERNAL_SERVICE_KEY_SIGNER`

### Required on Render/Railway (`agent`)
- `DATABASE_URL`
- `INTERNAL_SERVICE_KEY_SIGNER`
- `CLERK_JWT_ISSUER`
  Required for backend verification of Clerk-issued bearer tokens.
- `OPENAI_API_KEY`
- `SECRETS_FERNET_KEY`
  Required in production to encrypt and decrypt stored Google/Notion credentials.

### Usually required on backend for current features
- `OPENAI_MODEL`
- `OPENAI_ROUTER_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `ROUTER_USE_LLM`
- `LOG_LEVEL`
- `THREAD_RUN_STALE_SECONDS`
- `PG_POOL_MIN`
- `PG_POOL_MAX`
- `PG_POOL_COMMAND_TIMEOUT`
- `TOOL_SYNC_TIMEOUT`

### Optional backend integrations
- `HUBSPOT_PRIVATE_APP_TOKEN`
- `NOTION_API_KEY`
- `NOTION_CONTENT_CALENDAR_DB_ID`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_PRIMARY_CALENDAR_ID`

### Development-only toggles that should stay off in production
- `ALLOW_INSECURE_DEV_AUTH`
- `DEV_CLERK_USER_ID`
- `ALLOW_PLAINTEXT_INTEGRATION_SECRETS`
- `AGENT_TESTING`

## Backend Deploy Notes

- Build from [`agent/Dockerfile`](../agent/Dockerfile).
- Start command is handled by the container: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Health check endpoint: `GET /health`
- The backend should not be treated as a public API. Keep the service-token check enabled.
- Startup initializes Agno Postgres tables plus runtime tables; it also attempts knowledge seeding.

## Web Deploy Notes

- Root directory: `web`
- Build command: `npm run build`
- Start command: `npm run start`
- The app proxies requests through its `/api/*` routes and forwards Clerk bearer tokens plus the internal service token.

## Production Smoke Test

After deploy:

1. Open `agents.blakelinde.com` and sign in.
2. Create a thread and send a normal chat request.
3. Confirm the backend receives the request and `/api/threads/:id/state` updates.
4. Trigger an approval-gated action and approve it.
5. Refresh mid-run and confirm the thread/session recovers.
6. Verify stale-run metadata appears if a run is intentionally wedged.
7. Confirm the backend logs include `thread_run` lifecycle events.

## Risks To Watch

- `CLERK_JWT_ISSUER` missing or incorrect on the backend will cause all authenticated API calls to fail.
- `INTERNAL_SERVICE_KEY_SIGNER` mismatch between web and backend will return 403s.
- Missing `SECRETS_FERNET_KEY` will break stored integration credentials in production.
- A public backend URL without the service-token gate would expose tool execution paths.
- The frontend will look healthy even when the backend is unreachable unless `BACKEND_API_URL` is correct and monitored.
