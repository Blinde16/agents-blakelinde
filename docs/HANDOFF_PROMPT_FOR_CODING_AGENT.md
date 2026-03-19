# Handoff Prompt for Coding Agent

Copy and execute the exact prompt below when starting the technical build phase inside Cursor, Cline, or an independent worker agent:

---

**Prompt:**

"You are executing Phase 1 (MVP) of the Blake Linde Agents Platform (`agents.blakelinde.com`).

First, read the entire contents of the `/docs` directory to understand the firm system boundaries, specifically the `SYSTEM_ARCHITECTURE.md`, `DATA_MODEL.md`, and `LANGGRAPH_ARCHITECTURE.md`. 

Do not deviate from the architectural decisions outlined in `DECISION_LOG.md`. 
Do not use mock data generation; assume a Postgres database is the source of truth for all runtime state.
Do not build autonomous loops.

Your first technical assignment:
1. Initialize a Turborepo/monorepo structure with two direct sub-directories: `/web` (Next.js 14 App Router, Tailwind, TypeScript) and `/agent` (Python 3.11, FastAPI, virtual environment).
2. Write the raw `.sql` migrations for the Supabase database matching the schema defined in `DATA_MODEL.md`. Place these in a `/supabase/migrations` folder.
3. Stub the FastAPI application with a `/health` route and install `langgraph`, `langchain-openai`, and `langgraph-checkpoint-postgres`. 
4. Stop and ask me to verify the directory structure before writing the Next.js UI or the LangGraph nodes."
