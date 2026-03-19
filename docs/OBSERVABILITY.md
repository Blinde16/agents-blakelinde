# Observability

This architecture requires aggressive logging to ensure LLM behavior is auditable and tools aren't throwing silent exceptions.

## 1. LangSmith Integration (Required)
- **Scope**: Every invocation of the LangGraph `Supervisor` must emit a structured trace.
- **Setup**: The environment running the FastAPI backend must have `LANGCHAIN_TRACING_V2=true` and a valid `LANGCHAIN_API_KEY`.
- **Purpose**: Traces expose the exact inputs, tool payloads, and node transitions during complex escalations, allowing debugging of hallucinated arguments without digging through server text logs.

## 2. Usage & Action Logging (Database)
- Every system-mutating action successfully executed by the LangGraph application must leave a footprint in the Supabase database.
- The `action_audit_history` table (or similar) will record the `thread_id`, the user, the timestamp, and the JSON payload of the action taken (e.g., specific ID of moved deal).

## 3. Product Analytics 
- We will integrate **PostHog** specifically for the Next.js frontend to monitor actual usage patterns.
- **Focus Events**:
  - `Voice_Mic_Tapped`
  - `Approval_Granted`
  - `Approval_Rejected`
  - `Thread_Abandoned`
- This provides data regarding UI friction (e.g., do people routinely ignore approval cards, thus stalling graphs indefinitely?).

## 4. Error boundaries
- Sentry will wrap the Python FastAPI environment and the Next.js frontend to catch unhandled application exceptions independent of LLM hallucinations.
