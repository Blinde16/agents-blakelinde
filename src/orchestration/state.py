import json

async def create_approval_gate(db_url, thread_id, user_internal_id, tool_name, payload):
    print(f"APPROVAL_REQUIRED_SIGNAL: {tool_name}")
    print(f"PAYLOAD: {json.dumps(payload)}")
    return "gate_mocked"
