import pytest
from mafia_server.models import (
    Role, Team, Phase, Player, GameState,
    ActionRequest, ActionResponse, GameEvent
)
from mafia_server.server import MafiaServer

def test_server_checks_win_condition_after_night_kill():
    """
    Test that the server properly checks for win conditions immediately after a night kill
    that creates a situation where mafia has equal numbers to the town team.
    """
    # Create a server instance
    server = MafiaServer()
    
    # Create a game state with specific player configuration
    game = GameState()
    # Set up minimal player roles for testing
    players = [
        Player(0, Role.MAFIA),    # Mafia
        Player(1, Role.CITIZEN),  # Citizen to be killed
        Player(2, Role.CITIZEN),  # Citizen 
        Player(3, Role.DON),      # Don
    ]
    game.players = players
    
    # Set the game state on the server
    server.game_state = game
    
    # Now we're in NIGHT_KILL phase
    game.current_phase = Phase.NIGHT_KILL
    
    # Set active player to the Don
    server.active_player = 3  
    
    # Apply the kill action (this simulates the Mafia killing a Citizen)
    action = {
        "type": "KILL",
        "target": 1  # Target player 1 (Citizen)
    }
    
    # Process the kill action
    server._apply_action(action)
    
    # Before this kill, the count is RED:2, BLACK:2
    # After the kill is processed and win condition is checked, BLACK should win
    
    # Make sure the phase advanced properly
    assert server.game_state.current_phase == Phase.GAME_OVER, "Game should end after Mafia achieves numerical parity"
    assert server.game_state.winner == Team.BLACK, "BLACK team should win after achieving numerical parity"
