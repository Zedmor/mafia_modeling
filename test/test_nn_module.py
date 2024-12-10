import pytest
import torch
from unittest.mock import MagicMock
from mafia_game.multihead_nn import (
    BaseDQNNetwork,
    RedDQNNetwork,
    BlackDQNNetwork,
    select_action,
)
from mafia_game.actions import KillAction


# Define a fixture for the input size and hidden size
@pytest.fixture
def network_sizes():
    return {"input_size": 100, "hidden_size": 64}


# Define a fixture for a mock game state
@pytest.fixture
def mock_game_state():
    game_state = MagicMock()
    game_state.game_states = [MagicMock(alive=True) for _ in range(10)]
    return game_state


# Test the initialization of the BaseDQNNetwork
def test_base_dqn_network_initialization(network_sizes):
    network = BaseDQNNetwork(**network_sizes, action_types=[KillAction])
    assert isinstance(network, BaseDQNNetwork)
    assert len(network.heads) == 2  # Two action types


# Test the initialization of the RedDQNNetwork
def test_red_dqn_network_initialization(network_sizes):
    network = RedDQNNetwork(**network_sizes)
    assert isinstance(network, RedDQNNetwork)
    # Check that only red_team actions are included
    for action_type in network.action_types:
        assert action_type.red_team


# Test the initialization of the BlackDQNNetwork
def test_black_dqn_network_initialization(network_sizes):
    network = BlackDQNNetwork(**network_sizes)
    assert isinstance(network, BlackDQNNetwork)
    # Check that only black_team actions are included
    for action_type in network.action_types:
        assert action_type.black_team


# Test the select_action function with an index input type
def test_select_action_index_input(network_sizes, mock_game_state):
    network = BlackDQNNetwork(**network_sizes)
    # Mock the output of the network to be a tensor of shape (10,)
    network_output = torch.randn(10)
    network.forward = MagicMock(return_value=network_output)

    # Mock the to_tensor method of CompleteGameState to return a dummy input tensor
    mock_game_state.to_tensor = MagicMock(return_value=torch.randn(1, network_sizes["input_size"]))

    # Mock the generate_action_mask method to return a mask of ones
    KillAction.generate_action_mask = MagicMock(return_value=torch.ones(KillAction.action_size))

    # Select a KillAction which has an index input type
    action = select_action(network, mock_game_state, KillAction, player_index=0, epsilon=0)

    # Assert that the action is an instance of KillAction
    assert isinstance(action, KillAction)

    # Assert that the generate_action_mask method was called with the correct arguments
    KillAction.generate_action_mask.assert_called_with(mock_game_state, 0)
