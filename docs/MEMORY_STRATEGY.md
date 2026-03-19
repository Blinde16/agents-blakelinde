# Memory Strategy

Memory within the Agents Platform is intentionally segmented to prevent context pollution and prevent database-as-a-brain latency traps.

## 1. Short-Term Memory (Runtime State)
- **Mechanism**: The Agno `PgMemoryDb` Postgres memory store.
- **Location**: `agent_memory` and `agent_storage` tables.
- **Rules**: Everything within a specific analytical chain or request is handled by Agno's dynamic memory arrays. Agno manages automatic memory trimming if context windows become too large. This state is strictly bound to the `thread_id` and persists indefinitely, allowing users to return later for multi-stage workflows or pending approvals.

## 2. Long-Term Memory (Context Knowledge)
- **Mechanism**: Scoped Knowledge Adapter reading Notion.
- **Location**: Notion Databases/Pages.
- **Rules**: Notion is NOT the graph state store. Agents do NOT query Notion to figure out what they said 5 minutes ago. Notion is used exclusively when an Agent needs to load "ground truth" policies (e.g., the CMO Agent reading the "Brand Messaging Template" page before drafting copy).

## 3. Operational State (Business Reality)
- **Mechanism**: Direct Database / API Tool querying. 
- **Location**: PostgreSQL and HubSpot.
- **Rules**: Agents do not try to "remember" client revenue or open deal statuses in their LLM memory. They use explicit tools (`hubspot_read_deal`) strictly at runtime to fetch the immediate truth. This prevents hallucinated pipeline numbers.
