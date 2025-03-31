import pytest
from mafia_server.models import GameState, Role, Phase, Team

@pytest.fixture
def game_with_dead_players():
    """Set up a game with some dead players"""
    game = GameState.new_game()
    
    # Mark some players as dead
    game.players[1].alive = False  # Player 1 is dead
    game.players[3].alive = False  # Player 3 is dead
    
    # Set up for voting phase with nominations
    game.current_phase = Phase.VOTING
    game.nominated_players = [2, 4, 5]  # Player 1 was nominated before dying
    
    # Make player 0 the active player
    game.active_player = 0
    
    return game

def test_valid_actions_excludes_dead_players(game_with_dead_players):
    """Test that get_valid_actions excludes dead players"""
    game = game_with_dead_players
    valid_actions = game.get_valid_actions()
    
    # Check that voting actions don't include dead players
    assert 'vote' in valid_actions
    for player_id in valid_actions['vote']:
        assert game.players[player_id].alive
    
    # Specifically check that only alive nominated players are included
    assert 1 not in valid_actions['vote']
    assert 2 in valid_actions['vote']
    assert 3 not in valid_actions['vote']
    assert 4 in valid_actions['vote']
    assert 5 in valid_actions['vote']

def test_vote_for_dead_player_fails(game_with_dead_players):
    """Test that voting for a dead player raises an error"""
    game = game_with_dead_players
    
    # Try to vote for a dead player (Player 1)
    with pytest.raises(ValueError) as excinfo:
        game.apply_vote(0, 1)
    
    # Check the error message
    assert "Cannot vote for dead player" in str(excinfo.value)

def test_nominate_dead_player_fails(game_with_dead_players):
    """Test that nominating a dead player raises an error"""
    game = game_with_dead_players
    
    # Set up for declaration phase
    game.current_phase = Phase.DECLARATION
    
    # Try to nominate a dead player (Player 1)
    with pytest.raises(ValueError) as excinfo:
        game.apply_nomination(0, 1)
    
    # Check the error message
    assert "Cannot nominate dead player" in str(excinfo.value)

def test_kill_dead_player_fails(game_with_dead_players):
    """Test that killing a dead player raises an error"""
    game = game_with_dead_players
    
    # Set up for night kill phase
    game.current_phase = Phase.NIGHT_KILL
    
    # Make player 0 a mafia member
    game.players[0].role = Role.MAFIA
    
    # Try to kill a dead player (Player 1)
    with pytest.raises(ValueError) as excinfo:
        game.apply_kill(1)
    
    # Check the error message
    assert "Cannot kill dead player" in str(excinfo.value)

def test_check_dead_player_fails(game_with_dead_players):
    """Test that checking a dead player raises an error"""
    game = game_with_dead_players
    
    # Set up for don check phase
    game.current_phase = Phase.NIGHT_DON
    
    # Make player 0 the don
    game.players[0].role = Role.DON
    
    # Try to check a dead player (Player 1)
    with pytest.raises(ValueError) as excinfo:
        game.apply_don_check(1)
    
    # Check the error message
    assert "Cannot check dead player" in str(excinfo.value)

def test_sheriff_check_dead_player_fails(game_with_dead_players):
    """Test that sheriff checking a dead player raises an error"""
    game = game_with_dead_players
    
    # Set up for sheriff check phase
    game.current_phase = Phase.NIGHT_SHERIFF
    
    # Make player 0 the sheriff
    game.players[0].role = Role.SHERIFF
    
    # Try to check a dead player (Player 1)
    with pytest.raises(ValueError) as excinfo:
        game.apply_sheriff_check(1)
    
    # Check the error message
    assert "Cannot check dead player" in str(excinfo.value)
