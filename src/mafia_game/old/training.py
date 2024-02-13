# Define the environment
import json
import logging
import os
from collections import deque

import torch

from mafia_game.logger import logger
from mafia_game.models import Role, Player, GameState, GameController, Team
from mafia_game.nn_policy import NeuralNetworkCitizenPolicy, MODEL_PATH
from mafia_game.policies import StaticMafiaPolicy
import torch.nn.functional as F
import random

logger.setLevel(logging.ERROR)
log_file = 'logs/training_progress.json'


class MafiaEnvironment():
    def __init__(self, policy, agent):
        self.citizen_policy = policy
        self.mafia_policy = StaticMafiaPolicy()
        self.agent = agent
        self.mafia_won = 0
        self.citizens_won = 0

    def reset(self):
        players = [Player(i, Role.CITIZEN, self.citizen_policy) for i in range(7)]
        players[0].learner = True
        players += [Player(i, Role.MAFIA, self.mafia_policy) for i in range(7, 10)]
        random.shuffle(players)
        for i, player in enumerate(players, 0):
            player.id = i
        game_state = GameState(players)
        self.game_controller = GameController(game_state, agent)

    def play(self, n_rounds=1) -> Role:
        for i in range(n_rounds):
            self.reset()
            winner = self.game_controller.start_game()
            if winner == Role.MAFIA:
                self.mafia_won += 1
            else:
                self.citizens_won += 1

        print(f"Mafia won: {self.mafia_won}, Citizens won: {self.citizens_won}")
        print(f"Citizens winrate: {self.citizens_won / n_rounds}")


class DQNAgent:
    def __init__(self, policy):
        self.policy = policy
        self.memory = {'nominate_player': deque(maxlen=10000),
                       'vote': deque(maxlen=10000),
                       'make_declarations': deque(maxlen=10000)}
        self.gamma = 0.97  # discount factor
        self.steps = 0
        self.episode = 0

    def select_action(self, state):
        # TODO: Implement epsilon-greedy action selection here
        pass

    def store_experience(self, state, action, next_state, reward, action_type):
        self.memory[action_type].append([state, action, next_state, reward])

    def update_target_net(self):
        self.policy.target_net.load_state_dict(self.policy.network.state_dict())

    def update_policy(self, batch_size, action_type, episode_done, total_reward):
        self.steps += 1

        if self.episode % 100 == 0 and episode_done:
            self.update_target_net()
            logger.setLevel(logging.INFO)
            logger.info(f"Saving model, updating target model. Total steps: {self.steps}")
            logger.setLevel(logging.ERROR)
            torch.save(self.policy.network, MODEL_PATH)

        if len(self.memory[action_type]) < batch_size:
            return
        batch_state, batch_action, batch_next_state, batch_reward = zip(*random.sample(self.memory[action_type], batch_size))

        """
        Shapes are:
        
        batch_state: torch.Size([32, 3034])
        batch_action: torch.Size([32, 94])
        batch_reward: torch.Size([32, 1])
        batch_next_state: torch.Size([32, 3034])
        
        state_action_values: torch.Size([32, 21])
        next_state_values: torch.Size([32])
        expected_state_action_values: torch.Size([32, 32])
        """

        batch_state = torch.stack(batch_state)
        batch_action = torch.stack(batch_action).long()
        batch_reward = torch.stack(batch_reward)
        batch_next_state = torch.stack(batch_next_state)

        # Compute Q(s_t, a) - the model computes Q(s_t), then we select the
        # columns of actions taken. These are the actions which would've been taken
        # for each batch state according to policy_net

        declaration_out, voting_out, nominating_out = self.policy.network(batch_state)

        actions = {'make_declarations': declaration_out,
                   'vote': voting_out,
                   'nominate_player': nominating_out}

        state_action_values = (actions[action_type] * batch_action).sum(dim=1)

        # Compute V(s_{t+1}) for all next states.
        # Expected values of actions for non_final_next_states are computed based
        # on the "older" target_net; selecting their best reward with max(1)[0].
        # This is merged based on the mask, such that we'll have either the expected
        # state value or 0 in case the state was final.

        declaration_out, voting_out, nominating_out = self.policy.target_net(batch_next_state)
        actions = {'make_declarations': declaration_out,
                   'vote': voting_out,
                   'nominate_player': nominating_out}

        next_state_values = actions[action_type].max(1)[0].detach()
        # Compute the expected Q values
        expected_state_action_values = (next_state_values * self.gamma) + batch_reward.squeeze()

        # Compute Huber loss
        loss = self.policy.criterion(state_action_values, expected_state_action_values)

        # Optimize the model
        self.policy.optimizer.zero_grad()
        loss.backward()
        for param in self.policy.network.parameters():
            if param.grad is not None:
                param.grad.data.clamp_(-1, 1)
        self.policy.optimizer.step()

        if episode_done:
            self.policy.epsilon *= self.policy.epsilon_decay
            if self.policy.epsilon < 0.05:
                self.policy.epsilon = 0.05

            self.episode += 1
            with open(log_file, 'a') as f:
                json.dump({
                    'loss': loss.item(),
                    'reward': total_reward,
                    'epsilon': self.policy.epsilon
                }, f)
                f.write('\n')


# Define the agent

policy = NeuralNetworkCitizenPolicy(num_players=10)
agent = DQNAgent(policy)
env = MafiaEnvironment(policy, agent)

env.play(500000)
