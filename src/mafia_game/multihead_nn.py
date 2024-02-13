import torch.nn as nn
import random

from mafia_game.actions import *
from mafia_game.common import Team


class BaseDQNNetwork(nn.Module):
    def __init__(self, input_size, hidden_size, action_types):
        super(BaseDQNNetwork, self).__init__()
        self.base = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
        )
        self.heads = nn.ModuleList(
            [
                nn.Linear(hidden_size, action_type.action_size)
                for action_type in action_types
            ]
        )
        self.action_types = action_types

    def forward(
        self, game_state, action_type_index, mask=None):
        serialized_game_state = torch.tensor(
            game_state.serialize(), dtype=torch.float32
            ).view(1, -1)
        serialized_game_state = serialized_game_state.to(self.base[0].weight.device)
        base_output = self.base(serialized_game_state)

        head_output = self.heads[action_type_index](base_output)
        # Use torch.where to apply the mask with -inf for masked actions
        masked_output = torch.where(mask == 1, head_output,
                                    torch.tensor(float('-inf')).to(head_output.device))

        return masked_output


class RedDQNNetwork(BaseDQNNetwork):
    def __init__(self, input_size, hidden_size):
        # Filter action types for the Red team
        red_action_types = [
            action_type
            for action_type in Action.__subclasses__()
            if action_type.red_team
        ]
        super(RedDQNNetwork, self).__init__(input_size, hidden_size, red_action_types)


# Define the Black network subclass
class BlackDQNNetwork(BaseDQNNetwork):
    def __init__(self, input_size, hidden_size):
        # Filter action types for the Black team
        black_action_types = [
            action_type
            for action_type in Action.__subclasses__()
            if action_type.black_team
        ]
        super(BlackDQNNetwork, self).__init__(
            input_size, hidden_size, black_action_types
        )


# Define a function to select an action using the network output
def select_action(network, game_state_instance, action_type, player_index, epsilon=0.1):
    action_type_index = network.action_types.index(action_type)
    mask = action_type.generate_action_mask(game_state_instance, player_index)
    output = network(game_state_instance, action_type_index, mask)

    if action_type.input_type == InputTypes.VECTOR:
        # If the action expects a vector, use the entire output (e.g., for BeliefAction)

        random_vector = torch.randint(0, 3, (action_type.action_size,))
        action_data = random_vector if random.random() < epsilon else output
        return action_type.from_output_vector(
            action_data, game_state_instance, player_index
        ), action_type.normalize_vector(action_data)

    elif action_type.input_type == InputTypes.INDEX:
        # If the action expects an index, select one based on the output probabilities
        if random.random() < epsilon:
            # Exploration: Randomly select a valid action index
            valid_actions = output.nonzero(as_tuple=False).reshape(
                -1
            )  # Flatten the tensor to 1D
            action_index = (
                random.choice(valid_actions).item() if valid_actions.numel() > 0 else 0
            )
        else:
            # Exploitation: Select the action index with the highest probability
            action_index = output.argmax().item()  # Use argmax for 1D tensor
        return (
            action_type.from_index(action_index, game_state_instance, player_index),
            action_index,
        )


def calculate_reward(game_state, player_index):
    # Check if the game has ended and which team won
    if game_state.is_game_over():
        if (
            game_state.winning_team() == Team.RED_TEAM
            and game_state.game_states[player_index].private_data.team == Team.RED_TEAM
        ):
            return 1  # Reward for Red team winning
        elif (
            game_state.winning_team() == Team.BLACK_TEAM
            and game_state.game_states[player_index].private_data.team
            == Team.BLACK_TEAM
        ):
            return 1  # Reward for Black team winning
    return 0  # No reward if the game is not over or if the player's team did not win
