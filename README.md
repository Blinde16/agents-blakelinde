# Blake Linde Agents Platform (`agents.blakelinde.com`)

## Vision
The Blake Linde Agents Platform is a mobile-first, role-aware AI operating layer designed for practical business execution. It acts as a command center that utilizes an orchestrated team of specialized functional agents—CFO, CRO, CMO, and Ops. It is designed to interpret complex business requests, execute tool-based operations, request human-in-the-loop approvals for sensitive actions, and provide a seamless voice and text interface optimized for a mobile environment.

This system is built as a serious tool for a fractional systems architect, emphasizing structural predictability, rigid tool execution, and robust observability over unchecked generative autonomy.

## Core Tenets
1. **Deterministic Execution First**: Avoid LLM "magic" where rules suffice.
2. **Functional Identity**: Agents represent business layers (Finance, Sales) rather than pretending to be human personas.
3. **Execution with Permission**: State-mutating actions require explicit human approval via the Next.js UI.
4. **Mobile Native**: Voice and chat interfaces must operate flawlessly out-of-pocket on mobile devices.

## Architecture Summary
- **Frontend / Client Layer**: Next.js App Router (hosted on Vercel), featuring a mobile-first UI with Tailwind CSS. Authenticates via Clerk and polls the backend for agent state.
- **Orchestration / Backend Layer**: Python FastAPI running Agno AgentOS, hosted as an always-on service to handle long-running agent execution without Serverless timeout limitations. Next.js triggers the backend using short-lived internal service tokens.
- **State & Database**: PostgreSQL (Supabase). Utilizes Agno's `PgMemoryDb` and `PgAgentStorage` for persistent thread state, and stores metadata, users, and approval gates.
- **Voice Interface**: Vapi.ai acts as the voice transport, routing STT events via a thin webhook adapter to the async orchestration boundary.

## Repository Structure
- `/web`: The Next.js web application (React, Tailwind, Clerk).
- `/agent`: The Python FastAPI and Agno AgentOS orchestration service.
- `/docs`: Internal implementation documentation (Architecture, Scope, Constraints).
- `/supabase`: Database migrations and schema definitions.

## Documentation Map
Refer to the complete specifications in the `/docs` directory to understand the system dependencies and boundaries:
- **Product Definition**: `PRD.md`, `MVP_SCOPE.md`, `MOBILE_UX.md`, `ROADMAP.md`
- **Architecture & System**: `SYSTEM_ARCHITECTURE.md`, `AGNO_ARCHITECTURE.md`, `BACKEND_ARCHITECTURE.md`, `FRONTEND_ARCHITECTURE.md`, `VOICE_ARCHITECTURE.md`
- **Integration & Data**: `INTEGRATIONS.md`, `DATA_MODEL.md`, `MEMORY_STRATEGY.md`, `TOOL_CALLING_FRAMEWORK.md`
- **Agent Behavior**: `AGENT_DESIGN.md`, `ROUTING_STRATEGY.md`, `AGENT_PLAYBOOKS.md`, `PROMPT_STRATEGY.md`
- **DevOps & Standards**: `DEPLOYMENT.md`, `OBSERVABILITY.md`, `SECURITY_AND_GOVERNANCE.md`, `API_SURFACE.md`, `CODING_STANDARDS.md`, `TEST_STRATEGY.md`

## Development Setup
*(Placeholder - see `docs/BUILD_SEQUENCE.md` for exact initialization steps)*
