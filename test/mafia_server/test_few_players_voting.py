import pytest
from unittest.mock import MagicMock, patch

from mafia_server.models import Phase, GameState, Role


def test_voting_with_three_players_remaining():
    """Test voting phase when only 3 players remain in the game"""
    
    # Create a new game state
    game_state = GameState.new_game()
    
    # Mark most players as dead, leaving only 3 alive (3, 6, 7)
    for i, player in enumerate(game_state.players):
        if i not in [3, 6, 7]:
            player.alive = False
    
    # Assign specific roles for easier testing
    game_state.players[3].role = Role.DON     # Player 3 is Don
    game_state.players[6].role = Role.CITIZEN # Player 6 is Citizen
    game_state.players[7].role = Role.SHERIFF # Player 7 is Sheriff
    
    # Set the game state to declaration phase
    game_state.current_phase = Phase.DECLARATION
    game_state.active_player = 3  # Player 3 is active
    
    # Apply declarations
    game_state.apply_declaration(3, [0] * 10)
    game_state.apply_nomination(3, 6)  # Nominate player 6
    
    # Move to player 6
    game_state.active_player = 6
    game_state.apply_declaration(6, [0] * 10)
    game_state.apply_nomination(6, 7)  # Nominate player 7
    
    # Move to player 7
    game_state.active_player = 7
    game_state.apply_declaration(7, [0] * 10)
    
    # Transition to voting phase
    game_state._transition_phase()
    
    # Verify transition worked correctly
    assert game_state.current_phase == Phase.VOTING
    assert len(game_state.nominated_players) == 2
    
    # First player votes
    game_state.active_player = 3
    valid_actions = game_state.get_valid_actions()
    
    # Verify valid_actions contains vote option with valid targets
    assert "vote" in valid_actions
    assert len(valid_actions["vote"]) > 0
    assert 6 in valid_actions["vote"] and 7 in valid_actions["vote"]
    
    # Apply vote
    game_state.apply_vote(3, 6)
    
    # Move to player 6 and verify voting is still valid
    game_state.active_player = 6
    valid_actions = game_state.get_valid_actions()
    assert "vote" in valid_actions
    assert len(valid_actions["vote"]) > 0
    
    # Apply vote
    game_state.apply_vote(6, 7)
    
    # Move to player 7 and verify voting is still valid
    game_state.active_player = 7
    valid_actions = game_state.get_valid_actions()
    assert "vote" in valid_actions
    assert len(valid_actions["vote"]) > 0
    
    # Complete voting and resolve
    game_state.apply_vote(7, 6)
    eliminated_player = game_state._resolve_votes()
    
    # Verify elimination occurred
    assert eliminated_player == 6
    assert not game_state.players[6].alive


def test_full_cycle_with_few_players():
    """Test a full game cycle with only a few players remaining"""
    
    # Create a new game state with only 3 players alive
    game_state = GameState.new_game()
    
    # Mark most players as dead, leaving only 3 alive (3, 6, 7)
    for i, player in enumerate(game_state.players):
        if i not in [3, 6, 7]:
            player.alive = False
    
    # Assign specific roles for easier testing
    game_state.players[3].role = Role.DON     # Player 3 is Don
    game_state.players[6].role = Role.CITIZEN # Player 6 is Citizen
    game_state.players[7].role = Role.SHERIFF # Player 7 is Sheriff
    
    # Initialize game state
    game_state.current_phase = Phase.DECLARATION
    game_state.turn = 5  # Same as in the log
    game_state.active_player = 3
    game_state.phase_start_player = 3
    
    # Go through complete turn cycle
    # Player 3 (Don) declaration
    valid_actions = game_state.get_valid_actions()
    assert "declaration" in valid_actions
    game_state.apply_declaration(3, [0] * 10)
    game_state.apply_nomination(3, 6)
    
    # Advance to next player
    cycle_completed = game_state._advance_player()
    assert not cycle_completed
    assert game_state.active_player == 6
    
    # Player 6 (Citizen) declaration
    valid_actions = game_state.get_valid_actions()
    assert "declaration" in valid_actions
    game_state.apply_declaration(6, [0] * 10)
    
    # Advance to next player
    cycle_completed = game_state._advance_player()
    assert not cycle_completed
    assert game_state.active_player == 7
    
    # Player 7 (Sheriff) declaration
    valid_actions = game_state.get_valid_actions()
    assert "declaration" in valid_actions
    game_state.apply_declaration(7, [0] * 10)
    
    # Advance to next player - should complete the cycle
    cycle_completed = game_state._advance_player()
    assert cycle_completed
    
    # Transition to voting phase
    game_state._transition_phase()
    assert game_state.current_phase == Phase.VOTING
    
    # Reset the active player for voting
    game_state.active_player = game_state.phase_start_player
    
    # Check all players can vote
    for player_id in [3, 6, 7]:
        game_state.active_player = player_id
        valid_actions = game_state.get_valid_actions()
        assert "vote" in valid_actions
        assert len(valid_actions["vote"]) > 0
        assert 6 in valid_actions["vote"]  # Player 6 was nominated
        
        # Apply vote
        game_state.apply_vote(player_id, 6)
    
    # Resolve voting
    eliminated_player = game_state._resolve_votes()
    assert eliminated_player == 6
    assert not game_state.players[6].alive
    
    # Check win condition
    winner = game_state.check_win_condition()
    assert winner is not None  # Game should be over
