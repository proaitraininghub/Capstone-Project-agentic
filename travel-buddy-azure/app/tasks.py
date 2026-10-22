"""
tasks.py  --  THE JOB THE WORKER RUNS
=====================================
One job type: "answer this chat message for this session".

What a worker does for each job:
   1. Take the session lock       (so two messages from one person do not overwrite each other)
   2. Load the chat history from Redis
   3. Ask the agent                (this is the slow part: the model call, and maybe tools)
   4. Save the new history to Redis
   5. Return the answer            (Celery stores it in Redis, the API hands it to the browser)

Start a worker:   celery -A celery_app:celery_app worker --loglevel=info --concurrency=4
"""
import asyncio
import json
import os

from celery.exceptions import SoftTimeLimitExceeded
from celery.signals import worker_process_init

from agent_framework import AgentSession
from agent_setup import build_agent, setup_monitoring
from celery_app import celery_app
from redis_util import get_sync
from sessions import SESSION_TTL_SECONDS, lock_key, session_key, trim_history

ANSWER_CACHE_TTL = int(os.environ.get("ANSWER_CACHE_TTL", "600"))
MODEL_TIMEOUT_SECONDS = 60


@worker_process_init.connect
def _init_worker_process(**kwargs):
    # Runs once inside every worker process, AFTER it has started (monitoring must be
    # set up after the process is created, not before).
    setup_monitoring("travel-buddy-worker")


def _looks_like_rate_limit(error):
    text = str(error).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


@celery_app.task(bind=True, name="tasks.run_chat", max_retries=3)
def run_chat(self, session_id, message, answer_cache_key=None):
    r = get_sync()
    agent = build_agent()

    try:
        # Only one job per session at a time
        with r.lock(lock_key(session_id), timeout=90, blocking_timeout=60):
            raw = r.get(session_key(session_id))
            if raw:
                session = AgentSession.from_dict(json.loads(raw))
            else:
                session = agent.create_session(session_id=session_id)

            result = asyncio.run(
                asyncio.wait_for(agent.run(message, session=session), timeout=MODEL_TIMEOUT_SECONDS)
            )

            r.set(
                session_key(session_id),
                json.dumps(trim_history(session.to_dict())),
                ex=SESSION_TTL_SECONDS,
            )
    except SoftTimeLimitExceeded:
        raise RuntimeError("The agent took too long.")
    except Exception as error:
        # The model said "slow down" (HTTP 429): wait, then put the job back in line.
        if _looks_like_rate_limit(error):
            raise self.retry(exc=error, countdown=5 * (2 ** self.request.retries))
        raise

    tools_used = []
    for msg in result.messages:
        for content in msg.contents:
            if content.type == "function_call":
                tools_used.append(content.name)

    output = {"session_id": session_id, "answer": result.text, "tools_used": tools_used, "cached": False}

    # Remember the answer, so the same first question from other users is free next time
    if answer_cache_key and ANSWER_CACHE_TTL > 0:
        r.set(answer_cache_key, json.dumps({"answer": result.text, "tools_used": tools_used}), ex=ANSWER_CACHE_TTL)

    return output
