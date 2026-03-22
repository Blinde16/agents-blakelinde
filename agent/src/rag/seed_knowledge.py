"""One-shot embedding seed for knowledge_chunks (idempotent)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import asyncpg
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def _knowledge_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "knowledge"


async def _embed(client: AsyncOpenAI, text: str) -> list[float]:
    resp = await client.embeddings.create(model=_EMBED_MODEL, input=text)
    return list(resp.data[0].embedding)


def _to_vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


async def ensure_knowledge_seeded(db_url: str) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; skipping knowledge base seed.")
        return

    conn = await asyncpg.connect(db_url)
    try:
        try:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM public.knowledge_chunks WHERE embedding IS NOT NULL"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("knowledge_chunks not available: %s", exc)
            return
        if count is not None and int(count) > 0:
            return
    finally:
        await conn.close()

    kdir = _knowledge_dir()
    if not kdir.is_dir():
        logger.warning("Knowledge directory missing: %s", kdir)
        return

    files = sorted(kdir.glob("*.md"))
    if not files:
        logger.warning("No .md files under %s", kdir)
        return

    client = AsyncOpenAI(api_key=api_key)
    conn = await asyncpg.connect(db_url)
    try:
        for path in files:
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            vec = await _embed(client, text)
            vec_lit = _to_vector_literal(vec)
            await conn.execute(
                """
                INSERT INTO public.knowledge_chunks (source, content, metadata, embedding)
                VALUES ($1, $2, $3::jsonb, $4::vector)
                """,
                path.name,
                text,
                '{"kind": "markdown"}',
                vec_lit,
            )
            logger.info("embedded knowledge file %s", path.name)
    finally:
        await conn.close()
