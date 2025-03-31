import pytest
from mafia_server.models import (
    Role, Team, Phase, Player, GameState,
    ActionRequest, ActionResponse, GameEvent
)

def test_game_should_end_when_night_kill_causes_mafia_win():
    """
    Test that the game correctly ends when a night kill causes the Mafia team to have
    equal or greater numbers than the Town team.
    
    This reproduces the specific scenario from the game trace where player 1 was killed,
    which should have triggered a Mafia win but didn't.
    """
    # Create a new game state
    game = GameState.new_game()
    
    # Directly set the roles to match the scenario in the game log
    # Players: [0m,1c,2c,3c,4c,5s,6c,7c,8d,9m]
    roles = [Role.MAFIA, Role.CITIZEN, Role.CITIZEN, Role.CITIZEN, Role.CITIZEN,
             Role.SHERIFF, Role.CITIZEN, Role.CITIZEN, Role.DON, Role.MAFIA]
    
    for i, role in enumerate(roles):
        game.players[i].role = role
    
    # Verify the initial setup
    red_count = sum(1 for p in game.players if p.alive and p.team == Team.RED)
    black_count = sum(1 for p in game.players if p.alive and p.team == Team.BLACK)
    
    assert red_count == 7  # 6 Citizens + 1 Sheriff
    assert black_count == 3  # 2 Mafia + 1 Don
    
    # Simulate existing eliminations to match the game state
    # [0m,1c,2c,3c,4cx,5sx,6c,7cx,8d,9m]
    game.players[4].alive = False  # Player 4 (Citizen) is already dead
    game.players[5].alive = False  # Player 5 (Sheriff) is already dead
    game.players[7].alive = False  # Player 7 (Citizen) is already dead
    
    # Verify the updated counts after existing eliminations
    red_count = sum(1 for p in game.players if p.alive and p.team == Team.RED)
    black_count = sum(1 for p in game.players if p.alive and p.team == Team.BLACK)
    
    assert red_count == 4  # 4 Citizens alive
    assert black_count == 3  # 3 Mafia/Don alive
    
    # Simulate a night kill of player 1 (Citizen)
    # This should make the game end with Mafia win
    game.current_phase = Phase.NIGHT_KILL
    game.active_player = 8  # Don is active player (player 8)
    
    # Apply kill action
    game.apply_kill(1)  # Kill player 1 (Citizen)
    
    # Process the night phase end (this applies the kills)
    game._process_night_end()
    
    # Check win condition - should be BLACK team win
    winner = game.check_win_condition()
    
    # This assertion will fail without the fix, because the bug is that
    # we're not properly detecting the win condition
    assert winner == Team.BLACK, "Mafia (BLACK team) should win when they have equal numbers to Town (RED team)"
    
    # Verify the counts after the night kill
    red_count = sum(1 for p in game.players if p.alive and p.team == Team.RED)
    black_count = sum(1 for p in game.players if p.alive and p.team == Team.BLACK)
    
    assert red_count == 3  # Now only 3 Citizens alive
    assert black_count == 3  # 3 Mafia/Don alive
    
    # This is the condition that triggers BLACK team win
    assert black_count >= red_count, "BLACK team wins when they have equal or greater numbers than RED team"

def test_win_check_after_night_kill_in_transition():
    """
    Test that win conditions are properly checked after night kills are processed,
    particularly during phase transitions.
    """
    # Create a game state with minimal players for easier testing
    game = GameState()
    # Set up simplified player roles
    players = [
        Player(0, Role.CITIZEN),
        Player(1, Role.CITIZEN),
        Player(2, Role.SHERIFF),
        Player(3, Role.MAFIA),
        Player(4, Role.DON)
    ]
    game.players = players
    
    # Town (RED) team has 3 players, Mafia (BLACK) team has 2
    red_count = sum(1 for p in game.players if p.alive and p.team == Team.RED)
    black_count = sum(1 for p in game.players if p.alive and p.team == Team.BLACK)
    assert red_count == 3
    assert black_count == 2
    
    # Kill one Town member to make teams equal
    game.night_kills[0] = True  # Mark Citizen (player 0) for night kill
    
    # Now we're in NIGHT_SHERIFF phase and about to end the night
    game.current_phase = Phase.NIGHT_SHERIFF
    
    # Process the night end (applies kills)
    game._process_night_end()
    
    # Check win condition
    winner = game.check_win_condition()
    
    # BLACK team should win because they now have equal numbers
    assert winner == Team.BLACK, "BLACK team should win after night kill gives them equal numbers"
    
    # Verify counts
    red_count = sum(1 for p in game.players if p.alive and p.team == Team.RED)
    black_count = sum(1 for p in game.players if p.alive and p.team == Team.BLACK)
    assert red_count == 2
    assert black_count == 2
    assert black_count >= red_count

def test_win_check_after_every_night_phase():
    """
    Test that win conditions are checked after every night phase action that could
    potentially change the player counts.
    """
    # Create a game state
    game = GameState()
    # Set up player roles
    players = [
        Player(0, Role.CITIZEN),
        Player(1, Role.CITIZEN),
        Player(2, Role.SHERIFF),
        Player(3, Role.MAFIA),
        Player(4, Role.DON)
    ]
    game.players = players
    
    # Test for NIGHT_KILL phase
    game.current_phase = Phase.NIGHT_KILL
    
    # Mark a citizen for killing
    game.night_kills[0] = True
    
    # Process night end early (even though normally it would happen after SHERIFF phase)
    game._process_night_end()
    
    # Check win condition - this should trigger a BLACK win
    winner = game.check_win_condition()
    assert winner == Team.BLACK, "Win condition should be checked after each potential player elimination"
