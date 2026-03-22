-- 002_agent_runtime_state.sql
-- Adds persistent runtime state for agent execution and thread message history.

CREATE TABLE IF NOT EXISTS public.thread_runs (
    thread_id UUID PRIMARY KEY REFERENCES public.threads(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'idle',
    active_agent TEXT,
    pending_approval BOOLEAN NOT NULL DEFAULT FALSE,
    approval_gate_id UUID,
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.thread_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.thread_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.thread_messages ENABLE ROW LEVEL SECURITY;
