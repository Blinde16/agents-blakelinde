# MVP Scope

This document clearly defines the boundaries of the Phase 1 MVP to prevent scope creep. This architecture focuses heavily on operational robustness over feature variety.

## In-Scope (Must Have for MVP)
- **Web UI**: Next.js App Router optimized for mobile. Single chat stream with inline action cards.
- **Authentication**: Single-tenant deployment protected by Clerk. The Next.js route handlers validate the Clerk session and forward a Clerk-issued JWT to FastAPI alongside the internal service token; the Python layer verifies the JWT and scopes all thread and approval data by authenticated `user_id` (mapped to the `users` table).
- **Orchestration Engine**: Python FastAPI service running **Agno** agents with **Postgres-backed** thread messages, run state, and Agno `PgMemoryDb` / `PostgresAgentStorage` adapters. (LangGraph remains an optional future direction; the shipped MVP is Agno-first.)
- **Agents**: 4 roles defined in code (CFO, CRO, CMO, Ops) with distinct system prompts and tools.
- **Routing Strategy**: Functional role layers. A **deterministic router** (slash commands plus keyword heuristics) selects the active specialist per message; this is intentional for predictability. An LLM classifier may be added later without changing the HTTP contract.
- **Voice Integrations**: Vapi.ai transport layer. Thin webhook event adapter catching Vapi events and dispatching them to the async orchestration boundary (planned; not required for core text MVP).
- **Tool Framework**: Human-in-the-loop approval gates persisted in Postgres; mutating tools queue an approval record and the UI polls until the user approves or rejects. Polling-based UI for approval status.
- **Integrations**: 
  1. HubSpot (CRO Agent) - Limited to read/move specific deals.
  2. Notion (CMO/Ops Agent) - Scoped knowledge adapter (read-only document RAG).
  3. Postgres (CFO Agent) - Specific read-only financial query tools.
- **Analytics**: LangSmith tracing, simple PostHog event logging.

## Out-of-Scope (Deferred to Post-MVP)
- **Real-time UI updates (WebSockets)**: We will rely on HTTP polling (SWR/React Query) for state updates in Phase 1 before investing in complex WS infrastructure.
- **Cross-Agent Debate / Swarm**: Agents do not talk to each other to figure out complex multi-step problems. Maximum one hand-off, then escalate to user for clarification.
- **Dynamic Identity**: Agents will not have pseudo-personalities. They represent functional layers (e.g. "Finance Layer").
- **Proactive Cron Actions**: The graph is strictly reactive to user input in MVP. No background jobs waking up to check things without user interaction.
- **Multi-tenant RLS Enforcement**: Though the schema will have `org_id`, deep multi-tenant row-level security is deferred until we move off the single-user testbed.
- **Memory Consolidation**: No infinite memory summaries. Thread context is bounded by Agno history settings (`add_history_to_messages`, `num_history_responses`) plus Agno memory where enabled. **Knowledge RAG** uses a dedicated `pgvector` table for brand/docs retrieval, not unbounded chat memory.
- **Extensive Integrations**: No Google Calendar, Gmail, Stripe mutations, or complex Slack bots in Phase 1. Limit strictly to HubSpot, Notion (Read), and Postgres.
