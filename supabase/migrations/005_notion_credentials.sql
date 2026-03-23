-- Per-user Notion integration (encrypted token in app layer; optional content DB id).

CREATE TABLE IF NOT EXISTS public.user_notion_credentials (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    token_cipher TEXT NOT NULL,
    content_database_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
