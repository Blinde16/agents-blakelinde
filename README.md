# Blake Linde Agents Platform (`agents.blakelinde.com`)

## Vision
The Blake Linde Agents Platform is an operational command center using the **OpenClaw** architectural framework. It serves as a personal AI assistant embedded in standard messaging platforms (like Slack) without the need for a web dashboard.

This framework is built for highly reliable, skill-based execution while maintaining strict control boundaries for deterministic mutating steps.

## Core Tenets
1. **Deterministic Execution First**: Avoid LLM "magic" where rules suffice.
2. **Execution with Permission**: State-mutating actions (updating CRM deals, scheduling events, sending emails) require explicit human approval via simple conversational [Y/N] prompts.
3. **No Cross-Domain Mutation**: Maintain strict boundaries across systems so errors don't chain across layers.

## Architecture
This project is built to run locally (or on a lightweight VPS) using the OpenClaw structure:
- **Gateway**: Routes messages directly from Slack to the core runtime.
- **Identity**: Configured entirely via `SOUL.md` (Domain logic) and `AGENTS.md` (Security constraints).
- **Context**: Tracked natively via `USER.md` and automated updates to `MEMORY.md`.
- **Skills**: Tools are modularized into the `skills/` directory, exposing raw python CLIs and logic explicitly mapped out in `SKILL.md` instruction files for OpenClaw.

## Skills Included
- `google-workspace`: Gmail & Google Calendar interactions.
- `hubspot`: Deal querying and pipeline state management.
- `finance`: Postgres-driven staging metric ingestion and KPI lookups.
- `notion`: Content calendar CRUD operations.
- `social-media`: Cross-platform post generation and execution.
