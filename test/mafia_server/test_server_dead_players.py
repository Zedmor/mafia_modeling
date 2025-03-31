import pytest
import json
import socket
from unittest.mock import MagicMock, patch

from mafia_server.server import MafiaServer
from mafia_server.models import Phase, Role, ActionRequest

class TestServerWithDeadPlayers:
    """
    Tests for the server's behavior with dead players to ensure they:
    1. Receive game state updates
    2. Cannot take actions
    """
    
    @pytest.fixture
    def mock_server(self):
        """Create a server with mock client connections and some dead players"""
        server = MafiaServer("localhost", 8765)
        
        # Mock socket setup
        server.socket = MagicMock()
        server.is_running = True
        
        # Mock client connections
        mock_sockets = [MagicMock() for _ in range(3)]  # Create 3 mock client connections
        server.clients = {
            0: {"socket": mock_sockets[0], "address": ("127.0.0.1", 10000)},
            1: {"socket": mock_sockets[1], "address": ("127.0.0.1", 10001)},
            2: {"socket": mock_sockets[2], "address": ("127.0.0.1", 10002)},
        }
        
        # Mark player 1 as dead
        server.game_state.players[1].alive = False
        
        # Set up game state for voting phase
        server.game_state.current_phase = Phase.VOTING
        server.game_state.nominated_players = [0, 2]
        server.active_player = 0
        server.game_state.active_player = 0
        
        return server
    
    def test_dead_player_receives_game_state_without_actions(self, mock_server):
        """Test that dead players receive game state updates but cannot take actions"""
        # Patch the _send_length_prefixed_message method to verify calls
        with patch.object(mock_server, '_send_length_prefixed_message') as mock_send:
            # Call broadcast game state
            mock_server._broadcast_game_state()
            
            # Check that _send_length_prefixed_message was called for each client
            assert mock_send.call_count == len(mock_server.clients)
            
            # Check that the messages have appropriate content
            for i, (args, kwargs) in enumerate(mock_send.call_args_list):
                # First argument should be client socket, second is the message dict
                client_socket, sent_message = args
                
                # All players should receive a valid request object
                assert sent_message["type"] == "ACTION_REQUEST"
                player_id = sent_message["player_id"]
                assert sent_message["phase"] == Phase.VOTING.name
                
                # Check for valid actions based on player status
                if player_id == 0:  # Active player and alive
                    assert "vote" in sent_message["valid_actions"]
                    assert len(sent_message["valid_actions"]["vote"]) > 0
                elif player_id == 1:  # Dead player
                    # Dead player should receive empty valid_actions
                    assert sent_message["valid_actions"] == {}
                else:  # Alive but not active player
                    # Other players should also receive empty valid_actions
                    assert sent_message["valid_actions"] == {}
    
    def test_dead_player_action_rejected(self, mock_server):
        """Test that actions from dead players are rejected with appropriate error"""
        # Set active player to the dead player
        mock_server.active_player = 1
        mock_server.game_state.active_player = 1
        
        # Mock message from dead player
        message = {
            "type": "ACTION_RESPONSE",
            "player_id": 1,
            "action": {
                "type": "VOTE",
                "target": 2
            }
        }
        
        # Process the message
        with patch.object(mock_server, '_send_error') as mock_send_error:
            mock_server._process_message(message)
            
            # Verify error was sent to the dead player
            mock_send_error.assert_called_once()
            args = mock_send_error.call_args[0]
            assert args[0] == 1  # player_id
            assert "not alive" in args[1]  # error message
    
    def test_player_advancement_updates_active_player(self, mock_server):
        """Test that the server's active_player is properly updated after advancing to the next player"""
        # Create a vote action
        action = {
            "type": "VOTE",
            "target": 2
        }
        
        # Mock game state methods to avoid actually changing state
        with patch.object(mock_server.game_state, 'apply_vote'), \
             patch.object(mock_server.game_state, '_advance_player') as mock_advance:
            
            # Configure _advance_player to update game_state.active_player
            def set_next_player():
                mock_server.game_state.active_player = 2
                return False  # Not a cycle completion
            
            mock_advance.side_effect = set_next_player
            
            # Apply the action
            mock_server._apply_action(action)
            
            # Verify that server's active_player is updated to match game_state.active_player
            assert mock_server.active_player == 2
            assert mock_server.active_player == mock_server.game_state.active_player
    
    def test_broadcast_events_to_all_including_dead(self, mock_server):
        """Test that all players, including dead ones, receive game events"""
        # Patch the _send_length_prefixed_message method to verify calls
        with patch.object(mock_server, '_send_length_prefixed_message') as mock_send:
            # Broadcast an event
            mock_server._broadcast_event_to_all("PLAYER_ELIMINATED", player_id=2, revealed_role="MAFIA")
            
            # Check that _send_length_prefixed_message was called for each client
            assert mock_send.call_count == len(mock_server.clients)
            
            # Check that all messages have the correct event data
            for call_args in mock_send.call_args_list:
                # Second argument is the message dict
                sent_message = call_args[0][1]
                
                # Verify the event was correctly formatted
                assert sent_message["type"] == "GAME_EVENT"
                assert sent_message["event"] == "PLAYER_ELIMINATED"
                assert sent_message["player_id"] == 2
                assert sent_message["revealed_role"] == "MAFIA"
