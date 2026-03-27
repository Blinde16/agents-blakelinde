import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from agno.memory.db.postgres import PgMemoryDb
from agno.storage.agent.postgres import PostgresAgentStorage

# Import the API router — was missing, caused crash on startup
from src.api.routes import router as api_router
from src.orchestration.db_pool import close_pool, init_pool
from src.tools.sync_run import set_main_loop
from src.orchestration.state import initialize_runtime_tables
from src.orchestration.worker import run_job_worker
from src.rag.seed_knowledge import ensure_knowledge_seeded


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: Initialize Agno Postgres Memory and Storage adapters.
    Both tables are auto-created if they don't exist.
    """
    db_uri = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")

    agent_memory = PgMemoryDb(table_name="agent_memory", db_url=db_uri)
    agent_storage = PostgresAgentStorage(table_name="agent_storage", db_url=db_uri)

    try:
        agent_memory.create()
        agent_storage.create()
        initialize_runtime_tables(db_uri)
        print("[OK] Agno Postgres memory and storage tables initialized.")
    except Exception as e:
        print(f"[WARN] Postgres initialization info: {e}")

    try:
        await init_pool(db_uri)
        print("[OK] asyncpg connection pool ready.")
    except Exception as e:
        print(f"[ERROR] asyncpg pool failed: {e}")
        raise

    set_main_loop(asyncio.get_running_loop())

    try:
        await ensure_knowledge_seeded(db_uri)
    except Exception as e:
        print(f"[WARN] Knowledge seed skipped: {e}")

    # Attach both to app state so routes can access without re-creating
    app.state.agent_memory = agent_memory
    app.state.agent_storage = agent_storage
    app.state.database_url = db_uri
    worker_stop = asyncio.Event()
    worker_task = asyncio.create_task(run_job_worker(app, worker_stop), name="agent-job-worker")
    app.state.agent_job_worker_stop = worker_stop
    app.state.agent_job_worker_task = worker_task
    yield

    worker_stop.set()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await close_pool()


app = FastAPI(title="Blake Linde Agents Platform", lifespan=lifespan)

# Mount the API routes (prefixed at /api via router definition)
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agents.blakelinde-backend"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
