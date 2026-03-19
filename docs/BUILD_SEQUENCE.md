# Build Sequence

Because the architecture requires complex state integration, building must proceed linearly. Do not jump to voice if the database cannot check a basic prompt.

## Setup Phase
1. Initialize monorepo structure.
2. Initialize `package.json` for Next.js (`/web`) and Python dependencies (`/agent`).
3. Setup local `.env` files based on the map outlined in `DEPLOYMENT.md`.

## Data Phase (Supabase)
4. Execute raw SQL migrations to build the `users`, `threads`, and `approval_gates` tables.
5. Setup the official `langgraph-checkpoint-postgres` library locally, pointing it at the Supabase connection string to ensure tables generate.

## Backend Phase (Python / LangGraph)
6. Build `fastapi` server in `agent/main.py`. Test `/health`.
7. Define the `TypedDict` State schema.
8. Scaffold the `Router`, `Ops`, and `CFO` nodes with simple static prompts and no tools.
9. Link nodes in `StateGraph` and attach the postgres checkpointer.
10. Build the `interrupt_before` Tool UI Node logic to pause when a mutating action hits. 

## Frontend Phase (Next.js)
11. Scaffold basic Clerk authentication on `/web`.
12. Build the serverless proxy in Next.js `app/api/relay` to pass signed tokens to FastAPI.
13. Build the primary Chat UI. Text input hits proxy -> hits Python graph.
14. Implement the HTTP Polling mechanism to pull `PENDING` states from `approval_gates`. 
15. Render the UI Approval Action Card and wire the "Approve" button back to the python graph.

## Advanced Integrations Phase
16. Connect HubSpot API to the `CRO` agent node via secure tools.
17. Connect the Notion Knowledge Adapter for the `CMO` agent.
18. Wire the Vapi Webhook adapter allowing Voice events to drop into `BackgroundTasks` traversing the built graph.
