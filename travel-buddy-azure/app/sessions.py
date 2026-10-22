"""
sessions.py  --  CHAT MEMORY THAT SURVIVES AND IS SHARED
=========================================================
Before: chat history lived in a Python dictionary inside ONE running app.
        A restart wiped it, and a second copy of the app could not see it.

Now:    the history is saved in Redis under the key  tb:session:<session_id>.
        ANY worker, on ANY replica, can load it, answer, and save it back.
        It disappears by itself after SESSION_TTL_SECONDS of silence.

The agent framework can turn a session into plain JSON (session.to_dict())
and back again (AgentSession.from_dict(...)). We just store that JSON text.
"""
import json
import os

SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "3600"))
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "20"))


def session_key(session_id):
    return f"tb:session:{session_id}"


def lock_key(session_id):
    return f"tb:lock:{session_id}"


def trim_history(session_dict):
    """Sliding window (the idea from step 11): keep only the newest messages so the history,
    the cost and the delay do not grow forever. We cut so the history always starts with a
    USER message, so a tool call is never separated from its result."""
    memory = session_dict.get("state", {}).get("in_memory", {})
    messages = memory.get("messages")
    if messages and len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]
        while messages and messages[0].get("role") != "user":
            messages.pop(0)
        memory["messages"] = messages
    return session_dict


def seeded_session_json(session_id, question, answer):
    """Build a session that already contains one question and answer.
    Used when the answer came from the cache, so a follow-up question still has context."""
    return json.dumps({
        "type": "session",
        "session_id": session_id,
        "service_session_id": None,
        "state": {"in_memory": {"messages": [
            {"role": "user", "contents": [{"type": "text", "text": question, "additional_properties": {}}],
             "additional_properties": {}, "type": "message"},
            {"role": "assistant", "contents": [{"type": "text", "text": answer, "additional_properties": {}}],
             "author_name": "TravelBuddy", "additional_properties": {}, "type": "message"},
        ]}},
    })
