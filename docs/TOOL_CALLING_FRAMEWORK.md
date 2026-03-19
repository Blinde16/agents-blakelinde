# Tool Calling Framework

This document standardizes how AI system actions communicate with external systems, ensuring a controlled, permission-based operating environment.

## 1. Tool Creation Standard
Under the Agno AgentOS framework, tools are standard Python functions with clear docstrings and type annotations. Agno parses these natively into LLM tool schemas.

```python
from pydantic import BaseModel, Field

def hubspot_update_deal_stage(deal_id: str, new_stage: str) -> str:
    """Updates the stage of a specific deal in HubSpot.
    
    Args:
        deal_id (str): The exact HubSpot deal ID
        new_stage (str): The target pipeline stage ID
    """
    # Logic runs here
    return f"Deal {deal_id} updated to {new_stage}"
```

## 2. The Approval Gate
Tools are tagged conceptually with metadata indicating risk. Any tool that alters information outside the platform requires explicit human-in-the-loop approval. Because Agno lacks native node-pausing mechanisms like LangGraph, we implement an **Approval Wrapper Tool**.

### Mechanics Flow:
1. LLM decides to execute `hubspot_update_deal_stage`.
2. The agent executes the Approval Wrapper Tool instead of directly executing the API call.
3. The Wrapper Tool writes an entry to the `approval_gates` Postgres table containing tool arguments and sets status `PENDING`.
4. The Wrapper Tool returns a string memo to the Agent: "Action paused. Waiting for human approval."
5. The frontend polls the `approval_gates` table.
6. User clicks "Approve" in the Next.js UI.
7. Frontend POSTs an internal auth token affirming the choice to the backend `/resume` endpoint.
8. The backend manually invokes the actual `hubspot_update_deal_stage` business logic, updates the Postgres status, and injects a final completion message into the Agno agent's `PgMemoryDb`.

## 3. Tool Failure and Retries
If a tool execution fails (e.g., API 500 error, invalid ID), the python function must catch the exception and return a structured text error message *back to the agent interface*, avoiding crashing the application. The system will relay the error back to the originating Agent, allowing the LLM to understand the failure and re-attempt or report failure to the user.

## 4. Idempotency Expectations
Because workflows can theoretically replay or loop during retries, mutating tools must be built idempotently. (e.g., if a deal is already in Stage X, moving it to Stage X returns success without breaking).
