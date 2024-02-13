import numpy as np
import pytest
import torch
from unittest.mock import MagicMock


# Define a fixture for the network sizes
@pytest.fixture
def network_sizes():
    return {"input_size": 100, "hidden_size": 64}


# Define a fixture for a mock optimizer
@pytest.fixture
def mock_optimizer():
    optimizer = MagicMock()
    optimizer.zero_grad = MagicMock()
    optimizer.step = MagicMock()
    return optimizer


# Define a fixture for a mock criterion
@pytest.fixture
def mock_criterion():
    criterion = MagicMock()
    criterion.return_value = torch.tensor(0.0)  # Mock loss value
    return criterion


# Define a fixture for a mock game state with a serialize method
@pytest.fixture
def mock_game_state():
    game_state = MagicMock()
    game_state.serialize = MagicMock(
        return_value=np.zeros(100)
    )  # Mock serialized state
    return game_state

