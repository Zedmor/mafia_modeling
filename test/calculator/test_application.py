import pytest

from calculator_old.console_app import process_input_lines
from calculator_old.models import BeliefType, Game, Player


@pytest.fixture
def game():
    # Initialize the game with 5 players for testing
    players = [Player(player_id=i) for i in range(5)]
    return Game(players)


def test_process_input_lines_valid_input(game):
    player_id = 0
    player_lines = ["2++", "3---", "4++"]
    process_input_lines(game, player_id, player_lines)
    assert len(game.players[player_id].beliefs) == 3
    assert game.players[player_id].beliefs[0].belief_strength == 0.6
    assert game.players[player_id].beliefs[0].target_player == 1
    assert game.players[player_id].beliefs[1].belief_strength == 1.0
    assert game.players[player_id].beliefs[1].belief_type == BeliefType.BLACK
    assert game.players[player_id].beliefs[1].target_player == 2
    assert game.players[player_id].beliefs[2].belief_strength == 0.6
    assert game.players[player_id].beliefs[2].target_player == 3


def test_process_input_lines_invalid_input(game):
    player_id = 0
    player_lines = ["2xx", "3---", "invalid"]
    process_input_lines(game, player_id, player_lines)
    assert len(game.players[player_id].beliefs) == 1
    assert game.players[player_id].beliefs[0].belief_strength == 1.0
    assert game.players[player_id].beliefs[0].belief_type == BeliefType.BLACK


def test_process_input_lines_empty_input(game):
    player_id = 0
    player_lines = []
    process_input_lines(game, player_id, player_lines)
    assert len(game.players[player_id].beliefs) == 0


# Add more tests as needed to cover different scenarios and edge cases
