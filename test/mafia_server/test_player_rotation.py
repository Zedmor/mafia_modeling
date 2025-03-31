import pytest
from mafia_server.models import GameState, Player, Role, Phase

def test_day_starter_player_rotation():
    """Test that the starting player rotates each day."""
    # Create a game with predefined roles for testing
    game = GameState()
    
    # Create 10 players with predefined roles
    roles = [Role.CITIZEN, Role.SHERIFF, Role.CITIZEN, Role.MAFIA, 
            Role.CITIZEN, Role.CITIZEN, Role.CITIZEN, Role.MAFIA, 
            Role.CITIZEN, Role.DON]
    
    game.players = [Player(i, role) for i, role in enumerate(roles)]
    
    # Initial phase: DECLARATION with player 0 as the active player
    assert game.active_player == 0
    assert game.current_phase == Phase.DECLARATION
    
    # Simulate a day (DECLARATION -> VOTING -> NIGHT_KILL -> NIGHT_DON -> NIGHT_SHERIFF)
    # and verify player rotation for the next day
    
    # First, simulate DECLARATION phase
    # All players make declarations
    for i in range(10):
        game.active_player = i
        game.apply_declaration(i, [0] * 10)
    
    # Transition to VOTING phase
    game.active_player = 0  # Reset to player 0
    game.phase_start_player = 0
    game._transition_phase()
    assert game.current_phase == Phase.VOTING
    
    # Simulate voting
    for i in range(10):
        if game.players[i].alive:
            target = (i + 1) % 10
            while not game.players[target].alive or target == i:
                target = (target + 1) % 10
            game.active_player = i
            game.apply_vote(i, target)
    
    # Transition to NIGHT phases
    game.phase_start_player = 0
    game.active_player = 0
    game._transition_phase()  # VOTING -> NIGHT_KILL
    assert game.current_phase == Phase.NIGHT_KILL
    
    # Simulate night kill
    mafia_player = 3  # Known mafia player
    game.active_player = mafia_player
    game.apply_kill(0)  # Kill player 0
    
    # Transition to NIGHT_DON
    game.active_player = mafia_player
    game.phase_start_player = mafia_player
    game._transition_phase()  # NIGHT_KILL -> NIGHT_DON
    assert game.current_phase == Phase.NIGHT_DON
    
    # Simulate Don check
    don_player = 9  # Known Don player
    game.active_player = don_player
    game.apply_don_check(1)  # Check player 1
    
    # Transition to NIGHT_SHERIFF
    game.active_player = don_player
    game.phase_start_player = don_player
    game._transition_phase()  # NIGHT_DON -> NIGHT_SHERIFF
    assert game.current_phase == Phase.NIGHT_SHERIFF
    
    # Simulate Sheriff check
    sheriff_player = 1  # Known Sheriff player
    game.active_player = sheriff_player
    game.apply_sheriff_check(2)  # Check player 2
    
    # Transition to next day (DECLARATION)
    game.active_player = sheriff_player
    game.phase_start_player = sheriff_player
    game._transition_phase()  # NIGHT_SHERIFF -> DECLARATION
    
    # Night kill should have applied
    assert not game.players[0].alive
    
    # Verify that we're in the next day's DECLARATION phase
    assert game.current_phase == Phase.DECLARATION
    assert game.turn == 1
    
    # Most importantly, verify that the starting player has rotated to
    # player 1 (or the next alive player if 1 is dead)
    assert game.active_player != 0
    assert game.active_player == 1  # Player 1 should be the starting player for day 2
    
    # Simulate another day to verify rotation continues
    # Skip declaration phase and go to night_sheriff again
    game._transition_phase()  # DECLARATION -> VOTING
    game._transition_phase()  # VOTING -> NIGHT_KILL
    game._transition_phase()  # NIGHT_KILL -> NIGHT_DON
    game._transition_phase()  # NIGHT_DON -> NIGHT_SHERIFF
    
    # Transition to third day (DECLARATION)
    game.active_player = sheriff_player
    game.phase_start_player = sheriff_player
    game._transition_phase()  # NIGHT_SHERIFF -> DECLARATION
    
    # Verify we're now in turn 2
    assert game.turn == 2
    
    # And starting player has rotated again to player 2
    assert game.active_player == 2
