---
name: HubSpot CRM Operations
description: Queries and updates deal stages within HubSpot.
---

# HubSpot Skill

This skill allows you to interact with HubSpot CRM. You can list deals, query pipeline details, and update deal stages.

## Usage

There is a Python module available at `scripts/hubspot.py` that contains the core logic previously used for tool calling. You have local python execution capabilities. To use the HubSpot functions, you can invoke them via `python -c` or write a quick wrapper script if necessary.

**Available functions in `scripts/hubspot.py`:**
- `execute_hubspot_update_deal_stage(deal_id: str, new_stage: str)`: Mutates deal stages.

**IMPORTANT APPROVAL RULE:**
Even though you run on OpenClaw now, you MUST check with the user before actually executing `execute_hubspot_update_deal_stage`. Describe what you are going to do, ask [Y/N] for approval, and only if they say yes, execute the python function.
