import pytest
from unittest.mock import MagicMock, patch
import random

from mafia_server.random_agent import RandomAgent
from mafia_server.models import Phase, GameState


def test_random_agent_eliminate_all_voting():
    """Test that random agent correctly handles eliminate-all voting phase"""
    agent = RandomAgent(verbose=True)
    agent.client.player_id = 3  # Mock the player_id
    
    # Test eliminate-all voting
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
    
    # Set random seed for reproducible test
    random.seed(42)
    
    # Call the action callback multiple times to ensure it consistently works
    for _ in range(5):
        action = agent._action_callback(eliminate_message)
        assert "type" in action
        assert action["type"] == "ELIMINATE_ALL_VOTE"
        assert "vote" in action
        assert isinstance(action["vote"], bool)


def test_server_eliminate_all_vote_processing():
    """Test that server correctly processes eliminate-all votes"""
    from mafia_server.server import MafiaServer
    
    server = MafiaServer()
    server.game_state = GameState.new_game()
    server.game_state.current_phase = Phase.VOTING
    server.game_state.voting_round = 2  # Set to eliminate-all voting round
    server.active_player = 0
    
    # Create tied players
    server.game_state.tied_players = [2, 4]
    
    # Create an action for eliminate-all vote
    action = {
        "type": "ELIMINATE_ALL_VOTE",
        "vote": True
    }
    
    # Mock broadcast to avoid actual socket operations
    with patch.object(server, '_broadcast_event_to_all'):
        with patch.object(server, '_broadcast_game_state'):
            # Apply the action
            server._apply_action(action)
            
            # Verify the eliminate-all vote was applied
            assert server.game_state.eliminate_all_votes[0] == 1  # 1 for True, 0 for False
            
            # Test multiple players voting
            server.active_player = 1
            server._apply_action(action)
            
            server.active_player = 2
            server._apply_action(action)
            
            # Set up enough votes to pass the eliminate-all threshold
            for i in range(6):
                server.game_state.eliminate_all_votes[i] = 1
                
            # Manually resolve votes
            server.game_state._resolve_eliminate_all_vote()
            
            # Check that both tied players were eliminated
            assert not server.game_state.players[2].alive
            assert not server.game_state.players[4].alive


def test_integrated_voting_sequence():
    """
    Test the full sequence of voting rounds:
    1. First vote with tie
    2. Second vote with tie
    3. Eliminate-all vote
    """
    from mafia_server.server import MafiaServer
    
    server = MafiaServer()
    server.game_state = GameState.new_game()
    server.game_state.current_phase = Phase.VOTING
    server.game_state.voting_round = 0
    server.active_player = 0
    
    # Set up nominations
    server.game_state.nominated_players = [2, 4]
    
    # Create players for tied vote in first round
    for i in range(3):
        server.game_state.players[i].vote_for = 2
    
    for i in range(3, 6):
        server.game_state.players[i].vote_for = 4
    
    # Mock broadcasts to avoid actual socket operations
    with patch.object(server, '_broadcast_event_to_all'):
        with patch.object(server, '_broadcast_game_state'):
            # Ensure cycle is completed for vote resolution
            server.game_state.phase_start_player = 0
            server.game_state.active_player = server.game_state.phase_start_player
            
            # Simulate cycle completion
            cycle_completed = True
            
            # Process vote resolution manually
            if cycle_completed and server.game_state.current_phase == Phase.VOTING:
                eliminated_player = server.game_state._resolve_votes()
                
                # No player should be eliminated in the first round
                assert eliminated_player is None
                # Voting round should advance to 1
                assert server.game_state.voting_round == 1
                # Tied players should be [2, 4]
                assert set(server.game_state.tied_players) == {2, 4}
                
                # Second round of voting - also tie
                for i in range(3):
                    server.game_state.players[i].vote_for = 2
                
                for i in range(3, 6):
                    server.game_state.players[i].vote_for = 4
                
                eliminated_player = server.game_state._resolve_votes()
                
                # No player should be eliminated in the second round
                assert eliminated_player is None
                # Voting round should advance to 2 (eliminate-all)
                assert server.game_state.voting_round == 2
                
                # Setup eliminate-all votes - majority votes yes
                alive_count = sum(1 for p in server.game_state.players if p.alive)
                yes_votes = (alive_count // 2) + 1
                
                for i in range(yes_votes):
                    server.game_state.eliminate_all_votes[i] = 1
                
                # Process eliminate-all vote
                server.game_state._resolve_eliminate_all_vote()
                
                # Both tied players should be eliminated
                assert not server.game_state.players[2].alive
                assert not server.game_state.players[4].alive
