import pytest
import json
from unittest.mock import MagicMock, patch

from mafia_server.server import MafiaServer
from mafia_server.models import Phase, Role, Team

class TestPlayerEliminationPrivacy:
    """
    Tests to ensure player elimination events do not reveal player roles to clients,
    in accordance with game rules.
    """
    
    @pytest.fixture
    def mock_server(self):
        """Create a server with mock client connections"""
        server = MafiaServer("localhost", 8765)
        
        # Mock socket setup
        server.socket = MagicMock()
        server.is_running = True
        
        # Mock client connections
        mock_sockets = [MagicMock() for _ in range(3)]
        server.clients = {
            0: {"socket": mock_sockets[0], "address": ("127.0.0.1", 10000)},
            1: {"socket": mock_sockets[1], "address": ("127.0.0.1", 10001)},
            2: {"socket": mock_sockets[2], "address": ("127.0.0.1", 10002)},
        }
        
        return server
    
    def test_player_eliminated_event_no_role_revealed(self, mock_server):
        """Test that the PLAYER_ELIMINATED event does not reveal the player's role"""
        # Patch the _send_length_prefixed_message method to verify calls
        with patch.object(mock_server, '_send_length_prefixed_message') as mock_send:
            # Broadcast a player elimination event
            mock_server._broadcast_event_to_all("PLAYER_ELIMINATED", player_id=2)
            
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
                # Role should not be revealed
                assert "revealed_role" not in sent_message
    
    def test_observation_does_not_reveal_eliminated_roles(self, mock_server):
        """Test that the observation sent to clients does not reveal eliminated player roles"""
        # Mark player 1 as eliminated
        mock_server.game_state.players[1].alive = False
        
        # Get observation for player 0
        observation = mock_server.game_state.get_observation(0)
        
        # Verify that known_roles does not include role information
        assert "known_roles" in observation
        assert 1 in observation["known_roles"]  # Player 1 should be in known_roles
        
        # The role should be UNKNOWN, not the actual role
        assert observation["known_roles"][1] == "UNKNOWN"
