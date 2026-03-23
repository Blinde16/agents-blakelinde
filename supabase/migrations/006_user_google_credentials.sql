-- Per-user Google OAuth refresh token (encrypted in app) for Gmail + Calendar tools.

CREATE TABLE IF NOT EXISTS public.user_google_credentials (
    user_id UUID PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    refresh_token_cipher TEXT NOT NULL,
    google_email TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
