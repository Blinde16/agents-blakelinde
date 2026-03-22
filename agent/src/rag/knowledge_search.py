"""pgvector-backed semantic search over seeded knowledge chunks."""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg
from openai import AsyncOpenAI

_EMBED_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


async def _embed(client: AsyncOpenAI, text: str) -> list[float]:
    resp = await client.embeddings.create(model=_EMBED_MODEL, input=text)
    return list(resp.data[0].embedding)


def _to_vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(x) for x in vec) + "]"


async def search_brand_knowledge(db_url: str, query: str, *, limit: int = 5) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return json.dumps(
            {"error": "OPENAI_API_KEY not set", "detail": "Cannot embed query for RAG."}
        )

    client = AsyncOpenAI(api_key=api_key)
    qvec = await _embed(client, query)
    vec_lit = _to_vector_literal(qvec)

    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(
            """
            SELECT source, content, metadata,
                   (embedding <=> $1::vector) AS dist
            FROM public.knowledge_chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            vec_lit,
            limit,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {
                "error": "vector_search_failed",
                "detail": str(exc),
                "hint": "Ensure pgvector extension and knowledge_chunks table exist.",
            }
        )
    finally:
        await conn.close()

    if not rows:
        return json.dumps({"results": [], "detail": "No embedded documents in knowledge base."})

    parts: list[str] = []
    for i, row in enumerate(rows, start=1):
        meta: Any = row["metadata"] or {}
        src = row["source"]
        parts.append(f"[{i}] source={src} metadata={json.dumps(meta)}\n{row['content']}")
    return "\n\n".join(parts)
