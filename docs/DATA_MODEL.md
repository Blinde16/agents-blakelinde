# Data Model (Supabase)

This architecture assumes PostgreSQL (Supabase) is the source of truth for all runtime state, user profiles, and action gating.

## Core Entities
1. **users**
   - `id` (UUID): Primary Key.
   - `clerk_user_id` (String): External ID from Clerk authentication.
   - `tenant_id` (UUID): For phase 2 data isolation. All operational data must map back here.
2. **threads**
   - `id` (UUID): Primary Key. Sent back and forth between Next.js and Python.
   - `user_id` (UUID): Foreign Key linking session ownership.
   - `title` (String): Auto-generated conversation summary.
3. **thread_runs**
   - `thread_id` (UUID): Primary Key / Foreign Key to `threads`.
   - `status` (String): Runtime status such as `idle`, `processing`, `awaiting_approval`, `completed`, `error`.
   - `active_agent` (String): The currently assigned functional layer.
   - `pending_approval` (Boolean): Whether a mutating tool is paused for review.
   - `approval_gate_id` (UUID): The currently active approval gate, if any.
4. **thread_messages**
   - `id` (UUID): Primary Key.
   - `thread_id` (UUID): Foreign Key.
   - `role` (String): `user` or `assistant`.
   - `content` (Text): Persisted transcript content for UI polling.
5. **langgraph_checkpoints**
   - Handled entirely by `langgraph-checkpoint-postgres` library.
   - Saves binary byte blocks `bytea` mapping to `thread_id` and `checkpoint_id` to allow resuming workflows at exact nodes.
6. **approval_gates**
   - `id` (UUID): Primary Key.
   - `thread_id` (UUID): Foreign Key.
   - `tool_name` (String): e.g., `hubspot_update_deal_stage`.
   - `payload` (JSONB): The exact arguments the LLM requested.
   - `status` (Enum): `PENDING`, `APPROVED`, `REJECTED`. Next.js modifies this record directly.
7. **hubspot_deal_cache**
   - Since we only fetch specific HubSpot deals, we cache the resulting JSON here linking back to the `user_id` to minimize roundtrips on rapid-fire requests.

## Role of Row-Level Security (RLS)
The database must be structured assuming multitenancy from day 1, even if the user base is 1. `tenant_id` validation is embedded in Supabase RLS. Next.js accesses tables using Supabase JS client instantiated with the logged-in user's identity token.
