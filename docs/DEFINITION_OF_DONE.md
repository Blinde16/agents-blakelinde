# Definition of Done (MVP Go-Live)

To exit the MVP creation phase and declare the system usable by Blake in real-world scenarios, the following conditions must be met:

## 1. Hosting Parity
- Next.js application runs cleanly on `agents.blakelinde.com`. 
- Clerk intercepts traffic completely.
- FastAPI python instance runs securely, shielded from the public web via explicit JWT `X-Service-Token` headers.

## 2. Graph Stability
- LangGraph officially stores and retrieves session memory natively inside the Supabase Postgres context. `thread_id` continuity works across multiple browser reloads.
- The `interrupt_before` execution pause holds indefinitely without crashing the application until the human approves or rejects it in Next.js.

## 3. Integrations Operability
- **HubSpot**: CRO Agent can read and move a designated test deal without 500 API errors.
- **Notion**: CMO agent successfully retrieves text from a locked workspace Notion page via Integration Token.
- **Postgres**: CFO agent successfully runs a strict read-only SQL metric calculation via safe tool wrappers.

## 4. Voice Mechanics
- Vapi webhook adapter correctly receives text, bypasses URL timeouts, executes asynchronously, and pushes synthesized text back to Vapi successfully.

## 5. Tracing
- A run logged in LangSmith correctly visualizes: `Router` -> `Agent` -> `Tool Call` -> `End`.
