# Frontend Architecture

## Stack
- **Framework**: Next.js App Router.
- **Styling**: Tailwind CSS + Shadcn UI (accessible, lightweight building blocks).
- **Global State**: Zustand for UI toggles (e.g., tracking the active `thread_id`, the Vapi connection status).

## Component Architecture (Thin Presentation)
The UI is strictly presentation. It holds zero reasoning logic.
- `<ChatStream />`: Iterates over the `messages` array returned by the backend.
  - Renders `<TextBubble />` if it's normal conversational text.
  - Renders `<ActionCard />` if it's encountering a `PENDING` approval object in the state response.
- `<Controls />`: Exposes the text input and the Vapi microphone toggle.

## Next.js Data Fetching
- The frontend will rely exclusively on **HTTP Polling** as the Phase 1 solution for real-time reactivity in place of WebSockets.
- **SWR (Stale-While-Revalidate)** provides a continuous, efficient caching strategy for hitting the `GET /api/threads/{id}/state` endpoint every 1.5 seconds while the backend is marked `processing`.
- Polling stops immediately when the node state reaches `END` or encounters a state pause `interrupt_before`.

## Auth Structure
- Clerk `middleware.ts` routes anonymous users back to the index.
- A Next.js API route (e.g., `app/api/relay/route.ts`) will accept client-side requests from the Next.js UI, attach an internal JWT secret, and proxy the request to the Python backend to ensure credentials don't leak to the browser.
