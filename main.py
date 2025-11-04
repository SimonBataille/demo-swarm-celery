from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tasks import add, slow_double
from celery.result import AsyncResult
import os

app = FastAPI(title="Celery + Redis demo")

class AddPayload(BaseModel):
    x: int
    y: int

class DoublePayload(BaseModel):
    x: int

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/tasks/add")
def create_add_task(payload: AddPayload):
    r = add.delay(payload.x, payload.y)
    return {"task_id": r.id, "status": "queued"}

@app.post("/tasks/double")
def create_double_task(payload: DoublePayload):
    r = slow_double.delay(payload.x)
    return {"task_id": r.id, "status": "queued"}

@app.get("/tasks/{task_id}")
def get_task_result(task_id: str):
    # NB: la config backend est lue via l'objet Celery importé dans tasks.py
    result = AsyncResult(task_id)
    state = result.state
    if state == "PENDING":
        return {"task_id": task_id, "state": state}
    if state == "FAILURE":
        # on renvoie l'info d’erreur (sans stacktrace détaillée)
        return {"task_id": task_id, "state": state, "error": str(result.info)}
    # states possibles: STARTED, RETRY, SUCCESS
    return {"task_id": task_id, "state": state, "result": result.result}