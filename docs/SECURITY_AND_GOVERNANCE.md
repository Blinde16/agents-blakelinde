# Security & Governance

## 1. Authentication Layer (Next.js & Clerk)
- Clerk runs as middleware in Next.js, protecting all frontend routes.
- Unauthorized traffic reaching `agents.blakelinde.com/*` is swept to `/sign-in`.

## 2. API Authorization (Next.js Issuer)
- The Python Agno backend runs completely separated on an always-on host (Railway/Render).
- The Python backend *must not* accept public traffic.
- **The Pattern**: When Next.js pings the Python API (e.g. `POST /api/threads`), Next.js generates and signs an internal service JWT utilizing a secure secret (`INTERNAL_SERVICE_KEY`) shared exclusively between the two environments.
- Python validates this token and extracts the vetted user claims (`user_id`, `role`).
- This protects the orchestration service and avoids Python having to directly verify heavy third-party Clerk tokens.

## 3. Tool Permissions (Least Privilege)
- No agent is provided with an "Execute Arbitrary SQL" tool.
- PostgreSQL access is funneled through hardcoded `get_margin_by_client_id` functions, preventing prompt-injected `DROP TABLE` attacks.
- The Approval Wrapper mechanism guarantees tools that mutate state physically cannot execute until a separate API call (originating from human interaction in the UI) toggles the approval.

## 4. Encryption
- Secrets (OpenAI keys, HubSpot tokens, service keys) are exclusively managed via the Host Provider's environment variables. 
- Webhooks from Vapi carry an auth header validating the request legitimately originated from Vapi infrastructure.
