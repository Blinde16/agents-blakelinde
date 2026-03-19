# Decision Log

This log records major architectural decisions that impact the system's execution capability. If shifting a core technology, log it here first.

## 1. Voice Integration Architecture
**Decision**: We use **Vapi** as the voice transport, but process execution asynchronously behind a "Thin Event Adapter".
**Rationale**: Vapi enforces tight HTTP timeouts on their webhooks. A LangGraph process calling multiple tools and a large LLM context can easily exceed 5-10 seconds.
**Tradeoffs**: Vapi will need to play short filler audio ("Thinking...") while we wait to POST the final result back via the Server REST API.

## 2. Graph State Persistence
**Decision**: Use `langgraph-checkpoint-postgres` directly storing states into Supabase Postgres DB.
**Rationale**: Keeps all MVP backend logic within a single managed database vendor without needing separate vector or key-value stores for thread recovery.

## 3. Human Approval Latency Mechanism
**Decision**: HTTP Polling via SWR over WebSockets.
**Rationale**: Keeping the Next.js frontend stateless and disconnected from the Railway Python environment simplifies initial deployment.

## 4. CRM Integration Constraint
**Decision**: Only HubSpot is supported in the MVP.
**Rationale**: Prevents scope explosion when mapping deals.

## 5. Notion Integration Constraint
**Decision**: Notion is purely a read-only scoped knowledge adapter for the CMO/Ops agents.
**Rationale**: Notion APIs are not fast enough to act as the primary runtime state checkpointer.

## 6. Escalation Rule Pattern
**Decision**: Maximum one handoff between agents, then explicit user clarification.
**Rationale**: A recursive agent swarm is a gimmick in a practical command center. Overly complicated multi-turn internal chatter balloons token costs and worsens latency. If Ops can't figure it out, it must ask the human.
