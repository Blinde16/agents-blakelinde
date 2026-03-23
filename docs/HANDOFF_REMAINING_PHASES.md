# Handoff prompt: remaining implementation phases

**Purpose:** Copy this entire document (or the “Prompt for the coding agent” section at the bottom) into a new agent session. The repo is an **agent orchestration platform** (Next.js → FastAPI → Agno agents). This file summarizes **what is already done** and **what to build next**, with paths and constraints.

---

## Architecture (do not violate)

- **Next.js** = UI + Clerk auth only. **Python FastAPI** = LLM orchestration, tools, memory. Communication is **REST only** (no Server Actions to Python).
- **Absolute imports:** TypeScript `@/` → `web/src/`. Python: `from src....` with `PYTHONPATH=.` when running from `agent/`.
- **Prompts:** Load from `agent/prompts/*.md` asynchronously where applicable; avoid giant system strings in `.py` (see `.cursorrules`).
- **Tools:** Pydantic v2 for validation; **async** for DB/API; Supabase via **asyncpg** (pool in `src/orchestration/db_pool.py`).
- **Mutations:** Use existing **approval gate** pattern (`TOOLS_REQUIRING_APPROVAL`, `approval_gates` table, ActionCard UI) for anything that changes external systems.

---

## Already implemented (baseline)

### Stack
- **Routing:** `agent/src/orchestration/router.py` — slash commands (`/cfo`, `/cro`, `/cmo`, `/ops`) + keyword heuristics → specialist lane.
- **API:** `agent/src/api/routes.py` — threads, messages, state polling, approve; **`BackgroundTasks`** run `async_run_agent` after POST message.
- **Auth:** Clerk JWT + internal `x-service-token`; `CLERK_JWT_ISSUER` on agent; `user_id` scoping on `threads` / `users`.
- **DB:** `agent/src/orchestration/state.py` — Postgres runtime + **`asyncpg` pool** (`init_pool` / `close_pool` in `agent/main.py` lifespan). Hot paths consolidated to fewer round-trips.
- **Agents:** `agent/src/agents/specialists.py`, `builder.py` — specialists with `PgMemoryDb`, `add_history_to_messages`, `tool_call_limit=25`.
- **Tools registry:** `agent/src/tools/registry.py` — CFO (finance DB), CRO (HubSpot + approval-gated stage update), CMO (`search_brand_knowledge` / pgvector), Ops (`get_current_time` only).
- **RAG:** `agent/src/rag/knowledge_search.py`, `seed_knowledge.py`, `agent/knowledge/*.md`, migration `003_knowledge_and_finance.sql`. Embeddings need **`OPENAI_API_KEY`** and a model the project can use (`OPENAI_EMBEDDING_MODEL`).
- **Web:** `web/src/app/api/threads/**` proxies to Python with `buildAuthHeaders()`; `ChatStream` SWR polls state (~300ms when processing).

### Docs updated earlier
- `docs/MVP_SCOPE.md`, `docs/BACKEND_ARCHITECTURE.md` — Agno + heuristic router (not LangGraph as shipped MVP).

---

## Phase status and remaining work

### P0 — Speed / infra (partially done)
**Done:** asyncpg pool, fewer DB round-trips, faster SWR interval.

**Remaining (high leverage):**
1. **Token streaming** — Today the UI waits for the **full** assistant reply in Postgres + polling. Implement **SSE or chunked JSON** from FastAPI for assistant text; Next route proxies stream; client appends tokens. Agno `Agent.arun(..., stream=True)` returns an **async iterator** (`_arun`) when `is_streamable` — inspect `agno` version in use and wire `StreamingResponse`. Keep polling for **run status** and **approval** only, or merge into one mechanism.
2. **Optional:** Cache specialist `Agent` instances per `(thread_id, role)` only if Agno docs confirm **thread-safety** / no stale session state; otherwise skip.
3. **Optional:** `OPENAI_MODEL` env for faster default in dev.

### P1 — CFO: spreadsheets / structured finance
**Goal:** Finance interprets spreadsheets, not only seeded `finance_client_metrics` rows.

**Tasks:**
- Ingest: **CSV/XLSX upload** (Next route → Python) or **Google Sheets** OAuth read range.
- Parse with **pandas** / **openpyxl**; land **normalized** rows in Postgres (`tenant_id` / `user_id` scoped).
- New tools: e.g. `query_staging_metrics`, `summarize_sheet` with **strict** Pydantic inputs (no raw SQL from LLM).
- Extend RAG or metadata for **finance playbooks** in pgvector.

