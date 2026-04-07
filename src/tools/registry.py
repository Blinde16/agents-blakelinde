from dataclasses import dataclass

@dataclass(frozen=True)
class ToolRuntimeContext:
    thread_id: str
    db_url: str
    user_internal_id: str
