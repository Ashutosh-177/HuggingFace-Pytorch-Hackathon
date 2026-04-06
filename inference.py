"""
Inference script for Incident Response Triage OpenEnv.
Uses OpenAI client against API_BASE_URL / MODEL_NAME.
Emits [START], [STEP], [END] structured logs as required.
"""

import os
import json
import time
import requests
from openai import OpenAI

# ── Config from environment variables ──────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN",     "")
ENV_URL      = os.environ.get("ENV_URL",       "http://localhost:7860")

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

TASKS = ["task_easy", "task_medium", "task_hard"]

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) responding to a production incident in a microservices system.

You receive alerts, service metrics, and log entries. Your job is to diagnose the root cause and resolve the incident efficiently.

AVAILABLE COMMANDS (respond with ONLY the command, no explanation):
  INVESTIGATE <service>           - View recent logs for a service
  CHECK_METRICS <service>         - View CPU, memory, latency, error metrics
  CHECK_DEPENDENCIES <service>    - View upstream/downstream service dependencies
  RESTART <service>               - Restart a service
  SCALE <service> <count>         - Scale a service to N instances
  ROLLBACK <service>              - Roll back to the previous deployment version
  FLUSH_CACHE                     - Clear the Redis cache
  INCREASE_CONNECTIONS <service>  - Increase the database connection pool
  DIAGNOSE <root_cause>           - Submit your root cause diagnosis
  RESOLVE <summary>               - Mark the incident as resolved (only after fixing it)

SERVICES: web-frontend, api-gateway, auth-service, user-service, order-service, payment-service, notification-service, database, cache, message-queue

STRATEGY:
1. Read the alerts carefully - identify the most critical issues
2. Investigate affected services (check logs and metrics)
3. Trace dependencies to find the root cause
4. Submit your diagnosis with DIAGNOSE
5. Apply the correct remediation action
6. Resolve the incident with RESOLVE

Respond with EXACTLY ONE command per turn. No explanation, no extra text - just the command."""


def format_observation(obs: dict) -> str:
    """Format observation into a readable prompt for the LLM."""
    lines = ["=== CURRENT INCIDENT STATUS ==="]

    # Alerts
    lines.append("\n📢 ACTIVE ALERTS:")
    for a in obs.get("alerts", []):
        sev = a["severity"].upper()
        lines.append(f"  [{sev}] {a['service']}: {a['message']} (at {a['timestamp']})")

    # Service dashboard (only show non-healthy or key services)
    lines.append("\n📊 SERVICE DASHBOARD:")
    for svc, m in sorted(obs.get("services", {}).items()):
        status = m.get("status", "unknown")
        if status != "healthy" or m.get("error_rate_percent", 0) > 1:
            lines.append(
                f"  {svc:25s} | CPU: {m['cpu_percent']:5.1f}% | Mem: {m['memory_percent']:5.1f}% "
                f"| Latency: {m['request_latency_ms']:6.0f}ms | Errors: {m['error_rate_percent']:5.1f}% "
                f"| Status: {status}"
            )
            if m.get("last_deployment"):
                lines.append(f"  {'':25s}   └─ Last deploy: {m['last_deployment']}")

    # Last action result
    if obs.get("action_result"):
        lines.append(f"\n📋 LAST ACTION RESULT:\n{obs['action_result']}")

    lines.append(f"\n⏱ Step {obs['step_number']}/{obs['step_number'] + obs['steps_remaining']}")
    return "\n".join(lines)


def get_action(obs: dict, history: list) -> str:
    """Ask the LLM for the next command given current observation."""
    user_msg = format_observation(obs)
    if history:
        user_msg += "\n\nPREVIOUS ACTIONS:\n" + "\n".join(history[-5:])
    user_msg += "\n\nWhat is your next command?"

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=60,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
        )
        action = response.choices[0].message.content.strip()
        # Clean up: take only the first line
        action = action.split("\n")[0].strip()
        if not action:
            action = "INVESTIGATE web-frontend"
        return action
    except Exception as e:
        print(f"[LLM ERROR] {e}", flush=True)
        return "INVESTIGATE web-frontend"


def run_task(task_id: str) -> float:
    """Run a single task end-to-end, return score 0.0–1.0."""
    # Reset
    res = requests.post(f"{ENV_URL}/reset", json={"task_id": task_id})
    res.raise_for_status()
    data = res.json()
    obs = data["observation"]

    total_reward = 0.0
    step_num = 0
    rewards = []
    history = []

    print(json.dumps({
        "type": "[START]",
        "task_id": task_id,
        "env": "incident-response-triage",
        "model": MODEL_NAME,
        "alerts_count": len(obs.get("alerts", [])),
        "max_steps": obs["step_number"] + obs["steps_remaining"],
    }), flush=True)

    while not obs.get("done", False) and obs.get("steps_remaining", 0) > 0:
        action = get_action(obs, history)

        step_res = requests.post(f"{ENV_URL}/step", json={"command": action})
        step_res.raise_for_status()
        step_data = step_res.json()

        reward  = step_data["reward"]
        obs     = step_data["observation"]
        done    = step_data["done"]
        message = step_data["message"]

        total_reward += reward
        rewards.append(reward)
        step_num += 1

        print(json.dumps({
            "type": "[STEP]",
            "step": step_num,
            "action": action,
            "reward": reward,
            "total_reward": round(total_reward, 4),
            "done": done,
            "message": message[:120],
        }), flush=True)

        history.append(f"Step {step_num}: {action} → reward {reward:+.4f}")

        if done:
            break

    # Get final state for scoring
    state_res = requests.get(f"{ENV_URL}/state")
    state_data = state_res.json()
    milestones = state_data.get("milestones_achieved", {})
    score = max(0.0, min(1.0, total_reward))
    success = score >= 0.5

    print(json.dumps({
        "type": "[END]",
        "task_id": task_id,
        "success": success,
        "total_steps": step_num,
        "total_reward": round(total_reward, 4),
        "score": round(score, 4),
        "rewards": [round(r, 4) for r in rewards],
        "milestones": milestones,
    }), flush=True)

    return score


def main():
    print("=" * 60)
    print("Incident Response Triage — Inference Script")
    print("=" * 60)

    all_scores = {}
    for task_id in TASKS:
        print(f"\n{'─' * 40}")
        print(f"Running task: {task_id}")
        print(f"{'─' * 40}")
        score = run_task(task_id)
        all_scores[task_id] = score
        time.sleep(1)

    print("\n" + "=" * 60)
    print("Final Scores:")
    for task_id, score in all_scores.items():
        print(f"  {task_id}: {score:.4f}")
    avg = sum(all_scores.values()) / len(all_scores)
    print(f"  Average Score: {avg:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
