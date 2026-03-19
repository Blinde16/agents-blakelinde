# System Architecture

## Overview
The architecture is designed to bypass standard serverless timeout constraints for stateful LLM operations, ensuring complete control over the application state. It decouples the presentation layer from the runtime execution layer.

## High-Level Sequence & Components

### 1. Presentation Layer (Next.js / Vercel)
- **Framework**: Next.js App Router (React).
- **Authentication**: Clerk handles user identity and session tokens.
- **Responsibilities**: Renders the mobile-first UI, accepts text input, provides a "push-to-talk" Vapi interface, and renders Action Cards (pending approvals).
- **Communication Pipeline**: Calls the Python backend via REST APIs, passing an internal JWT for authorization. Next.js uses short polling (fetch loops via SWR) to query graph state and await node execution completion.

### 2. Orchestration Layer (Python / FastAPI / Always-on Worker)
- **Framework**: Python 3.11+, FastAPI, Agno AgentOS.
- **Hosting**: Render or Railway (Always-on service; prevents 60s termination applied by Vercel).
- **Responsibilities**: Maintains the Agno agents and orchestration logic. Receives API requests from the Next.js frontend, executes LLM logic (via OpenAI/Anthropic), evaluates tool definitions, and initiates state pauses when a tool requires approval.
- **Auth Strategy**: Next.js acts as an internal issuer and forwards a vetted JWT/API token to the FastAPI service to prove the user has valid access.  

### 3. Voice Transport (Vapi.ai)
- **Framework**: Vapi handles Speech-to-Text (STT) and Text-to-Speech (TTS), plus Voice Activity Detection (VAD).
- **Architecture Flow**:
  1. User talks into mobile browser (Vapi Web SDK).
  2. Vapi pings our FastAPI webhook (`/api/vapi_inbound`).
  3. **Thin Adapter**: FastAPI immediately acknowledges Vapi to prevent timeout, dropping the payload into a background task / orchestration boundary. 
  4. Agent processes the request, streaming or returning the outcome to Vapi for TTS speaking.

### 4. Data Layer (Supabase / Postgres)
- **Primary Data Store**:
  - `agent_memory` and `agent_storage`: Auto-managed by Agno `PgMemoryDb` and `PgAgentStorage`. 
  - `threads`: Metadata linking user sessions.
  - `approval_gates`: A robust table that records ID, thread, tool payload, and approval status (`PENDING`, `APPROVED`, `REJECTED`).
- **Knowledge Store**: Notion is utilized strictly as an external scoped knowledge adapter for the agents to query RAG documents. It is *not* used for operational session state.

### 5. Integrations & Tooling
- **HubSpot**: Connected via standard API token to the CRO agent.
- **Observability**: Hooked into Agno logging and potential Agno Cloud usage for full trace coverage.

## Architectural Tradeoffs
- **Polling vs WebSockets**: Polling adds slight latency to the UI reaction, but significantly simplifies Phase 1 deployment across isolated Vercel & Railway instances.
- **Fat Backend**: Moving intelligence entirely into Python makes the web app thin, meaning we could swap to a React Native mobile app in the future without rebuilding the reasoning layer.
