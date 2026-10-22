"""
redis_util.py  --  ONE place that knows how to reach Redis
==========================================================
Redis plays FOUR jobs in this project. All of them use the same Redis server
and the same address (REDIS_URL). Each job uses its own key PREFIX so they never mix:

   Job                      Key prefix / who writes it          Why it needs Redis
   -----------------------  ----------------------------------  ---------------------------------------
   1. Celery BROKER         queue list "celery"  (Celery)       the waiting line of chat jobs
   2. Celery RESULT store   "celery-task-meta-*" (Celery)       where a worker leaves the finished answer
   3. Chat SESSIONS         "tb:session:<id>"                   every replica can continue any chat
   4. CACHE and LIMITS      "tb:wiki:*", "tb:answer:*",         save model/web calls, protect the quota
                            "tb:rate:*", "tb:lock:*"

We use ONE database (number 0) on purpose: Azure Managed Redis with a clustering policy
only offers database 0, so prefixes are how we keep the jobs apart.

REDIS_URL looks like:
   redis://localhost:6379/0                                  (your laptop)
   rediss://:<access-key>@<host>.redis.azure.net:10000/0     (Azure Managed Redis, TLS, note the double s)
"""
import os

import redis
import redis.asyncio as aredis

_sync_client = None
_async_client = None


def redis_url():
    return os.environ.get("REDIS_URL")


def get_sync():
    """Normal (blocking) Redis client. Used by the Celery worker and by the Wikipedia tool.
    Returns None when REDIS_URL is not set, so the tools still work on a laptop without Redis."""
    global _sync_client
    if _sync_client is None and redis_url():
        _sync_client = redis.Redis.from_url(
            redis_url(), decode_responses=True,
            socket_timeout=5, socket_connect_timeout=5,
            health_check_interval=30, socket_keepalive=True,
        )
    return _sync_client


def get_async():
    """Async Redis client. Used by the FastAPI app, which must never block while it waits for Redis."""
    global _async_client
    if _async_client is None:
        if not redis_url():
            raise RuntimeError("REDIS_URL is not set. The API needs Redis for sessions, cache and rate limits.")
        _async_client = aredis.Redis.from_url(
            redis_url(), decode_responses=True,
            socket_timeout=5, socket_connect_timeout=5,
            health_check_interval=30, socket_keepalive=True,
        )
    return _async_client
