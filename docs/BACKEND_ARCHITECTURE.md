# Backend Architecture

## Stack
- **Framework**: Python 3.11+. FastAPI for serving the HTTP endpoints. Agno AgentOS for the reasoning engine.
- **Host**: Deployed on an always-on Docker environment (Render/Railway). Do NOT host on Vercel Python execution contexts due to strict 15s to 60s max execution limits.
- **Database driver**: `asyncpg` combined with Agno's `PgMemoryDb`.

## Event Dispatch Model
FastAPI acts as a thin wrapper over the Agno agents and memory system.
Because LLM interactions block the event loop heavily (unless utilizing deep `asyncio`), the backend uses `async/await` structure for all database calls and LLM invocations, optimizing concurrency even within a single-threaded server.

## Folder Structure
- `/api`: The FastAPI endpoints (`routes.py`, `dependencies.py` for auth checks).
- `/agents`: The Agno agent definitions (`builder.py`, localized configuration, system prompts, `cfo_agent.py`, `ops_agent.py`).
- `/tools`: The raw atomic python functions decorated with `@tool` executing external business logic.

## Resilience
A Python backend processing LLM requests will scale resources aggressively. Memory leaks must be avoided. Keep intermediate agent states small; avoid injecting 50MB PDFs directly into the agent memory history arrays without using RAG.
