# Contributing to `agents.blakelinde.com`

## Branch Strategy
1. **`main`**: Represents the live production MVP.
2. **`dev`**: Integration branch for new tools or UI adjustments.
3. **Feature Branches**: E.g. `feat/cmo-agent-notion-rag`, `fix/vapi-webhook-timeout`.

## Workflow
1. Create a feature branch off `main`.
2. Implement backend requirements strictly mapping to `/docs/AGNO_ARCHITECTURE.md`. If architecture must change, *update the docs first*.
3. Test locally against the `_dev` Supabase database.
4. Open a Pull Request.

## Pull Request Requirements
- Must provide an Agno Workspace trace URL demonstrating a successful run.
- Must not introduce any synchronous/blocking HTTP requests within Python.
- Must ensure that any new mutating Action implements the `Approval Wrapper` UX component natively.
- UI changes must render cleanly on Chrome Mobile layout.

## Environment Boundaries
Do not commit keys. Ensure `.env.example` remains updated. Note that `INTERNAL_SERVICE_KEY_SIGNER` must be matched identically in the `.env` of the `/web` directory and the `/agent` directory to allow local cross-testing.
