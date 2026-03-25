# Launch Checklist

## Goal
Ship `agents.blakelinde.com` as a dependable mobile-first agent workspace that can sustain long-running work, approvals, and reconnects without confusing the user about system state.

## Must-Have Before Launch
- Clerk auth works across all web routes and API proxy routes.
- Next.js can always reach the Python backend using the production `BACKEND_API_URL`.
- FastAPI has health checks, structured logs, and clear error responses.
- Thread state survives refresh/reconnect on mobile.
- Long-running runs expose clear statuses: `processing`, `awaiting_approval`, `completed`, `error`.
- Approval flows are resumable and visibly reflected in the UI.
- At least one read workflow and one write-with-approval workflow are verified end-to-end.

## Product Readiness
- Mobile chat layout is comfortable on narrow screens and safe-area devices.
- Users can tell which layer is active and whether the system is still working.
- Stream interruptions degrade gracefully with useful recovery language.
- Spreadsheet upload feedback is visible and tied to the active thread.
- Empty, loading, approval, and error states all have intentional copy.

## Backend Readiness
- Every thread run writes state transitions to Postgres.
- Tool execution failures are caught and surfaced to the user without crashing the run.
- Approval-gated tools are idempotent where possible.
- External integrations have timeouts and retry policy where safe.
- Background tasks can complete without serverless execution limits.

## Observability
- Log thread ID, user ID, route target, tool start, tool finish, approval ID, and terminal run state.
- Distinguish model failure, tool failure, network failure, and auth failure in logs.
- Add dashboards or saved log queries for stuck runs, approval backlog, and repeated tool errors.

## Deployment
- `web` deployed on Vercel with production env vars set.
- `agent` deployed on Render or Railway as an always-on service.
- Supabase migrations applied in production.
- CORS and service-token validation verified between web and backend.
- Domain `agents.blakelinde.com` points at the web app and sign-in flow works there.

## Manual Acceptance Pass
1. Sign in on mobile Safari and Chrome.
2. Create a new thread, send a normal request, and confirm streaming text arrives.
3. Trigger an approval-gated action and approve it from the phone.
4. Refresh mid-run and verify thread history plus current status recover.
5. Background the browser, return, and confirm the UI re-syncs correctly.
6. Upload a finance sheet and use the returned `upload_id` in a CFO request.
7. Force a tool failure and verify the user sees a useful error state.
