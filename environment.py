import math
import random
import sys
from models import Observation, Action, State

# Global flag to track if we are running in real simulation or fallback mode
USE_REAL_ISAAC = False

try:
    # We attempt to import isaaclab. If we are running inside HF Spaces CPU container, 
    # this will fail gracefully and we will use the fallback mathematically simulated proxy environment.
    import isaaclab.sim as sim_utils
    # USE_REAL_ISAAC = True # Set manually if running on a local GPU
except ImportError:
    pass

class IncidentResponseEnv:
    def __init__(self):
        self.task_id = None
        self.steps = 0
        self.max_steps = 25
        self.total_reward = 0.0
        self.done = False

        # Internal state for the Mock mathematical robot (if Isaac is unavailable)
        self.robot_pos = [0.0, 0.0, 0.0]
        self.robot_heading = 0.0
        self.target_pos = [2.0, 2.0, 0.0]
        
        # Action space mapping to continuous velocities [v_left, v_right]
        self.action_map = {
            "FORWARD": (1.0, 1.0),
            "BACKWARD": (-1.0, -1.0),
            "TURN_LEFT": (-0.5, 0.5),
            "TURN_RIGHT": (0.5, -0.5),
            "STOP": (0.0, 0.0)
        }

    def reset(self, task_id: str) -> State:
        self.task_id = task_id
        self.steps = 0
        self.total_reward = 0.0
        self.done = False

        # Reset Mock Robot
        self.robot_pos = [0.0, 0.0, 0.0]
        self.robot_heading = 0.0
        
        if task_id == "task_easy":
            self.target_pos = [2.0, 0.0, 0.0]
        elif task_id == "task_medium":
            self.target_pos = [4.0, 2.0, 0.0]
        else:
            self.target_pos = [5.0, -3.0, 0.0]

        return self.state()

    def get_observation(self) -> Observation:
        dx = self.target_pos[0] - self.robot_pos[0]
        dy = self.target_pos[1] - self.robot_pos[1]
        dist = math.sqrt(dx**2 + dy**2)
        
        # Calculate heading error
        target_angle = math.atan2(dy, dx)
        heading_error = target_angle - self.robot_heading
        
        # Normalize heading error to [-pi, pi]
        heading_error = (heading_error + math.pi) % (2 * math.pi) - math.pi

        return Observation(
            target_pos=[dx, dy, 0.0],
            heading_error=heading_error,
            distance_to_target=dist,
            stagnation_warn=(self.steps > 15 and dist > 1.5),
            message="Robot sensors normal. Obstacles clear."
        )

    def step(self, command: str) -> dict:
        if self.done:
            return {"reward": 0.0, "done": True, "observation": self.get_observation().model_dump()}

        self.steps += 1
        
        # 1. Decode Action
        if command not in self.action_map:
            command = "STOP"
        
        v_left, v_right = self.action_map[command]
        
        # 2. Mathematical Mock Simulation Update
        # Assuming simple differential drive kinematics
        dt = 0.5
        v = (v_left + v_right) / 2.0
        omega = (v_right - v_left) / 1.0  # Simple wheelbase proxy
        
        self.robot_heading += omega * dt
        self.robot_pos[0] += v * math.cos(self.robot_heading) * dt
        self.robot_pos[1] += v * math.sin(self.robot_heading) * dt

        obs = self.get_observation()
        
        # 3. Calculate Reward (shaped)
        reward = -0.01  # time penalty
        if command == "FORWARD" and obs.distance_to_target < 5.0 and abs(obs.heading_error) < 0.5:
            reward += 0.1 # progressing towards target
            
        if obs.distance_to_target < 0.5:
            self.done = True
            reward += 10.0 # Reached target!
        elif self.steps >= self.max_steps:
            self.done = True

        self.total_reward += reward

        return {
            "reward": reward,
            "done": self.done,
            "observation": obs.model_dump()
        }

    def state(self) -> State:
        return State(
            task_id=self.task_id,
            total_reward=self.total_reward,
            steps_taken=self.steps,
            done=self.done
        )

    def grade(self, task_id: str) -> float:
        """
        Grader function to verify the task is solvable.
        We run a simple proportional controller to solve the mock env.
        """
        self.reset(task_id)
        while not self.done:
            obs = self.get_observation()
            if abs(obs.heading_error) > 0.3:
                action = "TURN_LEFT" if obs.heading_error > 0 else "TURN_RIGHT"
            else:
                action = "FORWARD"
            self.step(action)
        
        obs = self.get_observation()
        return 1.0 if obs.distance_to_target < 0.5 else 0.0
