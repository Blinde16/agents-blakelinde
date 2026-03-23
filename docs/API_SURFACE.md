# API Surface

This architecture defines explicit service boundaries to separate the Next.js frontend clients from the LangGraph execution environment.

## Frontend to Orchestration Boundary
**Transport**: Next.js connects via standard HTTP REST. Internal auth checks the `X-Service-Token` header.
- `POST /api/threads` → Instantiates a new Postgres checkpoint thread ID and returns it.
- `POST /api/threads/{thread_id}/messages` → Pushes human text input strings into the graph. Returns a `{ status: "processing" }` 202 acknowledgment.
- `GET /api/threads/{thread_id}/state` → The frontend continuously polls this endpoint every 2s. The endpoint returns current `active_agent`, persisted chat text, runtime `status`, and the payload for any `PENDING` tool approvals.
- `POST /api/threads/{thread_id}/approve` → The frontend pushes a body like `{"decision": "APPROVED"}` returning the graph to active processing status. 

## External Webhooks
**Transport**: Exposed and validated via external provider keys.
- `POST /api/webhooks/vapi` → Vapi pings this url with transcript payloads via `Server Message`. The endpoint immediately responds 200 OK. A python `BackgroundTasks` thread grabs the payload, searches for the matching `thread_id` associated with the call, and invokes the orchestration boundary natively across the server.

The API design is stateless strictly speaking. The application state is exclusively sourced from the underlying Postgres checkpointers read during subsequent requests.
