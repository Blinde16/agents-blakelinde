# UX Copy Guidelines

The system's tone directly influences user trust. Systems built for business execution must sound reliable, deterministic, and slightly technical—never whimsical.

## General Voice Rules
- **No Personification**: The system must not refer to itself with names. (e.g., Avoid: "Hi! I'm your CFO agent.").
- **Direct Operational Phrasing**: (e.g., Use: "Routing to Finance layer. Checking margin tables...").
- **Conciseness**: Remove introductory pleasantries ("Sure thing! Let me just..."). Get straight to the data.

## Polling & System States
When the UI is waiting on the Python backend, utilize these precise strings in the UI Loader:
- `Processing input...` (Default initial hit)
- `Routing request...` (Evaluating the Classifier)
- `Querying databases...` (Executing safe tools)
- `Awaiting human approval...` (Interrupt before executing payload)

## Error States
A failure should provide an exact boundary explanation, rather than generic AI confusion.
- **Bad**: "I'm sorry, I couldn't figure that out right now."
- **Good**: "System Execution Failure: Unable to locate the specified HubSpot ID. Please verify the client name."
- **Good**: "Approval Timeout: Action disregarded."

## UI Elements
- **Action Cards**: 
  - Title: "[System] Proposed Operation"
  - Primary Button: `Confirm & Execute`
  - Secondary Button: `Reject`
