"""
celery_app.py  --  THE JOB QUEUE
=================================
Celery is the "waiting line" between the web API and the AI work.

   Browser --> FastAPI --(put a job on the queue)--> Redis <--(take a job)-- Celery WORKER --> model

Why not call the model inside the API request?
   * One chat takes 3 to 20 seconds. The API would hold a connection open all that time.
   * If 500 people ask at once, the model's rate limit (429 errors) would be hit all at once.
   * With a queue, the API answers instantly ("got it, job id 123"), and a limited number of
     workers (you choose how many) feed the model at a pace it can handle.

Both the API and the worker import this file, so they use the same settings.
"""
import os
import ssl

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "travelbuddy",
    broker=REDIS_URL,    # where waiting jobs are kept
    backend=REDIS_URL,   # where finished answers are kept for a while
)

celery_app.conf.update(
    # Plain JSON only (safe and easy to read). Never use pickle with data from users.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",

    # Report "running" (STARTED) so the API can tell waiting jobs from running jobs
    task_track_started=True,

    # RELIABILITY: only mark a job as done AFTER it finishes. If a worker is killed half-way
    # (for example the container is replaced during a scale-in), the job goes back on the queue.
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # FAIRNESS: each worker process takes ONE job at a time (no hoarding a pile of jobs).
    worker_prefetch_multiplier=1,

    # SAFETY: no job may run forever. Soft limit raises an error we can catch, hard limit kills it.
    task_soft_time_limit=75,
    task_time_limit=90,

    # Finished answers disappear from Redis after one hour (keeps Redis small)
    result_expires=3600,

    # Keep trying to reach Redis when the worker starts, instead of crashing
    broker_connection_retry_on_startup=True,

    # Must be LONGER than the hard time limit above (seconds)
    broker_transport_options={
        "visibility_timeout": 600,
        "socket_keepalive": True,
        "health_check_interval": 30,
    },
    redis_backend_health_check_interval=30,
    redis_socket_keepalive=True,
)

# Azure Managed Redis only accepts encrypted connections (URL starts with rediss://).
# Celery needs to be told to use TLS for BOTH the broker and the result backend.
if REDIS_URL.startswith("rediss://"):
    celery_app.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    celery_app.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
