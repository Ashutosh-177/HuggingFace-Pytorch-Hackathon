"""
FastAPI server for the Incident Response Triage OpenEnv environment.
Exposes reset / step / state / tasks / grade endpoints.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from environment import IncidentResponseEnv
from models import (
    Action, StepOutput, ResetInput, ResetOutput, State, Task,
)

app = FastAPI(
    title="Incident Response Triage — OpenEnv",
    description=(
        "An OpenEnv-compliant environment simulating production incident "
        "response. AI agents act as SREs diagnosing and resolving real-world "
        "infrastructure incidents across a microservices architecture."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = IncidentResponseEnv()

TASKS = [
    Task(
        id="task_easy",
        name="Memory Leak Detection",
        description="Identify and resolve a memory leak in a single service with clear symptoms.",
        difficulty="easy",
        reward_range=[0.0, 1.0],
    ),
    Task(
        id="task_medium",
        name="Database Connection Exhaustion",
        description="Diagnose cascading failures caused by database connection pool exhaustion.",
        difficulty="medium",
        reward_range=[0.0, 1.0],
    ),
    Task(
        id="task_hard",
        name="Cascading Deployment Failure",
        description="Investigate a complex cascading failure with misleading symptoms from a bad deployment.",
        difficulty="hard",
        reward_range=[0.0, 1.0],
    ),
]

VALID_IDS = {t.id for t in TASKS}


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "env": "incident-response-triage"}


@app.post("/reset", response_model=ResetOutput, tags=["openenv"])
def reset(body: ResetInput = ResetInput()):
    if body.task_id not in VALID_IDS:
        raise HTTPException(400, f"task_id must be one of {sorted(VALID_IDS)}")
    return env.reset(task_id=body.task_id)


@app.post("/step", response_model=StepOutput, tags=["openenv"])
def step(body: Action):
    return env.step(command=body.command)


@app.get("/state", response_model=State, tags=["openenv"])
def state():
    return env.state()


@app.get("/tasks", response_model=list[Task], tags=["openenv"])
def tasks():
    return TASKS


@app.get("/grade/{task_id}", tags=["grading"])
def grade(task_id: str):
    if task_id not in VALID_IDS:
        raise HTTPException(400, f"task_id must be one of {sorted(VALID_IDS)}")
    score = env.grade(task_id)
    return {"task_id": task_id, "score": score, "reward_range": [0.0, 1.0]}
