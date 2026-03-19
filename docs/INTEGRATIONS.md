# Integrations Strategy

Phase 1 focuses exclusively on integrations critical to the four agent roles, emphasizing reliability over breadth.

## 1. HubSpot (Targeting CRO Agent)
- **Authentication**: Private App Token (Stored securely in Render/Railway `.env`).
- **Scope**: Single-provider for MVP (no generic Salesforce abstractions).
- **Core Operations**: Let CRO Agent query pipeline state, search specific clients, and request stage modifications on specific deals.

## 2. Notion (Targeting CMO/Ops Agents)
- **Role**: Scoped Knowledge Adapter.
- **Implementation**: Notion is purely a read-only document lake, *not* the graph's runtime memory.
- **Mechanics**: Provide specific Notion Page IDs constraints in the tools (e.g. `Brand_Guidelines_Page_ID`) to limit the RAG retrieval scope. The Agent fetches text from these approved pages to guide decision making. 

## 3. PostgreSQL (Targeting CFO Agent)
- **Role**: Structured backend database connection.
- **Implementation**: Assume there is a Supabase table representing operational reality (e.g., a pseudo-ERP `invoices` or `projects` table). 
- **Mechanics**: Create safe read-only SQL execution tools. Use explicit views containing `user_id` context to prevent cross-account querying boundaries if we move toward multi-tenant. 

## Later-Phase Rollouts
The following are explicitly deferred from the initial MVP to limit testing complexity:
- Gmail (OAuth scopes too complex for phase 1)
- Google Calendar
- Stripe (Stripe webhooks and idempotency keys add deep complexity)
- Slack webhooks
