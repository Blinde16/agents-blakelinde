import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.orchestration.context_engine import prepare_user_intent


def test_resolves_archive_followup_from_recent_ids() -> None:
    history = [
        {
            "role": "assistant",
            "content": (
                "Running:\n"
                "- get_email_message(message_id=19d1baab153df622)\n"
                "- get_email_message(message_id=19d1aa2480d81bdc)"
            ),
        }
    ]
    decision = prepare_user_intent("archive both of these", prior_context={}, history=history)
    assert decision.direct_action == "archive_email_bulk"
    assert decision.message_ids == ["19d1baab153df622", "19d1aa2480d81bdc"]
    assert decision.domain == "OPS"


def test_uses_context_ids_for_followup() -> None:
    prior = {"selected_email_message_ids": ["abc12345", "def67890"]}
    decision = prepare_user_intent("mark them read", prior_context=prior, history=[])
    assert decision.direct_action == "mark_email_read_bulk"
    assert decision.message_ids == ["abc12345", "def67890"]


def test_keeps_unknown_without_context() -> None:
    decision = prepare_user_intent("archive those", prior_context={}, history=[])
    assert decision.direct_action is None
    assert decision.intent == "archive"
