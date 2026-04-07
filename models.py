from pydantic import BaseModel, ConfigDict
from typing import List, Literal, Optional

# --- Custom observation and action logic ---

class Observation(BaseModel):
    model_config = ConfigDict(strict=True)
    target_pos: List[float]       # [x, y, z] relative distance to target
    heading_error: float          # Deviation from target angle (radians)
    distance_to_target: float     # Euclidian distance
    stagnation_warn: bool         # Warning if the robot hasn't made progress
    message: str                  # Textual context for LLM

class Action(BaseModel):
    model_config = ConfigDict(strict=True)
    command: Literal["FORWARD", "BACKWARD", "TURN_LEFT", "TURN_RIGHT", "STOP"]

# --- OpenEnv Standard Spec Models ---

class State(BaseModel):
    model_config = ConfigDict(strict=True)
    task_id: Optional[str]
    total_reward: float
    steps_taken: int
    done: bool

class ResetInput(BaseModel):
    task_id: str = "task_easy"

class ResetOutput(BaseModel):
    observation: Observation

class StepOutput(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: dict = {}

class Task(BaseModel):
    id: str
    name: str
    description: str
    difficulty: str
    reward_range: List[float]
