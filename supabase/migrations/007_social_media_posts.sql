-- Social queue: draft → schedule → publish (publish only after in-app approval).

CREATE TABLE IF NOT EXISTS public.social_media_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    scheduled_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    external_post_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT social_media_posts_status_check CHECK (
        status IN ('draft', 'scheduled', 'published', 'cancelled')
    )
);

CREATE INDEX IF NOT EXISTS idx_social_posts_user_status
    ON public.social_media_posts (user_id, status);
