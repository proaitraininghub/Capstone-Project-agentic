import os

from celery_app import celery_app
import tasks  # noqa: F401  (importing it registers the job)

if __name__ == "__main__":
    concurrency = os.environ.get("WORKER_CONCURRENCY", "4")
    celery_app.worker_main(["worker", "--loglevel=info", f"--concurrency={concurrency}"])