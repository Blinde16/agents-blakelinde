---
name: Google Workspace
description: Interact with Gmail and Google Calendar (Read, Draft, Send, Schedule).
---

# Google Workspace Skill

This skill allows you to control the user's Google Workspace inbox and calendar.

## Usage

You have access to the legacy Python implementations in `scripts/google_workspace.py`.

**Functions Available:**
- Email: `execute_send_email`, `execute_trash_message`, `execute_modify_email_labels`
- Calendar: `execute_create_calendar_event`, `execute_update_calendar_event`, `execute_delete_calendar_event`

**IMPORTANT APPROVAL RULE:**
You MUST check with the user before sending an email, trashing an email, or modifying calendar events. Always present the drafted email or exact event details to the user and request a [Y/N] approval. Only execute the python code upon receiving confirmation.
