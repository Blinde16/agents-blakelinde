# Backend Architecture

## Stack
- **Framework**: Python 3.11+. FastAPI for serving the HTTP endpoints. **Agno** for the agent runtime (specialists, tools, optional team router in code but not the default HTTP path).
- **Host**: Deployed on an always-on Docker environment (Render/Railway). Do NOT host on Vercel Python execution contexts due to strict 15s to 60s max execution limits.
- **Database driver**: `asyncpg` for application tables (threads, messages, approvals, RAG chunks, finance reads). Agno uses `PgMemoryDb` and `PostgresAgentStorage` with the same `DATABASE_URL` where configured.

## Routing and orchestration
- **HTTP layer** ([`agent/src/api/routes.py`](../agent/src/api/routes.py)) creates threads, appends messages, runs a **single specialist** per user message, and exposes polling state.
- **Message routing** ([`agent/src/orchestration/router.py`](../agent/src/orchestration/router.py)) picks CFO / CRO / CMO / Ops using slash commands and keyword heuristics. This is deterministic and auditable; it is not an LLM classifier in the MVP.
- **Lead router agent** ([`agent/src/agents/builder.py`](../agent/src/agents/builder.py) `build_lead_router_agent`) demonstrates Agno **team** delegation and may be wired later; the live API path builds one specialist at a time.

## Event dispatch model
FastAPI acts as a thin wrapper over the Agno agents and persistence.
All database calls that touch app tables use **async** `asyncpg`. LLM and tool calls run in async context; long agent runs are scheduled via FastAPI `BackgroundTasks` so the client receives an immediate `processing` response and polls for completion.

## Folder structure (agent package)
- **`src/api`**: FastAPI routes (`routes.py`), auth dependencies (`dependencies.py`).
- **`src/agents`**: Agent construction (`builder.py`, `specialists.py`), external prompts under `agent/prompts/`.
- **`src/orchestration`**: Router heuristics and Postgres runtime state (`state.py`).
- **`src/tools`**: Tool implementations and registry; mutating tools that need approval are registered in `TOOLS_REQUIRING_APPROVAL`.

## Resilience
A Python backend processing LLM requests will scale resources aggressively. Memory leaks must be avoided. Keep intermediate agent states small; do not inject large documents into the chat transcript—use **RAG** (`pgvector` + retrieval tool) for long-form knowledge.
