import logging
import os
import random

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np

from mafia_game.logger import logger
from mafia_game.models import Policy, GameActionType, Role

INPUT_LAYER_SIZE = 3025
MODEL_PATH = f'{os.getcwd()}/../../model_weights/policy_model.pth'


if torch.cuda.is_available():
    device = torch.device('cuda')
    torch.set_default_tensor_type('torch.cuda.FloatTensor')
else:
    device = torch.device('cpu')
    torch.set_default_tensor_type('torch.FloatTensor')


class MultiHeadNetwork(nn.Module):
    def __init__(self, input_size, hidden_size, num_players):
        super(MultiHeadNetwork, self).__init__()

        # Shared layers
        self.shared_layers = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU()
        )

        # Declaration head
        self.declaration_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, num_players * 2 * 3 + 1),
            nn.Softmax(dim=1)
        )

        # Voting head
        self.voting_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, num_players),
            nn.Softmax(dim=1)
        )

        # Nominating head
        self.nominating_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, num_players + 1),
            nn.Softmax(dim=1)
        )

    def forward(self, x):
        shared_out = self.shared_layers(x)

        declaration_out = self.declaration_head(shared_out)
        voting_out = self.voting_head(shared_out)
        nominating_out = self.nominating_head(shared_out)

        return declaration_out, voting_out, nominating_out


class NeuralNetworkCitizenPolicy(Policy):
    policy_name = "NeuralNetworkCitizenPolicy"

    def __init__(self, num_players):
        self.num_players = num_players
        try:
            logger.info("Loading model...")
            self.network = torch.load(MODEL_PATH).to(device)
            self.target_net = torch.load(MODEL_PATH).to(device)
        except Exception:
            logger.error("Error in loading model")
            self.network = MultiHeadNetwork(INPUT_LAYER_SIZE, INPUT_LAYER_SIZE, num_players).to(device)
            self.target_net = MultiHeadNetwork(INPUT_LAYER_SIZE, INPUT_LAYER_SIZE, num_players).to(device)

        self.optimizer = optim.Adam(self.network.parameters(), lr=0.00025)
        self.criterion = nn.MSELoss()
        self.epsilon = 1
        self.epsilon_decay = 0.995

    def get_output_size(self, action_type):
        output_size = {"make_declarations": self.num_players * 3 * 2 + 1,
                       "vote": self.num_players,
                       "nominate_player": self.num_players + 1}
        return output_size[action_type]

    def get_action_vector(self, state_vector, action_type):
        if random.random() < self.epsilon:
            # Generate a random action vector
            action_vector = torch.rand(self.get_output_size(action_type))
        else:
            # Use the network to generate the action vector
            with torch.no_grad():
                declaration_vector, voting_vector, nominating_vector = self.network(state_vector.unsqueeze(0))
                if action_type == 'nominate_player':
                    action_vector = nominating_vector
                elif action_type == 'vote':
                    action_vector = voting_vector
                elif action_type == 'make_declarations':
                    action_vector = declaration_vector

        return action_vector.squeeze(0)

    def _get_declarations_from_vector(self, action_vector, game_state):
        # The action vector should already be masked, so we just need to find the indices of the maximum values.
        # These indices correspond to the declarations that the agent has decided to make.
        top_indices = torch.topk(action_vector, 3).indices  # Get the indices of the top 3 values
        declarations = []
        for index in top_indices:
            if index < 60:
                target = game_state.players[index % 10]
                belief = index % 20 // 10
                if belief == 0:
                    belief = Role.MAFIA
                else:
                    belief = Role.CITIZEN

                declarations.append((target, belief))

        return declarations, top_indices

    def _get_vote_from_vector(self, action_vector, game_state):
        if not game_state.nominated_players:
            return None, None

        vote_index = torch.argmax(action_vector).item()
        voted_player = game_state.players[vote_index]

        return voted_player, torch.Tensor([vote_index])

    def _get_kill_from_vector(self, action_vector):
        # TODO: Implement this method to convert the output vector of the network into a kill
        pass

    def _get_nomination_from_vector(self, action_vector, game_state):

        nomination_index = torch.argmax(action_vector).item()

        if nomination_index < 10:
            nominated_player = game_state.players[nomination_index]
        else:
            nominated_player = None  # The agent has decided not to nominate anyone

        return nominated_player, torch.Tensor([nomination_index])

    def get_vector(self, game_state, action_type, player):
        state_vector = game_state.get_state_vector(player, action_type)
        action_vector = self.get_action_vector(state_vector, action_type)
        player.action_vector = action_vector
        return action_vector

    def make_declarations(self, game_state, player):
        action_type = "make_declarations"
        action_vector = self.get_vector(game_state, action_type, player)
        declarations, action_vector_indices = self._get_declarations_from_vector(action_vector, game_state)
        player.action_vector.index_fill_(0, action_vector_indices.long(), 1)
        return declarations

    def vote(self, game_state, player):
        action_type = "vote"
        action_vector = self.get_vector(game_state, action_type, player)

        mask = torch.zeros(10, dtype=torch.bool)
        for player in game_state.nominated_players:
            mask[player.id] = True  # Only nominated players are considered

        action_vector = action_vector.masked_fill(~mask, -1e9)

        target_player, action_vector_indices = self._get_vote_from_vector(action_vector, game_state)
        if not target_player:
            return
        player.action_vector.index_fill_(0, action_vector_indices.long(), 1)
        return target_player

    def kill(self, game_state, player):
        action_type = "kill"
        action_vector = self.get_vector(game_state, action_type, player)
        target_player, action_vector_indices = self._get_kill_from_vector(action_vector)
        player.action_vector.index_fill_(0, action_vector_indices.long(), 1)
        return target_player

    def nominate_player(self, game_state, player):
        action_type = "nominate_player"
        action_vector = self.get_vector(game_state, action_type, player)
        target_player, action_vector_indices = self._get_nomination_from_vector(action_vector, game_state)
        player.action_vector.index_fill_(0, action_vector_indices.long(), 1)
        return target_player
