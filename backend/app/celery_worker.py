import multiprocessing
import os
from celery import Celery

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Disable fork safety for macOS
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
multiprocessing.set_start_method("spawn", force=True)

celery_app = Celery(
    "mindcrunch",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_track_started=True,
    result_extended=True,
)

# Ensure tasks are registered
import app.tasks.process_file_job
