import pytest
import time
from unittest.mock import MagicMock, patch
import threading

from mafia_server.random_agent import RandomAgent
from mafia_server.models import Phase


def test_random_agent_initialization():
    """Test that random agent initializes correctly"""
    agent = RandomAgent(host="test_host", port=1234, agent_id=5, verbose=True)
    
    assert agent.host == "test_host"
    assert agent.port == 1234
    assert agent.agent_id == 5
    assert agent.verbose == True
    assert agent.connected == False
    assert agent.client is not None


@patch('mafia_server.random_agent.MafiaClient')
def test_random_agent_connect(mock_client_class):
    """Test that random agent connects correctly"""
    # Mock the connect method to return True
    mock_client_instance = MagicMock()
    mock_client_instance.connect.return_value = True
    mock_client_class.return_value = mock_client_instance
    
    agent = RandomAgent()
    result = agent.connect()
    
    assert result == True
    assert agent.connected == True
    mock_client_instance.connect.assert_called_once()


@patch('mafia_server.random_agent.MafiaClient')
def test_random_agent_disconnect(mock_client_class):
    """Test that random agent disconnects correctly"""
    # Setup
    mock_client_instance = MagicMock()
    mock_client_class.return_value = mock_client_instance
    
    agent = RandomAgent()
    agent.client = mock_client_instance  # Override with our mock
    agent.connected = True  # Simulate being connected
    
    # Act
    agent.disconnect()
    
    # Assert
    assert agent.connected == False
    mock_client_instance.disconnect.assert_called_once()


def test_random_agent_action_callback():
    """Test that random agent generates valid actions for different phases"""
    agent = RandomAgent(verbose=True)
    agent.client.player_id = 3  # Mock the player_id
    
    # Test DECLARATION phase
    declaration_message = {
        "player_id": 3,
        "phase": "DECLARATION",
        "valid_actions": {
            "declaration": "vector_10",
            "sheriff_claims": "matrix_10x10",
            "nomination": [-1, 0, 1, 2, 4, 5, 6, 7, 8, 9]
        },
        "observation": {
            "turn": 1,
            "alive_players": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        }
    }
    
    action = agent._action_callback(declaration_message)
    assert "type" in action
    assert action["type"] == "DECLARATION"
    assert "declaration" in action
    assert len(action["declaration"]) == 10
    assert "sheriff_claims" in action
    
    # Test VOTING phase
    voting_message = {
        "player_id": 3,
        "phase": "VOTING",
        "valid_actions": {
            "vote": [1, 5]
        },
        "observation": {
            "turn": 1,
            "alive_players": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        }
    }
    
    action = agent._action_callback(voting_message)
    assert "type" in action
    assert action["type"] == "VOTE"  # Server expects "VOTE"
    assert "target" in action
    assert action["target"] in [1, 5]
    
    # Test ELIMINATE_ALL_VOTE phase
    eliminate_message = {
        "player_id": 3,
        "phase": "ELIMINATE_ALL_VOTE",
        "valid_actions": {
            "eliminate_all": [True, False]
        },
        "observation": {
            "turn": 1,
            "alive_players": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        }
    }
    
    action = agent._action_callback(eliminate_message)
    assert "type" in action
    assert action["type"] == "ELIMINATE_ALL_VOTE"
    assert "vote" in action
    assert isinstance(action["vote"], bool)
    
    # Test NIGHT_KILL phase
    kill_message = {
        "player_id": 3,
        "phase": "NIGHT_KILL",
        "valid_actions": {
            "kill": [1, 2, 5, 7]
        },
        "observation": {
            "turn": 1,
            "alive_players": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        }
    }
    
    action = agent._action_callback(kill_message)
    assert "type" in action
    assert action["type"] == "KILL"  # Server expects "KILL"
    assert "target" in action
    assert action["target"] in [1, 2, 5, 7]


def test_agent_ignore_other_players_turns():
    """Test that random agent ignores messages for other players"""
    agent = RandomAgent()
    agent.client.player_id = 3  # Mock the player_id
    
    # Message for another player
    other_player_message = {
        "player_id": 2,  # Not our player_id
        "phase": "DECLARATION",
        "valid_actions": {
            "declaration": "vector_10"
        },
        "observation": {
            "turn": 1,
            "alive_players": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        }
    }
    
    action = agent._action_callback(other_player_message)
    assert action is None


def test_agent_handles_no_valid_actions():
    """Test that random agent handles messages with no valid actions"""
    agent = RandomAgent(verbose=True)
    agent.client.player_id = 3  # Mock the player_id
    
    # Message with no valid actions
    no_actions_message = {
        "player_id": 3,
        "phase": "DECLARATION",
        "valid_actions": {},
        "observation": {
            "turn": 1,
            "alive_players": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        }
    }
    
    action = agent._action_callback(no_actions_message)
    assert action is None


@pytest.mark.skip("Integration test - requires running server")
def test_integration_random_agent():
    """
    Integration test for random agent.
    
    This test requires a running server. It will connect a random agent
    and verify that it can interact with the server.
    
    Note: This test is skipped by default as it requires manual setup.
    """
    from mafia_server.server import MafiaServer
    
    # Start server in a separate thread
    server = MafiaServer()
    server_thread = threading.Thread(target=server.start)
    server_thread.daemon = True
    server_thread.start()
    
    time.sleep(1)  # Give the server time to start
    
    # Connect random agent
    agent = RandomAgent(verbose=True)
    connected = agent.connect()
    
    assert connected == True
    
    # Let it run for a few seconds
    time.sleep(5)
    
    # Clean up
    agent.disconnect()
    server.stop()
