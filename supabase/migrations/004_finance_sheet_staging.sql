-- User-scoped spreadsheet staging for CFO tools (CSV/XLSX ingest).

CREATE TABLE IF NOT EXISTS public.finance_sheet_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    upload_id UUID NOT NULL,
    filename TEXT NOT NULL,
    row_index INT NOT NULL,
    row_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_finance_staging_user_upload
    ON public.finance_sheet_staging (user_id, upload_id);

CREATE INDEX IF NOT EXISTS idx_finance_staging_upload_row
    ON public.finance_sheet_staging (upload_id, row_index);
