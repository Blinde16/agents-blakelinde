from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
from typing import Any

from src.orchestration.job_runner import (
    execute_agent_run_job,
    execute_approved_tool_job,
    record_agent_run_failure,
    record_approved_tool_failure,
    route_from_payload,
)
from src.orchestration.state import (
    claim_next_agent_job,
    complete_agent_job,
    fail_agent_job,
    recover_stale_agent_jobs,
    touch_agent_job,
)

logger = logging.getLogger(__name__)


def _worker_poll_seconds() -> float:
    raw = os.getenv("AGENT_JOB_WORKER_POLL_SECONDS", "").strip()
    if not raw:
        return 2.0
    try:
        parsed = float(raw)
    except ValueError:
        logger.warning("Invalid AGENT_JOB_WORKER_POLL_SECONDS=%r; using default 2.0", raw)
        return 2.0
    return max(parsed, 0.2)


def _heartbeat_seconds() -> float:
    raw = os.getenv("AGENT_JOB_HEARTBEAT_SECONDS", "").strip()
    if not raw:
        return 15.0
    try:
        parsed = float(raw)
    except ValueError:
        logger.warning("Invalid AGENT_JOB_HEARTBEAT_SECONDS=%r; using default 15.0", raw)
        return 15.0
    return max(parsed, 5.0)


def _job_worker_enabled() -> bool:
    if os.getenv("AGENT_TESTING", "").strip() == "1":
        return False
    raw = os.getenv("AGENT_JOB_WORKER_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


async def _heartbeat_job(db_url: str, job_id: str, worker_id: str, stop: asyncio.Event) -> None:
    interval = _heartbeat_seconds()
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            await touch_agent_job(db_url, job_id, worker_id)


async def process_claimed_job(app: Any, job: dict[str, Any]) -> None:
    db_url = app.state.database_url
    payload = job.get("payload") or {}
    job_type = job["job_type"]

    if job_type == "agent_run":
        route = route_from_payload(payload["route"])
        await execute_agent_run_job(
            db_url=db_url,
            agent_storage=app.state.agent_storage,
            agent_memory=getattr(app.state, "agent_memory", None),
            thread_id=job["thread_id"],
            message=payload["message"],
            user_internal_id=job["user_id"],
            route=route,
        )
        return

    if job_type == "approved_tool":
        await execute_approved_tool_job(
            db_url=db_url,
            thread_id=job["thread_id"],
            user_internal_id=job["user_id"],
            approval=payload["approval"],
        )
        return

    raise ValueError(f"Unsupported agent job type: {job_type}")


async def _record_terminal_stale_job_failure(db_url: str, job: dict[str, Any]) -> None:
    payload = job.get("payload") or {}
    error = str(job.get("last_error") or "Agent job failed after worker heartbeat expired.")

    if job["job_type"] == "agent_run":
        route_payload = payload.get("route")
        if isinstance(route_payload, dict):
            await record_agent_run_failure(
                db_url=db_url,
                thread_id=job["thread_id"],
                user_internal_id=job["user_id"],
                route=route_from_payload(route_payload),
                error=error,
            )
        else:
            logger.warning("agent_job_worker missing route payload for stale agent_run job=%s", job["id"])
        return

    if job["job_type"] == "approved_tool":
        approval = payload.get("approval")
        if isinstance(approval, dict):
            await record_approved_tool_failure(
                db_url=db_url,
                thread_id=job["thread_id"],
                user_internal_id=job["user_id"],
                approval=approval,
                error=error,
            )
        else:
            logger.warning("agent_job_worker missing approval payload for stale approved_tool job=%s", job["id"])
        return

    logger.warning("agent_job_worker cannot record stale failure for unsupported job type=%s id=%s", job["job_type"], job["id"])


async def run_job_worker(app: Any, stop: asyncio.Event) -> None:
    if not _job_worker_enabled():
        logger.info("agent_job_worker disabled")
        return

    db_url = app.state.database_url
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    poll_seconds = _worker_poll_seconds()
    logger.info("agent_job_worker starting worker_id=%s", worker_id)

    while not stop.is_set():
        try:
            recovered = await recover_stale_agent_jobs(db_url)
            if recovered["recovered"] or recovered["failed"]:
                logger.warning("agent_job_worker recovered=%s failed=%s", recovered["recovered"], recovered["failed"])
            for terminal_job in recovered.get("terminal_jobs", []):
                try:
                    await _record_terminal_stale_job_failure(db_url, terminal_job)
                except Exception:
                    logger.exception(
                        "agent_job_worker failed to persist stale terminal job failure id=%s type=%s",
                        terminal_job.get("id"),
                        terminal_job.get("job_type"),
                    )

            job = await claim_next_agent_job(db_url, worker_id)
            if job is None:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
                except asyncio.TimeoutError:
                    pass
                continue

            heartbeat_stop = asyncio.Event()
            heartbeat_task = asyncio.create_task(
                _heartbeat_job(db_url, job["id"], worker_id, heartbeat_stop),
                name=f"agent-job-heartbeat-{job['id']}",
            )
            try:
                await process_claimed_job(app, job)
                await complete_agent_job(db_url, job["id"])
            except Exception as exc:
                outcome = await fail_agent_job(db_url, job["id"], error=str(exc))
                if outcome["terminal"]:
                    payload = job.get("payload") or {}
                    if job["job_type"] == "agent_run":
                        await record_agent_run_failure(
                            db_url=db_url,
                            thread_id=job["thread_id"],
                            user_internal_id=job["user_id"],
                            route=route_from_payload(payload["route"]),
                            error=str(exc),
                        )
                    elif job["job_type"] == "approved_tool":
                        await record_approved_tool_failure(
                            db_url=db_url,
                            thread_id=job["thread_id"],
                            user_internal_id=job["user_id"],
                            approval=payload["approval"],
                            error=str(exc),
                        )
                logger.exception(
                    "agent_job_worker job_failed id=%s type=%s terminal=%s attempts=%s/%s",
                    job["id"],
                    job["job_type"],
                    outcome["terminal"],
                    outcome["attempts"],
                    outcome["max_attempts"],
                )
            finally:
                heartbeat_stop.set()
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task
        except Exception:
            logger.exception("agent_job_worker loop failure")
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                pass

    logger.info("agent_job_worker stopped worker_id=%s", worker_id)
