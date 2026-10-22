"""
app/main.py  --  THE WEB API (FastAPI)
======================================
The front door. It does NOT talk to the AI model. Its job is to be fast:

   POST /chat            check the message, check the user's rate limit, look in the answer cache,
                         otherwise put a job on the Celery queue and reply at once with a job id
   GET  /chat/{task_id}  ask "is my job finished?"  (the client repeats this every second or so)
   GET  /health          alive check (Azure restarts the container if this fails)
   GET  /ready           also checks Redis

Why two steps (submit, then poll)?  The model can take many seconds. If the API waited, a few
hundred waiting users would use up every connection. Now each request takes a few milliseconds.

Run on your laptop (needs a Redis, see README):
   uvicorn main:app --reload          and, in a second terminal:
   celery -A celery_app:celery_app worker --loglevel=info --pool=solo
"""
import hashlib
import json
import os
import re
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from celery.result import AsyncResult

load_dotenv()

from celery_app import celery_app          # noqa: E402  (after load_dotenv so REDIS_URL is read)
from redis_util import get_async           # noqa: E402
from sessions import SESSION_TTL_SECONDS, seeded_session_json, session_key  # noqa: E402

# ------------------------------------------------------------------
# SETTINGS (all can be changed with environment variables)
# ------------------------------------------------------------------
MAX_MESSAGE_LENGTH = 500
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10"))
ANSWER_CACHE_TTL = int(os.environ.get("ANSWER_CACHE_TTL", "600"))  # seconds. 0 turns it off

# Monitoring (optional): traces of every web request go to Application Insights
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    os.environ.setdefault("OTEL_SERVICE_NAME", "travel-buddy-api")
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"])

# ------------------------------------------------------------------
# INPUT GUARDRAIL (from Part 2, step 8): refuse bad messages BEFORE they cost any money
# ------------------------------------------------------------------
INJECTION_PATTERNS = [
    r"ignore (all |your |any )?(previous|prior|above) instructions",
    r"(reveal|show|print|repeat) .*(system|hidden|secret) (prompt|instructions)",
    r"you are now",
    r"pretend (to be|you are)",
]


def input_is_ok(message):
    if len(message) > MAX_MESSAGE_LENGTH:
        return False
    return not any(re.search(pattern, message, re.IGNORECASE) for pattern in INJECTION_PATTERNS)


app = FastAPI(title="Travel Buddy API")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class SubmitResponse(BaseModel):
    status: str                    # "queued" (poll for the result) or "done" (answer is included)
    session_id: str
    task_id: str | None = None
    answer: str | None = None
    tools_used: list[str] | None = None
    cached: bool = False


class ResultResponse(BaseModel):
    status: str                    # queued | running | retrying | done | failed
    session_id: str | None = None
    answer: str | None = None
    tools_used: list[str] | None = None
    cached: bool = False
    error: str | None = None


def who_is_calling(request: Request):
    """Work out WHO is asking, so each person gets their own rate limit.
    1. Container Apps sign-in (Entra ID) adds this header. It cannot be faked from outside.
    2. X-User-Id is a simple header for testing. Anyone can fake it, so do not trust it in production.
    3. Otherwise use the caller's IP address."""
    return (
        request.headers.get("x-ms-client-principal-id")
        or request.headers.get("x-user-id")
        or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
        or (request.client.host if request.client else "unknown")
    )


async def check_rate_limit(user):
    """Fixed-window limit: at most RATE_LIMIT_PER_MINUTE messages per person per minute.
    Redis INCR counts atomically, so it is correct even with many API replicas."""
    r = get_async()
    window = int(time.time() // 60)
    key = f"tb:rate:{user}:{window}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 70)
    if count > RATE_LIMIT_PER_MINUTE:
        retry_after = 60 - int(time.time() % 60)
        raise HTTPException(
            status_code=429,
            detail="You are sending messages too quickly. Please wait a moment.",
            headers={"Retry-After": str(retry_after)},
        )


def answer_cache_key(message):
    normalized = " ".join(message.lower().split())
    return "tb:answer:" + hashlib.sha256(normalized.encode()).hexdigest()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    try:
        await get_async().ping()
    except Exception:
        raise HTTPException(status_code=503, detail="Redis is not reachable.")
    return {"status": "ready"}


@app.post("/chat", response_model=SubmitResponse)
async def submit_chat(body: ChatRequest, request: Request, response: Response):
    # 1) Guardrail
    if not input_is_ok(body.message):
        raise HTTPException(status_code=400, detail="That message was blocked by the input guardrail.")

    # 2) Rate limit (per person)
    await check_rate_limit(who_is_calling(request))

    r = get_async()
    is_new_chat = body.session_id is None
    session_id = body.session_id or str(uuid.uuid4())

    # 3) Answer cache. Only for the FIRST message of a chat, because a later message depends
    #    on the conversation so far and cannot be shared between people.
    cache_key = None
    if is_new_chat and ANSWER_CACHE_TTL > 0:
        cache_key = answer_cache_key(body.message)
        saved = await r.get(cache_key)
        if saved:
            data = json.loads(saved)
            # Give this person a session that already holds the question and answer
            await r.set(session_key(session_id), seeded_session_json(session_id, body.message, data["answer"]),
                        ex=SESSION_TTL_SECONDS)
            return SubmitResponse(status="done", session_id=session_id, answer=data["answer"],
                                  tools_used=data["tools_used"], cached=True)

    # 4) Put the job on the queue and answer immediately
    task_id = str(uuid.uuid4())
    await run_in_threadpool(
        celery_app.send_task, "tasks.run_chat",
        args=[session_id, body.message, cache_key], task_id=task_id,
    )
    response.status_code = 202   # 202 Accepted = "received, still working"
    return SubmitResponse(status="queued", session_id=session_id, task_id=task_id)


@app.get("/chat/{task_id}", response_model=ResultResponse)
def get_result(task_id: str):
    # (a normal "def", so FastAPI runs it in a thread and Celery may wait on Redis safely)
    result = AsyncResult(task_id, app=celery_app)
    state = result.state

    if state == "SUCCESS":
        return ResultResponse(status="done", **result.result)
    if state in ("FAILURE", "REVOKED"):
        return ResultResponse(status="failed", error="The agent could not answer. Please try again.")
    if state == "STARTED":
        return ResultResponse(status="running")
    if state == "RETRY":
        return ResultResponse(status="retrying")
    return ResultResponse(status="queued")   # PENDING (also what you see for an unknown id)
