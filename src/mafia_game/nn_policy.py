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

INPUT_LAYER_SIZE = 3044
MODEL_PATH = f'{os.getcwd()}/../../model_weights/policy_model.pth'


if torch.cuda.is_available():
    device = torch.device('cuda')
    torch.set_default_tensor_type('torch.cuda.FloatTensor')
else:
    device = torch.device('cpu')
    torch.set_default_tensor_type('torch.FloatTensor')


class NeuralNetwork(nn.Module):
    def __init__(self, input_size, output_size):
        super(NeuralNetwork, self).__init__()
        self.layer1 = nn.Linear(input_size, 128)
        self.layer2 = nn.Linear(128, 256)
        self.layer3 = nn.Linear(256, output_size)

    def forward(self, x):
        x = F.relu(self.layer1(x))
        x = F.relu(self.layer2(x))
        out = self.layer3(x)
        return out




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
            self.network = NeuralNetwork(INPUT_LAYER_SIZE, self.output_size).to(device)
            self.target_net = NeuralNetwork(INPUT_LAYER_SIZE, self.output_size).to(device)

        self.optimizer = optim.Adam(self.network.parameters(), lr=0.00025)
        self.criterion = nn.MSELoss()
        self.epsilon = 1
        self.epsilon_decay = 0.995

    @property
    def output_size(self):
        """
        Output is vector of:
        10 for voting,
        11 for nominating (players + no one),
        63 for declaring (three declarations for each target player with mafia/citizen + option for not declaring).
        10 for killing
        ----
        94 long

        :return:
        """
        return 94
        # return self.num_players + self.num_players + 1 + (self.num_players * 2 + 1) * 3 + self.num_players

    def get_action_vector(self, state_vector):
        if random.random() < self.epsilon:
            # Generate a random action vector
            action_vector = torch.rand(self.output_size)
        else:
            # Use the network to generate the action vector
            with torch.no_grad():
                action_vector = self.network(state_vector.unsqueeze(0))
        return action_vector.squeeze(0)

    def _get_declarations_from_vector(self, action_vector, game_state):
        # The action vector should already be masked, so we just need to find the indices of the maximum values.
        # These indices correspond to the declarations that the agent has decided to make.
        top_indices = torch.topk(action_vector, 3).indices  # Get the indices of the top 3 values
        declarations = []
        for index in top_indices:
            index -= 21
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
        # The action vector should already be masked, so we just need to find the index of the maximum value.
        # This index corresponds to the player that the agent has decided to nominate.
        nomination_index = torch.argmax(action_vector).item()
        # The nomination_index should be between 0 and 10 (inclusive) because there are 10 players and one 'no one' option.
        # We can use this index to get the corresponding player from the game state.
        if nomination_index < 10:
            nominated_player = game_state.players[nomination_index]
        else:
            nominated_player = None  # The agent has decided not to nominate anyone

        return nominated_player, torch.Tensor([nomination_index])

    def get_vector(self, game_state, action_type, player):
        state_vector = game_state.get_state_vector(player, action_type)
        action_vector = self.get_action_vector(state_vector)
        mask = game_state.create_mask(action_type)
        action_vector = action_vector.masked_fill(~mask, -1e9)
        player.action_vector = action_vector
        return action_vector

    def make_declarations(self, game_state, player):
        action_type = "make_declarations"
        action_vector = self.get_vector(game_state, action_type, player)
        declarations, action_result_indices = self._get_declarations_from_vector(action_vector, game_state)
        player.action_result.index_fill_(0, action_result_indices.long(), 1)
        return declarations

    def vote(self, game_state, player):
        action_type = "vote"
        action_vector = self.get_vector(game_state, action_type, player)
        target_player, action_result_indices = self._get_vote_from_vector(action_vector, game_state)
        if not target_player:
            return
        player.action_result.index_fill_(0, action_result_indices.long(), 1)
        return target_player

    def kill(self, game_state, player):
        action_type = "kill"
        action_vector = self.get_vector(game_state, action_type, player)
        target_player, action_result_indices = self._get_kill_from_vector(action_vector)
        player.action_result.index_fill_(0, action_result_indices.long(), 1)
        return target_player

    def nominate_player(self, game_state, player):
        action_type = "nominate_player"
        action_vector = self.get_vector(game_state, action_type, player)
        target_player, action_result_indices = self._get_nomination_from_vector(action_vector, game_state)
        player.action_result.index_fill_(0, action_result_indices.long(), 1)
        return target_player
