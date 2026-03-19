# Deployment Strategy

The deployment separates stateful workloads from presentation rendering to sidestep platform constraints.

## 1. Vercel (Frontend Next.js)
- **Role**: Compiles and serves the React UI. Handles Clerk callbacks.
- **Deployment**: Automatic branch pipelines from GitHub. Serverless Next.js. Maps strictly to `agents.blakelinde.com`.

## 2. Railway / Render (Backend Python)
- **Role**: Always-on hosting environment. Avoids serverless "sleep" and webhook timeouts.
- **Deployment**: `Dockerfile` mapping installing `.txt` requirements and exposing Uvicorn on port `8000`. Scale 1 instance vertically to handle LLM I/O bursts. Map to internally accessible URL or subdomain api.blakelinde.com strictly protected by Service Tokens.

## 3. Supabase (Postgres Database)
- **Role**: Long term durable storage.
- **Deployment**: Managed hosted instance. The `langgraph-checkpoint-postgres` library can automatically run migrations, or we will manage explicit schema structures using standard Supabase CLI migrations during CI pipelines.

## 4. Environment Variables Map
### Next.js (Vercel)
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `INTERNAL_SERVICE_KEY_SIGNER` (Shared via env, signed JWT string wrapper)

### Python (Railway)
- `OPENAI_API_KEY` (or Anthropic key)
- `LANGCHAIN_API_KEY` (for LangSmith Tracing)
- `DATABASE_URL` (Supabase Connection String)
- `HUBSPOT_API_KEY` (Scoped read/write token)
- `NOTION_API_KEY` (Scoped integration token)
- `INTERNAL_SERVICE_KEY_SIGNER` (Same key, mapped to decoder for auth validation)
