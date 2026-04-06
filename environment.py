"""
Core environment logic for Incident Response Triage.
Implements reset() / step() / state() per OpenEnv spec.
"""

import copy
from typing import Any, Dict, Tuple

from models import (
    Observation, StepOutput, ResetOutput, State, Alert, Action,
)
from scenarios import SCENARIOS, SERVICES, DEPENDENCY_GRAPH


class IncidentResponseEnv:
    """Simulates a production incident that an SRE agent must diagnose & resolve."""

    def __init__(self):
        self.task_id: str = "task_easy"
        self.scenario: dict = {}
        self.services: Dict[str, dict] = {}
        self.alerts: list = []
        self.milestones: Dict[str, bool] = {}
        self.milestone_rewards: Dict[str, float] = {}
        self.steps_taken: int = 0
        self.max_steps: int = 15
        self.total_reward: float = 0.0
        self.done: bool = False
        self.incident_resolved: bool = False
        self.last_action_result: str = ""
        self.investigated_services: set = set()
        self.remediation_applied: bool = False
        self.secondary_applied: bool = False
        self.diagnosis_submitted: bool = False

    # ------------------------------------------------------------------ reset
    def reset(self, task_id: str = "task_easy") -> ResetOutput:
        self.task_id = task_id
        self.scenario = SCENARIOS[task_id]
        self.services = copy.deepcopy(self.scenario["services"])
        self.alerts = copy.deepcopy(self.scenario["alerts"])
        self.milestone_rewards = dict(self.scenario["milestones"])
        self.milestones = {k: False for k in self.milestone_rewards}
        self.steps_taken = 0
        self.max_steps = self.scenario["max_steps"]
        self.total_reward = 0.0
        self.done = False
        self.incident_resolved = False
        self.last_action_result = "Environment reset. Review the alerts and begin your investigation."
        self.investigated_services = set()
        self.remediation_applied = False
        self.secondary_applied = False
        self.diagnosis_submitted = False
        return ResetOutput(observation=self._obs(), message="Environment reset.")

    # ------------------------------------------------------------------- step
    def step(self, command: str) -> StepOutput:
        if self.done:
            return StepOutput(
                observation=self._obs(), reward=0.0, done=True,
                message="Episode finished. Call reset().")

        reward = -0.01  # small step cost
        parts = command.strip().split(maxsplit=1)
        action = parts[0].upper() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        # dispatch
        if action == "INVESTIGATE":
            r, msg = self._do_investigate(arg)
        elif action == "CHECK_METRICS":
            r, msg = self._do_check_metrics(arg)
        elif action == "CHECK_DEPENDENCIES":
            r, msg = self._do_check_deps(arg)
        elif action == "RESTART":
            r, msg = self._do_restart(arg)
        elif action == "SCALE":
            r, msg = self._do_scale(arg)
        elif action == "ROLLBACK":
            r, msg = self._do_rollback(arg)
        elif action == "FLUSH_CACHE":
            r, msg = self._do_flush_cache()
        elif action == "INCREASE_CONNECTIONS":
            r, msg = self._do_increase_conn(arg)
        elif action == "DIAGNOSE":
            r, msg = self._do_diagnose(arg)
        elif action == "RESOLVE":
            r, msg = self._do_resolve(arg)
        else:
            r, msg = -0.03, f"Unknown command '{action}'. Available: INVESTIGATE, CHECK_METRICS, CHECK_DEPENDENCIES, RESTART, SCALE, ROLLBACK, FLUSH_CACHE, INCREASE_CONNECTIONS, DIAGNOSE, RESOLVE"

        reward += r
        self.total_reward += reward
        self.steps_taken += 1
        self.last_action_result = msg

        if self.steps_taken >= self.max_steps and not self.done:
            self.done = True
            msg += " | Max steps reached."

        return StepOutput(
            observation=self._obs(), reward=round(reward, 4),
            done=self.done, message=msg)

    # ------------------------------------------------------------------ state
    def state(self) -> State:
        return State(
            observation=self._obs(),
            milestones_achieved={k: v for k, v in self.milestones.items()},
            total_reward=round(self.total_reward, 4))

    # ----------------------------------------------------------------- grader
    def grade(self, task_id: str) -> float:
        """Run a scripted optimal agent and return score 0.0-1.0."""
        self.reset(task_id)
        scenario = SCENARIOS[task_id]
        for cmd in scenario["optimal_actions"]:
            if self.done:
                break
            self.step(cmd)
        score = self._compute_score()
        return round(score, 4)

    # ========================== command handlers ==========================

    def _do_investigate(self, service: str) -> Tuple[float, str]:
        service = self._normalise_service(service)
        if service not in SERVICES:
            return -0.02, f"Unknown service '{service}'. Valid: {', '.join(SERVICES)}"
        self.investigated_services.add(service)
        logs = self.scenario["logs"].get(service)
        if logs:
            result = f"=== Logs for {service} ===\n{logs}"
        else:
            result = f"=== Logs for {service} ===\n[No anomalies detected. Service operating normally.]"
        return self._check_investigation_milestones(service), result

    def _do_check_metrics(self, service: str) -> Tuple[float, str]:
        service = self._normalise_service(service)
        if service not in SERVICES:
            return -0.02, f"Unknown service '{service}'."
        self.investigated_services.add(service)
        m = self.services.get(service, {})
        lines = [f"=== Metrics for {service} ==="]
        lines.append(f"  CPU:          {m.get('cpu_percent', 0):.1f}%")
        lines.append(f"  Memory:       {m.get('memory_percent', 0):.1f}%")
        lines.append(f"  Latency p99:  {m.get('request_latency_ms', 0):.0f} ms")
        lines.append(f"  Error rate:   {m.get('error_rate_percent', 0):.1f}%")
        lines.append(f"  Connections:  {m.get('active_connections', 0)}")
        lines.append(f"  Instances:    {m.get('instances', 1)}")
        lines.append(f"  Status:       {m.get('status', 'unknown')}")
        if m.get("last_deployment"):
            lines.append(f"  Last deploy:  {m['last_deployment']}")
        return self._check_investigation_milestones(service), "\n".join(lines)

    def _do_check_deps(self, service: str) -> Tuple[float, str]:
        service = self._normalise_service(service)
        if service not in SERVICES:
            return -0.02, f"Unknown service '{service}'."
        deps = DEPENDENCY_GRAPH.get(service, [])
        rev = [s for s, d in DEPENDENCY_GRAPH.items() if service in d]
        lines = [f"=== Dependencies for {service} ==="]
        lines.append(f"  Depends on: {', '.join(deps) if deps else 'none'}")
        lines.append(f"  Depended on by: {', '.join(rev) if rev else 'none'}")
        r = self._award("traced_dependencies", self.milestone_rewards.get("traced_dependencies", 0))
        return r, "\n".join(lines)

    def _do_restart(self, service: str) -> Tuple[float, str]:
        service = self._normalise_service(service)
        if service not in SERVICES:
            return -0.02, f"Unknown service '{service}'."
        sc = self.scenario
        if sc["remediation_action"] == "RESTART" and service == sc["remediation_target"]:
            self._apply_fix(service)
            r = self._award("correct_remediation",
                            self.milestone_rewards.get("correct_remediation", 0))
            return r, f"Service '{service}' restarted successfully. Metrics returning to normal."
        return -0.05, f"Service '{service}' restarted, but this did not resolve the incident."

    def _do_scale(self, arg: str) -> Tuple[float, str]:
        parts = arg.split()
        service = self._normalise_service(parts[0]) if parts else ""
        if service not in SERVICES:
            return -0.02, f"Unknown service '{service}'."
        return -0.03, f"Scaled '{service}', but this is not the correct remediation."

    def _do_rollback(self, service: str) -> Tuple[float, str]:
        service = self._normalise_service(service)
        if service not in SERVICES:
            return -0.02, f"Unknown service '{service}'."
        sc = self.scenario
        if sc["remediation_action"] == "ROLLBACK" and service == sc["remediation_target"]:
            self._apply_fix(service)
            key = "correct_primary_remediation" if "correct_primary_remediation" in self.milestones else "correct_remediation"
            r = self._award(key, self.milestone_rewards.get(key, 0))
            return r, f"Rolled back '{service}' to previous stable version. Errors decreasing."
        return -0.05, f"Rolled back '{service}', but this did not help."

    def _do_flush_cache(self) -> Tuple[float, str]:
        sc = self.scenario
        if sc.get("secondary_remediation") and sc["secondary_remediation"][0] == "FLUSH_CACHE":
            self.secondary_applied = True
            r = self._award("correct_secondary_remediation",
                            self.milestone_rewards.get("correct_secondary_remediation", 0))
            return r, "Cache flushed. Stale entries cleared."
        return 0.0, "Cache flushed. No significant effect observed."

    def _do_increase_conn(self, service: str) -> Tuple[float, str]:
        service = self._normalise_service(service)
        if service not in SERVICES:
            return -0.02, f"Unknown service '{service}'."
        sc = self.scenario
        if sc["remediation_action"] == "INCREASE_CONNECTIONS" and service == sc["remediation_target"]:
            self._apply_fix(service)
            r = self._award("correct_remediation",
                            self.milestone_rewards.get("correct_remediation", 0))
            return r, f"Connection pool increased for '{service}'. Active connections stabilizing."
        return -0.03, f"Increased connections for '{service}', but this is not the issue."

    def _do_diagnose(self, diagnosis: str) -> Tuple[float, str]:
        self.diagnosis_submitted = True
        diag_lower = diagnosis.lower()
        keywords = self.scenario["root_cause_keywords"]
        if any(kw in diag_lower for kw in keywords):
            r = self._award("correct_diagnosis",
                            self.milestone_rewards.get("correct_diagnosis", 0))
            return r, f"Diagnosis accepted: root cause correctly identified."
        return -0.05, "Diagnosis does not match the root cause. Continue investigating."

    def _do_resolve(self, summary: str) -> Tuple[float, str]:
        # Only award resolve if the correct remediation was applied
        if self.milestones.get("correct_remediation", False) or \
           self.milestones.get("correct_primary_remediation", False):
            self.incident_resolved = True
            self.done = True
            r = self._award("incident_resolved",
                            self.milestone_rewards.get("incident_resolved", 0))
            return r, f"Incident resolved! Summary: {summary}"
        # Partial resolve without proper remediation
        self.done = True
        return 0.0, "Incident marked as resolved, but the root cause was not properly remediated. No resolution credit."

    # ========================== internal helpers ==========================

    def _normalise_service(self, name: str) -> str:
        name = name.strip().lower().replace("_", "-")
        # fuzzy match
        for s in SERVICES:
            if name == s or name == s.replace("-", ""):
                return s
        return name

    def _award(self, milestone: str, value: float) -> float:
        if milestone in self.milestones and not self.milestones[milestone]:
            self.milestones[milestone] = True
            return value
        return 0.0

    def _check_investigation_milestones(self, service: str) -> float:
        sc = self.scenario
        reward = 0.0
        # Root service investigation
        if service == sc["root_cause_service"]:
            reward += self._award("investigated_root_service",
                                  self.milestone_rewards.get("investigated_root_service", 0))

        # Task-specific investigation milestones
        tid = self.task_id
        if tid == "task_easy":
            if service != sc["root_cause_service"]:
                reward += self._award("investigated_context",
                                      self.milestone_rewards.get("investigated_context", 0))
        elif tid == "task_medium":
            symptom_services = ["order-service", "payment-service", "api-gateway", "auth-service"]
            if service in symptom_services:
                reward += self._award("investigated_symptoms",
                                      self.milestone_rewards.get("investigated_symptoms", 0))
        elif tid == "task_hard":
            if service in ("web-frontend", "api-gateway"):
                reward += self._award("investigated_frontend",
                                      self.milestone_rewards.get("investigated_frontend", 0))
            if service == "order-service":
                reward += self._award("traced_to_backend",
                                      self.milestone_rewards.get("traced_to_backend", 0))
        return reward

    def _apply_fix(self, service: str):
        """Simulate service recovery after correct remediation."""
        self.remediation_applied = True
        self.services[service] = dict(
            cpu_percent=10, memory_percent=30, request_latency_ms=25,
            error_rate_percent=0, active_connections=20, instances=1,
            uptime_hours=0.01, status="healthy", last_deployment=None)
        # Heal downstream/upstream services
        for s_name, s_data in self.services.items():
            if s_data.get("status") in ("degraded", "down") and s_name != service:
                self.services[s_name]["status"] = "healthy"
                self.services[s_name]["error_rate_percent"] = max(0, s_data["error_rate_percent"] - 20)
                self.services[s_name]["request_latency_ms"] = max(30, s_data["request_latency_ms"] * 0.3)

    def _compute_score(self) -> float:
        achieved = sum(self.milestone_rewards[k] for k, v in self.milestones.items() if v)
        return max(0.0, min(1.0, achieved))

    def _obs(self) -> Observation:
        alert_objs = [Alert(**a) for a in self.alerts]
        return Observation(
            alerts=alert_objs,
            services=copy.deepcopy(self.services),
            action_result=self.last_action_result,
            step_number=self.steps_taken,
            steps_remaining=max(0, self.max_steps - self.steps_taken),
            incident_resolved=self.incident_resolved,
            task_id=self.task_id,
            done=self.done)
