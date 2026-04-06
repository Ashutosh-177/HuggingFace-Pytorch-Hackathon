"""
Pydantic models for the Incident Response Triage OpenEnv environment.
Defines typed Observation, Action, State, and Reward models.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ServiceStatusEnum(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class Alert(BaseModel):
    id: str
    severity: AlertSeverity
    service: str
    message: str
    timestamp: str


class ServiceMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    request_latency_ms: float
    error_rate_percent: float
    active_connections: int
    instances: int = 1
    uptime_hours: float = 100.0
    status: ServiceStatusEnum
    last_deployment: Optional[str] = None


class Observation(BaseModel):
    alerts: List[Alert]
    services: Dict[str, Dict[str, Any]]
    action_result: str = ""
    step_number: int = 0
    steps_remaining: int = 15
    incident_resolved: bool = False
    task_id: str = "task_easy"
    done: bool = False


class Action(BaseModel):
    command: str = Field(..., description="Text command, e.g. 'INVESTIGATE user-service'")


class StepOutput(BaseModel):
    observation: Observation
    reward: float
    done: bool
    message: str
    info: Dict[str, Any] = {}


class ResetInput(BaseModel):
    task_id: Optional[str] = "task_easy"


class ResetOutput(BaseModel):
    observation: Observation
    message: str


class State(BaseModel):
    observation: Observation
    milestones_achieved: Dict[str, bool] = {}
    total_reward: float = 0.0


class Task(BaseModel):
    id: str
    name: str
    description: str
    difficulty: str
    reward_range: List[float]
