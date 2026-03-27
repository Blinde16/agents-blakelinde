CREATE TABLE IF NOT EXISTS public.agent_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INT NOT NULL DEFAULT 100,
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    worker_id TEXT,
    heartbeat_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT agent_jobs_status_check CHECK (
        status IN ('queued', 'running', 'completed', 'failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_agent_jobs_status_available
    ON public.agent_jobs (status, available_at, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_agent_jobs_thread_created
    ON public.agent_jobs (thread_id, created_at DESC);
