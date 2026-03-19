# Product Requirements Document (PRD)

## Project Context
`agents.blakelinde.com` is an AI operating layer for business execution. It replaces scattered systems with a unified command center capable of invoking specialized reasoning agents to execute business workflows.

## Problem Statement
Business operations—ranging from pipeline analysis to financial margin calculations—are fragmented across CRMs, ERPs, Notion, and email. Existing LLM frontends (like ChatGPT) cannot securely manipulate these isolated systems, lack robust identity/routing concepts, and are not designed around a rigid approval-driven workflow. Blake Linde needs a tailored, mobile-accessible layer that centralizes command over these business systems without sacrificing execution control.

## Target Audience
- **Primary (Phase 1)**: Blake Linde (Fractional SMB systems architect).
- **Secondary (Phase 2+)**: Future white-labeled clients requiring encapsulated internal operating systems. 

## Business Goals
1. **Accelerate specialized analysis**: Reduce time to answer financial and sales questions by routing them to specialized Agno Agents integrated directly with system databases.
2. **Execute with confidence**: Introduce a "Tool Calling with Approval" UX that guarantees state-mutating actions (e.g., sending emails, moving CRM deals) never occur without user sign-off.
3. **Voice-enabled Operation**: Enable hands-free operation via a low-latency voice interface while commuting or away from a desk.

## Core Use Cases
1. **Financial Quick-Check**: User opens the mobile app, taps the mic, asks "What were my gross margins on the recent consulting gig?". System invokes CFO agent, queries database, returns exact figures.
2. **CRM Action**: User types "Move the Acme deal to Closed Won and draft an onboarding sequence in HubSpot". Route to CRO Agent. Agent executes the move (with an approval gate), then generates copy.
3. **Ambiguous Triage**: User asks a generic question. System falls back to Ops agent, which asks clarifying questions without hallucinating random assumptions.

## Functional Requirements
- **Authentication**: Email/Social login via Clerk.
- **Role Routing**: The system must have a supervisor capable of identifying whether a prompt belongs to the CFO, CRO, CMO, or Ops agent.
- **Workflow State**: Users must be able to view their Chat History and resume interrupted workflows.
- **Voice Interactivity**: Dedicated voice transport capable of capturing transcripts and interrupting seamlessly.
- **Human-in-the-loop**: Next.js UI must display structured "Action Cards" for pending tool calls.

## Non-Functional Requirements
- **Latency**: Voice-to-Event adapter must acknowledge requests instantly, even if the Agno orchestration requires seconds to complete. 
- **Reliability**: The agent execution must be failure-tolerant, requiring a persistent memory store (`PgMemoryDb`).
- **Scale**: Although initially single-user, all data models must include `user_id` and an assumed placeholder `tenant_id` string for future expansion.
- **Traceability**: All agent reasoning steps must be tracked via Agno session runs and logging.

## Success Criteria (MVP)
- A deployed web app where user can log in, ask a question via text or voice.
- The system correctly routes the intent 95%+ of the time.
- Tool executions are accurately captured, paused, and approved in the UI.
- No autonomous outbound mutated state without an explicit `APPROVED` enum in the database.