### P2 — CMO: Notion content calendar
**Goal:** Read/write Notion database for content calendar; brand RAG already exists.

**Tasks:**
- Notion API: integration token or OAuth; store secrets per user encrypted + `user_id`.
- Tools: list/upcoming items, create/update row, **approval gate** for writes that publish or alter external state.
- Optional: sync Notion pages into `knowledge_chunks` for hybrid search.

### P3 — Ops: Gmail + Calendar
**Goal:** Read (then draft) email and calendar; no silent sends.

**Tasks:**
- Google Workspace OAuth (or Microsoft Graph if product direction changes).
- Tools: `list_recent_threads`, `get_calendar_events`, `draft_email` (returns draft only); **send** / **create event** behind **approval**.
- Token storage: Postgres, encrypted, keyed by internal `user_id`.

### P4 — Social (future)
**Goal:** Draft → approve → schedule → post (LinkedIn, Meta, X, etc.).

**Tasks:**
- Per-platform OAuth and API compliance; **never** auto-post without approval.
- Start with **draft + scheduled row in DB**; posting only after explicit user action in UI.

### Cross-cutting
- **CEO cockpit / weekly brief** — aggregate tools + RAG into one structured output (new prompt + orchestration step).
- **Observability:** LangSmith / logging of tool names and args (already partially via Agno `show_tool_calls`).

---

## Environment variables (reference)

| Area | Variables |
|------|-----------|
| Web | `NEXT_PUBLIC_CLERK_*`, `CLERK_SECRET_KEY`, `BACKEND_API_URL`, `INTERNAL_SERVICE_KEY_SIGNER` |
| Agent | `DATABASE_URL`, `CLERK_JWT_ISSUER`, `INTERNAL_SERVICE_KEY_SIGNER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `HUBSPOT_PRIVATE_APP_TOKEN` (optional), `PG_POOL_MIN` / `PG_POOL_MAX` (optional) |
| Embeddings | `OPENAI_EMBEDDING_MODEL` if default blocked on account |

---

## Key file paths (quick index)

| Area | Path |
|------|------|
| FastAPI app | `agent/main.py` |
| Routes | `agent/src/api/routes.py` |
| Router | `agent/src/orchestration/router.py` |
| State + DB | `agent/src/orchestration/state.py`, `db_pool.py` |
| Agents | `agent/src/agents/specialists.py`, `builder.py` |
| Tools | `agent/src/tools/registry.py`, `finance.py`, `hubspot.py`, `schemas.py` |
| RAG | `agent/src/rag/knowledge_search.py`, `seed_knowledge.py` |
| Prompts | `agent/prompts/*.md` |
| Migrations | `supabase/migrations/*.sql` |
| Next proxy | `web/src/lib/backend.ts`, `backendAuth.ts`, `web/src/app/api/threads/**` |
| Chat UI | `web/src/components/chat/ChatStream.tsx`, `Controls.tsx`, `ActionCard.tsx` |

---

## Prompt for the coding agent (copy below)

```
You are continuing work on the Blake Linde Agents Platform (repo: agents-blakelinde).

Read docs/HANDOFF_REMAINING_PHASES.md for full context. Constraints are in .cursorrules at repo root.

Current state:
- FastAPI + Agno specialists; heuristic router; Clerk + service token; Postgres + asyncpg POOL; approval gates for HubSpot stage updates; pgvector RAG for CMO brand search; thread state via polling (no token streaming yet).

Your priority order unless the user says otherwise:
1) Implement token streaming (SSE or equivalent) from Python through Next to the chat UI so first token latency improves; keep approval + run state correct.
2) Then proceed with phased features: CFO spreadsheet/Sheets ingest, Notion calendar tools with approval on writes, Gmail/Calendar read + draft-with-approval.

Requirements:
- Preserve async patterns; use existing pool in src/orchestration/db_pool.py for new DB access.
- New external writes go through approval where appropriate.
- Do not add Server Actions for LangGraph/Python; use Next route handlers only.
- Match existing code style and typing.

Start by reading HANDOFF_REMAINING_PHASES.md and the files it lists, then implement the next unfinished phase with minimal unrelated refactors.
```

---

*End of handoff document.*
