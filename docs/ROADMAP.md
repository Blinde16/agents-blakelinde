# Roadmap

This outlines the progression from a solo consultant command-center toward a scalable, client-isolated product asset.

## Phase 1: Minimum Viable Command Center (The Target MVP)
- Build the Vercel/Railway dual-host architecture.
- Wire Supabase Agno PgMemoryDb checkpointing.
- Implement Clerk Auth locking to single-user.
- Implement the `Lead Router` delegation scheme.
- Setup Ops Agent as fallback, CFO Agent for read-only database metric checks, CRO for Hubspot interactions.
- Build Next.js SWR polling to handle the pending approval UX action cards.
- **Goal**: Blake can type/speak a request and approve a tool execution safely.

## Phase 2: Voice Layer & UX Expansion 
- Hook Vapi.ai webhooks into the Python Router.
- Refine latency behavior on the phone frontend. 
- Enable the CMO Agent accessing Notion RAG endpoints for strategic brand synthesis.
- **Goal**: Full hands-free interaction capability mapped back to internal knowledge.

## Phase 3: Broad Integrations (Gmail / Calendar Actions)
- Deploy OAuth integrations for reading calendars and drafting specific emails via Ops layer.
- Ensure the Action Cards UI can render dynamic inputs (e.g. expanding an email draft allowing user to live-edit text before clicking 'Approve').

## Phase 4: Multi-Tenant Hardening (White-Label Strategy)
- Replace static `.env` keys with dynamic Postgres-driven OAuth app connections so individual clients can bind their own CRM and APIs.
- Rigidly audit DB Row-Level-Security rules locking everything behind `tenant_id`. 
- **Goal**: Spin out `agents.blakelinde.com` as an asset provided to consulting clients natively.
