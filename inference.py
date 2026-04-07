import os
import time
import requests
import json
from openai import OpenAI

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.environ.get("HF_TOKEN",     "")
ENV_URL      = os.environ.get("ENV_URL",      "http://localhost:7860")

TASKS = ["task_easy", "task_medium", "task_hard"]
MAX_STEPS = 25

def print_log(log_dict):
    """Prints the required structured JSON logs strictly to stdout."""
    print(json.dumps(log_dict), flush=True)

def resolve_next_action(client, obs, context_history):
    """
    Asks the LLM for the next command based on sensor readings.
    """
    system_prompt = (
        "You are an AI brain controlling a simulated physical Turtlebot.\n"
        "Your goal is to navigate to the target coordinate while avoiding obstacles.\n"
        "You receive sensor data including your heading error and distance to target.\n"
        "Your available actions are EXACTLY ONE of the following keywords: \n"
        "FORWARD\nBACKWARD\nTURN_LEFT\nTURN_RIGHT\nSTOP\n\n"
        "If heading error is > 0.4, you should turn. If facing the target, move FORWARD."
    )
    
    prompt = f"SENSOR DATA:\nDistance to target: {obs['distance_to_target']}\nHeading error: {obs['heading_error']}\nEnvironment message: {obs['message']}\n\nWhat is your next command?"
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=10
        )
        action = response.choices[0].message.content.strip().upper()
        # Clean up output
        for valid in ["FORWARD", "BACKWARD", "TURN_LEFT", "TURN_RIGHT", "STOP"]:
            if valid in action:
                return valid
        return "STOP"
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        # Fallback proportional controller if API limit hits
        if obs['heading_error'] > 0.3:
            return "TURN_LEFT"
        elif obs['heading_error'] < -0.3:
            return "TURN_RIGHT"
        else:
            return "FORWARD"

def main():
    print("=" * 60)
    print("Isaac Sim Robotics Navigation — Inference Script")
    print("=" * 60)
    print()

    client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

    for task_id in TASKS:
        # 1. Reset Environment
        print(f"\\n{'─' * 40}\\nRunning task: {task_id}\\n{'─' * 40}")
        try:
            res = requests.post(f"{ENV_URL}/reset", json={"task_id": task_id})
            res.raise_for_status()
            obs = res.json()["observation"]
        except Exception as e:
            print(f"Failed to reset {task_id}: {e}")
            continue

        start_log = {
            "type": "[START]",
            "task_id": task_id,
            "env": "isaac-navigation-openenv",
            "model": MODEL_NAME,
            "max_steps": MAX_STEPS
        }
        print_log(start_log)

        total_reward = 0.0
        done = False
        context_history = []

        # 2. Run Episode
        for step_idx in range(1, MAX_STEPS + 1):
            action = resolve_next_action(client, obs, context_history)
            
            try:
                res = requests.post(f"{ENV_URL}/step", json={"command": action})
                res.raise_for_status()
                step_data = res.json()
            except Exception as e:
                print(f"Failed to execute step: {e}")
                break
                
            obs = step_data["observation"]
            reward = step_data["reward"]
            done = step_data["done"]
            total_reward += reward

            step_log = {
                "type": "[STEP]",
                "step": step_idx,
                "action": action,
                "reward": reward,
                "total_reward": total_reward,
                "done": done,
            }
            print_log(step_log)

            if done:
                break

            time.sleep(0.1) # Small delay for realism if someone is watching server logs

        # 3. End Episode
        end_log = {
            "type": "[END]",
            "task_id": task_id,
            "total_steps": step_idx,
            "final_reward": total_reward,
            "success": obs['distance_to_target'] < 0.5
        }
        print_log(end_log)

if __name__ == "__main__":
    main()
