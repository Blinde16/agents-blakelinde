# Open Questions & Resolved Constraints

This document previously contained uncertainties. Following technical review, core constraints are now locked in place. Remaining operational ambiguities should be tracked below:

## Resolved Directives
- **Voice Platform**: Vapi.
- **Approvals Mechanism**: Next.js HTTP polling from Postgres table updates.
- **Notion Rule**: Read-only Knowledge Adapter, isolated from the graph state context entirely.
- **Hosting Strategy**: Python backend deployed to an Always-On environment like Railway.
- **Auth Bridging**: Internal JWT Service token passing vetted claims between layers.

## Current Open Questions
1. **Tool Output Handling in Voice**: When a tool returns a massive JSON table (e.g., pipeline report), how do we gracefully render that visually on Next.js while the voice layer simply TTS says "I've loaded the report"?
   *Assumption*: The Python backend will need to push the UI payload directly to the frontend's database state separate from the Vapi TTS injection hook.
2. **Audio Overlap**: If a user speaks while an agent is mid-execution, does Vapi cancel the webhook or buffer it?
   *Assumption*: We must handle HTTP trace cancellations in FastAPI if Vapi sends a VAD interrupt event, ensuring we don't bill unnecessary tokens or finalize a mutant state.
