# MVP Scope

This document clearly defines the boundaries of the Phase 1 MVP to prevent scope creep. This architecture focuses heavily on operational robustness over feature variety.

## In-Scope (Must Have for MVP)
- **Web UI**: Next.js 14 App Router optimized for mobile. Single chat stream with inline action cards.
- **Authentication**: Single-tenant deployment protected by Clerk (only Blake Linde has access, or strict allowlink). Token validation between frontend and backend.
- **Orchestration Engine**: Python FastAPI service running a LangGraph `StateGraph` with the Official Postgres checkpointer.
- **Agents**: 4 roles defined in code (CFO, CRO, CMO, Ops) with distinct system prompts and tools.
- **Routing Strategy**: Functional role layers. Classifier model routes incoming messages.
- **Voice Integrations**: Vapi.ai transport layer. Thin webhook event adapter catching Vapi events and dispatching them to the async orchestration graph.
- **Tool Framework**: Tool approval pause mechanism using LangGraph's `interrupt_before`. Polling-based UI for checking approval status.
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
- **Memory Consolidation**: No infinite memory summaries or vector DB memory. Thread context window limits are managed by LangGraph's standard trimming logic.
- **Extensive Integrations**: No Google Calendar, Gmail, Stripe mutations, or complex Slack bots in Phase 1. Limit strictly to HubSpot, Notion (Read), and Postgres.
