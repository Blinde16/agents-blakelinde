# Test Strategy

## 1. Backend: Tool Testing
- **Goal**: Ensure the atomic Python tools connecting to external APIs correctly shape inputs and handle failures.
- **Methodology**: Use standard `pytest` tests mocking specific responses from HubSpot, Notion, or Supabase.

## 2. Backend: Agent Orchestration Tests
- **Goal**: Verify the Lead Router logic correctly delegates to the CFO, CRO, CMO, or Ops agent based on different prompts.
- **Methodology**: Pass pre-defined string prompts into the `Lead_Router` directly. Validate the targeted agent selection.

## 3. Backend: Approval State Validation
- **Goal**: Ensure the workflow strictly captures pending state when hitting any mutated state tool (`hubspot_update_deal_stage`). 
- **Methodology**: Construct a mock state context where an Agent decides to execute a protected tool. Verify the Approval Wrapper outputs the pause signal memo and generates the database row.

## 4. Frontend: Flow Tests (UI)
- **Goal**: Verify state polling operates and renders Action Cards, and that clicking "Approve" triggers the correct API boundary.
- **Methodology**: Use Jest + React Testing Library to simulate the SWR polling state transitioning from `PENDING` -> `APPROVED`.

## 5. End-to-End Tracing
- **Goal**: Visual verification of complex agent interactions in development environments. 
- **Methodology**: Agno Run inspection. Run a development query, review the logs or Agno UI, ensure tool inputs did not hallucinate extra fields, and verify the run completes successfully.
