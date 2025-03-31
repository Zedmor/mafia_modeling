import pytest
import json
import socket
import threading
from unittest.mock import MagicMock, patch

from mafia_server.server import MafiaServer
from mafia_server.client import MafiaClient
from mafia_server.models import Phase, GameState, Player, Role


class TestEliminateAllServerClientIntegration:
    """Test the integration between server and client for eliminate-all voting phase"""
    
    @pytest.fixture
    def server(self):
        """Create a server with a specific game state for eliminate-all voting"""
        server = MafiaServer("localhost", 8765)
        
        # Prepare the game state for eliminate-all voting
        server.game_state = GameState.new_game()
        server.game_state.current_phase = Phase.VOTING
        server.game_state.voting_round = 2  # Set to eliminate-all voting round
        server.game_state.tied_players = [2, 4]  # Players in tie
        
        # Mock socket setup
        server.socket = MagicMock()
        server.is_running = True
        
        # Set active player
        server.active_player = 0
        server.game_state.active_player = 0
        
        # Set up mock client connections
        mock_sockets = [MagicMock() for _ in range(3)]
        server.clients = {
            0: {"socket": mock_sockets[0], "address": ("127.0.0.1", 10000)},
            1: {"socket": mock_sockets[1], "address": ("127.0.0.1", 10001)},
            2: {"socket": mock_sockets[2], "address": ("127.0.0.1", 10002)},
        }
        
        return server
    
    def test_server_sends_correct_action_request_for_eliminate_all(self, server):
        """Test that server sends the correct action request for eliminate-all voting"""
        # Patch the _send_length_prefixed_message method to capture the message
        with patch.object(server, '_send_length_prefixed_message') as mock_send:
            # Send game state to active player
            server._send_game_state(server.active_player)
            
            # Check that _send_length_prefixed_message was called
            mock_send.assert_called_once()
            
            # Get the message that was sent
            client_socket, sent_message = mock_send.call_args[0]
            
            # Verify message content
            assert sent_message["type"] == "ACTION_REQUEST"
            assert sent_message["player_id"] == 0
            assert sent_message["phase"] == "VOTING"
            assert "eliminate_all" in sent_message["valid_actions"]
            assert sent_message["valid_actions"]["eliminate_all"] == [True, False]
    
    def test_server_accepts_eliminate_all_vote_action(self, server):
        """Test that server correctly processes eliminate-all vote action"""
        # Create an eliminate-all vote action
        action = {
            "type": "ELIMINATE_ALL_VOTE",
            "vote": True
        }
        
        # Apply the action
        with patch.object(server, '_broadcast_game_state'):
            server._apply_action(action)
            
            # Verify the vote was recorded
            assert server.game_state.eliminate_all_votes[0] == 1
    
    def test_validate_eliminate_all_vote_action(self, server):
        """Test that server correctly validates eliminate-all vote action"""
        # Get valid actions
        valid_actions = server.game_state.get_valid_actions()
        
        # Create eliminate-all vote action
        action = {
            "type": "ELIMINATE_ALL_VOTE",
            "vote": True
        }
        
        # Call _validate_action directly
        is_valid, error_msg = server._validate_action(action, valid_actions)
        
        # The action should be valid
        assert is_valid, f"Action should be valid. Error: {error_msg}"
    
    def test_client_sends_correct_action_for_eliminate_all_phase(self):
        """Test that client sends the correct action for eliminate-all voting phase"""
        # Create a client with a mock socket
        client = MafiaClient()
        client.socket = MagicMock()
        client.is_connected = True
        client.player_id = 0
        
        # Create a mock message that would be received during eliminate all voting
        message = {
            "type": "ACTION_REQUEST",
            "player_id": 0,
            "phase": "VOTING",  # Note: Phase is still VOTING
            "valid_actions": {
                "eliminate_all": [True, False]
            },
            "observation": {}
        }
        
        # Define a simple action callback that votes True
        def action_callback(msg):
            if "eliminate_all" in msg["valid_actions"]:
                return {
                    "type": "ELIMINATE_ALL_VOTE",
                    "vote": True
                }
            return None
        
        # Set the callback
        client.action_callback = action_callback
        
        # Call _process_message with the mock message
        with patch.object(client, '_send_action') as mock_send:
            client._process_message(message)
            
            # Check that _send_action was called with the correct action
            mock_send.assert_called_once()
            action = mock_send.call_args[0][0]
            
            # Verify the action
            assert action["type"] == "ELIMINATE_ALL_VOTE"
            assert action["vote"] is True
    
    def test_end_to_end_eliminate_all_voting(self, server):
        """Test the complete eliminate-all voting flow from multiple players voting through to resolution"""
        # Make sure only a few players are alive to make the majority easier to reach
        for i in range(5, 10):
            if i != server.active_player and i not in server.game_state.tied_players:
                server.game_state.players[i].alive = False
        
        # Calculate how many votes needed for majority
        alive_count = sum(1 for p in server.game_state.players if p.alive)
        majority_needed = (alive_count // 2) + 1
        
        # Set up players to vote
        with patch.object(server, '_broadcast_event_to_all'), \
             patch.object(server, '_broadcast_game_state'):
            
            # Have enough players vote "Yes" to exceed the majority threshold
            votes_cast = 0
            for i in range(10):
                if votes_cast < majority_needed and server.game_state.players[i].alive:
                    server.active_player = i
                    server._apply_action({"type": "ELIMINATE_ALL_VOTE", "vote": True})
                    votes_cast += 1
            
            # Now simulate a cycle completion to trigger vote resolution
            server.game_state.active_player = server.game_state.phase_start_player
            
            # Process the eliminate-all vote resolution
            server.game_state._resolve_eliminate_all_vote()
            
            # Both tied players should be eliminated
            assert not server.game_state.players[2].alive
            assert not server.game_state.players[4].alive
            
            # Voting round should be reset
            assert server.game_state.voting_round == 0
            assert server.game_state.tied_players == []
    
    def test_random_agent_eliminate_all_vote(self):
        """Test that RandomAgent correctly handles eliminate-all voting"""
        from mafia_server.random_agent import RandomAgent
        
        # Create RandomAgent instance
        agent = RandomAgent()
        
        # Create mock message for eliminate-all voting phase
        message = {
            "player_id": 0,
            "phase": "ELIMINATE_ALL_VOTE",  # This is how server identifies the phase to the client
            "valid_actions": {
                "eliminate_all": [True, False]
            },
            "observation": {}
        }
        
        # Set player_id to match the message
        agent.client.player_id = 0
        
        # Call the action callback
        action = agent._action_callback(message)
        
        # Verify the action
        assert action["type"] == "ELIMINATE_ALL_VOTE"
        assert isinstance(action["vote"], bool)
