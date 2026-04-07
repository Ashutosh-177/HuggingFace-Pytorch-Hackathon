"""
FastAPI server for the Isaac Sim Robotics OpenEnv environment.
Exposes reset / step / state / tasks / grade endpoints.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Initialize environment logic (this will handle Isaac app launcher internally if available)
from environment import IncidentResponseEnv as IsaacNavigationEnv
from models import (
    Action, StepOutput, ResetInput, ResetOutput, State, Task,
)

app = FastAPI(
    title="Isaac Sim Navigation — OpenEnv",
    description=(
        "An OpenEnv-compliant robotics environment wrapping NVIDIA Isaac Sim. "
        "AI agents must navigate a physical Turtlebot to reach targets while dodging obstacles."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = IsaacNavigationEnv()

TASKS = [
    Task(
        id="task_easy",
        name="Empty Room Navigation",
        description="Navigate a Turtlebot through an empty room directly to a target cone.",
        difficulty="easy",
        reward_range=[0.0, 1.0],
    ),
    Task(
        id="task_medium",
        name="Static Obstacle Corridor",
        description="Navigate through a narrow corridor avoiding static boxes to reach the target.",
        difficulty="medium",
        reward_range=[0.0, 1.0],
    ),
    Task(
        id="task_hard",
        name="Dynamic Obstacle Corridor",
        description="Navigate a corridor while dodging dynamically moving obstacles to reach the target.",
        difficulty="hard",
        reward_range=[0.0, 1.0],
    ),
]

VALID_IDS = {t.id for t in TASKS}


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "env": "isaac-navigation-openenv"}


@app.post("/reset", response_model=ResetOutput, tags=["openenv"])
def reset(body: ResetInput = ResetInput()):
    if body.task_id not in VALID_IDS:
        raise HTTPException(400, f"task_id must be one of {sorted(VALID_IDS)}")
    state = env.reset(task_id=body.task_id)
    return {"observation": env.get_observation().model_dump()}


@app.post("/step", response_model=StepOutput, tags=["openenv"])
def step(body: Action):
    result = env.step(command=body.command)
    return result


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
