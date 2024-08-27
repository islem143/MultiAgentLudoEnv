from enum import Enum
import numpy as np
from typing import Dict, List, Tuple, Optional
from pettingzoo import AECEnv
from pettingzoo.utils import agent_selector
from gymnasium import spaces

class Player(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    YELLOW = "yellow"

NUM_PLAYERS = len(Player)
NUM_TOKENS = 4
OUT_OF_BOUNDS = -1
START_SQUARE = 0
FINAL_SQUARE = 58

class LudoEnv(AECEnv):
    metadata = {"render_modes": ["human"], "name": "ludo_v0"}

    def __init__(self):
        super().__init__()
        self.possible_agents = [player.value for player in Player]
        
        self.action_spaces = {agent: spaces.Discrete(5) for agent in self.possible_agents}
        self.observation_spaces = {
            agent: spaces.Dict({
                "board_state": spaces.Box(
                    low=OUT_OF_BOUNDS,
                    high=FINAL_SQUARE,
                    shape=(NUM_PLAYERS, NUM_TOKENS),
                    dtype=int,
                ),
                "current_player": spaces.Discrete(NUM_PLAYERS),
                "action_mask": spaces.Box(low=0, high=1, shape=(5,), dtype=int),
                "last_roll": spaces.Discrete(7),
            }) for agent in self.possible_agents
        }

        self.state: np.ndarray = np.full((NUM_PLAYERS, NUM_TOKENS), OUT_OF_BOUNDS, dtype=int)
        self.current_player: str = Player.RED.value
        self.dice_roll: int = 0
        self.agent_selection: str = self.current_player

        self.start_positions: List[int] = [0, 13, 26, 39]
        self.home_stretches: List[List[int]] = [
            list(range(51, 57)),
            list(range(12, 18)),
            list(range(25, 31)),
            list(range(38, 44)),
        ]

    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> None:
        self.state = np.full((NUM_PLAYERS, NUM_TOKENS), OUT_OF_BOUNDS, dtype=int)
        self.agents = self.possible_agents[:]
        self.current_player = Player.RED.value
        self.dice_roll = 0
        self._cumulative_rewards = {agent: 0 for agent in self.agents}
        self.agent_selection = self.current_player
        self._agent_selector = agent_selector(self.agents)
        self.rewards = {agent: 0 for agent in self.agents}
        self._dones = {agent: False for agent in self.agents}
        self.infos = {agent: {} for agent in self.agents}

    def step(self, action: int) -> None:
        if self._dones[self.agent_selection]:
            return self._was_done_step(action)

        agent = self.agent_selection
        player_index = self.possible_agents.index(agent)

        self.dice_roll = np.random.randint(1, 7)
        reward = 0

        if action == 0 and self.dice_roll == 6:  # Enter a token
            for token in range(NUM_TOKENS):
                if self.state[player_index][token] == OUT_OF_BOUNDS:
                    self.state[player_index][token] = self.start_positions[player_index]
                    break
        elif 1 <= action <= 4:  # Move a token
            token = action - 1
            if self.state[player_index][token] != OUT_OF_BOUNDS:
                new_pos = self._calculate_new_position(self.state[player_index][token], self.dice_roll)
                self.state[player_index][token] = new_pos
                
                captured = self._check_capture(new_pos)
                if captured:
                    reward += 1
                
                if new_pos == FINAL_SQUARE:
                    reward += 2

        self.rewards[agent] = reward
        self._cumulative_rewards[agent] += reward

        if self._check_game_over():
            self._dones = {agent: True for agent in self.agents}
        else:
            self.agent_selection = self._agent_selector.next()

    def observe(self, agent: str) -> Dict:
        return {
            "board_state": self.state,
            "current_player": self.possible_agents.index(self.agent_selection),
            "action_mask": self._mask_actions(agent),
            "last_roll": self.dice_roll,
        }

    def render(self) -> None:
        print(f"Current state:")
        for i, player_pieces in enumerate(self.state):
            print(f"Player {self.possible_agents[i]}: {player_pieces}")
        print(f"Current player: {self.agent_selection}")
        print(f"Last dice roll: {self.dice_roll}")

    def _calculate_new_position(self, current_pos: int, steps: int) -> int:
        if current_pos < 52:  # On the main track
            new_pos = (current_pos + steps) % 52
            player_index = self.possible_agents.index(self.agent_selection)
            if new_pos in self.home_stretches[player_index]:
                # Enter home stretch
                return 52 + (new_pos - self.home_stretches[player_index][0])
            return new_pos
        elif current_pos < 57:  # In the home stretch
            new_pos = current_pos + steps
            return min(new_pos, 58)  # Cap at 58 (finished)
        return current_pos  # Already finished

    def _check_capture(self, position: int) -> Optional[Tuple[int, int]]:
        if position in self.start_positions:
            return None  # Starting positions are safe

        current_player_index = self.possible_agents.index(self.agent_selection)
        for player in range(NUM_PLAYERS):
            if player != current_player_index:
                for piece in range(NUM_TOKENS):
                    if self.state[player][piece] == position:
                        # Capture occurred
                        self.state[player][piece] = OUT_OF_BOUNDS
                        return (player, piece)

        return None  # No capture occurred

    def _mask_actions(self, agent: str) -> np.ndarray:
        mask = np.zeros(5, dtype=int)
        player_index = self.possible_agents.index(agent)
        
        # if player has any out of bounds pieces and has rolled a 6 then action is allowed
        if np.any(self.state[player_index] == OUT_OF_BOUNDS) and self.dice_roll == 6:
            mask[0] = 1
        
        # if player has a piece inside the board and their dice roll doesn't overshoot final square then action is allowed
        for token in range(NUM_TOKENS):
            if START_SQUARE <= self.state[player_index][token] <= FINAL_SQUARE - self.dice_roll:
                mask[token + 1] = 1
        
        return mask

    def _check_game_over(self) -> bool:
        return any(np.all(player_pieces == FINAL_SQUARE) for player_pieces in self.state)

    def close(self) -> None:
        pass

if __name__ == "__main__":
    env = LudoEnv()
    env.reset()

    for _ in range(100):
        action = env.action_spaces[env.agent_selection].sample()
        env.step(action)
        env.render()
        
        if all(env._dones.values()):
            break

    env.close()