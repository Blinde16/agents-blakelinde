# Voice Architecture

We leverage **Vapi** as the frontend and transport mechanism for speech recognition, Voice Activity Detection (VAD), and text-to-speech rendering, avoiding the overhead of WebRTC internals.

## Integration Architecture
Integrating Vapi natively with Agno AgentOS requires bypassing Vapi's internal LLM orchestration so we maintain full control over our agent execution, tools, and approvals.

### 1. The Thin Event Adapter (Webhook)
Vapi acts purely as an audio transport. It receives spoken audio, transcribes it, and sends a `Server Message` to our FastAPI backend.
- **Endpoint**: `POST /api/webhooks/vapi`
- **Behavior**: The webhook receives the transcript. To prevent Vapi from timing out during deep orchestration, our API returns an immediate acknowledgment response (or a filler payload: `{"message": "Routing request..."}`). 
- **Async Boundary**: The transcript is placed on an async Python `asyncio` Task or a lightweight queue (`BackgroundTasks`).

### 2. Processing and State
The Python background task instantiates or resumes the user's Agno `thread_id` session and processes the transcript string just as if it were a typed chat.
- Lead Router delegates to Agent.
- Agent generates completion text.

### 3. Pushing State Back
Because we decoupled the request to prevent timeouts, we use Vapi's REST API to inject the final system response into the ongoing call asynchronously.
- **Action**: Our backend executes `POST https://api.vapi.ai/call/{id}/message` containing the agent's textual output.
- **Result**: Vapi synthesizes the text into speech and plays it to the user.

## Handling Interruptions
If the agent halts for a Tool Approval, the backend pushes a message to Vapi: _"I need your approval in the app before I can proceed."_
The user cannot "speak" an approval because of security validation. They must physically tap the UI to resume the agent workflow.

## Mobile Considerations
- Vapi's Web SDK will be instantiated inside the Next.js frontend via a persistent Floating Action Button ("Talk Mode").
- Audio context must not interrupt phone-level notifications; request AudioFocus gracefully.
