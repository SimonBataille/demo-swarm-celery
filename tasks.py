import os
import time
from celery import Celery

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

app = Celery(
    "demo_app",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
)

@app.task
def add(x: int, y: int) -> int:
    return x + y

@app.task
def slow_double(x: int) -> int:
    time.sleep(3)  # simule une tâche lourde
    return 2 * x