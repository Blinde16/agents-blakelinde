# Agent Playbooks

## Playbook: Standard Tool Approval
**Scenario**: User needs to alter a system state in HubSpot.

1. **User (Voice)**: "Update the Acme deal. Move it to Closed Won."
2. **Router**: Classifies as `CRO` layer target.
3. **CRO Agent**: Recognizes it needs to invoke `hubspot_update_deal_stage`. Requires `deal_id` (assumed found or searched prior) and `new_stage` (Closed Won string ID). 
4. **Execution Pause**: Graph hits the interrupt node. Tool marks itself `PENDING` in the database.
5. **Vapi (Voice)**: Adapter returns a TTS payload early: "I've queued that update. Awaiting your approval in the application."
6. **Next.js (Web)**: User views the screen. An Action Card appears: "Move Acme Deal to Closed Won".
7. **User (Web)**: Taps **[Approve]**.
8. **Graph Resume**: Python graph executes HubSpot API call, moves deal, and terminates sequence. 

## Playbook: Ambiguous Triage Fallback
**Scenario**: User provides highly generic instructions.

1. **User (Text)**: "Can we look into that one client thing we talked about?"
2. **Router**: Confidence across CMO, CFO, CRO is < 85%. Defaults to `Ops` Agent.
3. **Ops Agent**: Receives text. Agent understands it lacks structural target context.
4. **Escalation**: Ops hits limits and cannot invoke tools. Ops directly replies: "I am unable to identify the target client. Please specify the deal name or the financial project ID."
5. **Constraint Maintained**: The system did not blindly ping the database wasting tokens or guessing on a partial match.

## Playbook: Notion Scoped Fetch
**Scenario**: User requests context based on an internal standard operating procedure. 

1. **User (Text)**: "Draft a new email to an investor based on our standard brand narrative."
2. **Router**: Identifies `CMO` role (Brand messaging). 
3. **CMO Agent**: Uses `read_notion_brand_guidelines` tool passing its explicitly approved Notion context IDs.
4. **Resolution**: CMO agent builds text based exactly on retrieved RAG blocks rather than generic LLM memory, formatting output for the user.
