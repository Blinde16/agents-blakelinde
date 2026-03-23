-- pgvector for CMO RAG; finance read models for CFO tools.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source ON public.knowledge_chunks (source);

CREATE TABLE IF NOT EXISTS public.finance_client_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_key TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    margin_pct NUMERIC NOT NULL,
    revenue_ytd NUMERIC NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.finance_revenue_totals (
    timeframe TEXT PRIMARY KEY,
    total_revenue NUMERIC NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.finance_client_metrics (client_key, display_name, margin_pct, revenue_ytd)
VALUES
    ('acme', 'Acme Corp', 68.5, 45000),
    ('contoso', 'Contoso Ltd', 42.0, 120000)
ON CONFLICT (client_key) DO NOTHING;

INSERT INTO public.finance_revenue_totals (timeframe, total_revenue)
VALUES ('YTD', 1250000), ('Q1', 310000), ('LAST_MONTH', 98000)
ON CONFLICT (timeframe) DO NOTHING;
