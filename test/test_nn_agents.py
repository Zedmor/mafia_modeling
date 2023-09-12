import random
import pytest
from mafia_game.models import Role, Player, GameState, GameController
from mafia_game.nn_policy import NeuralNetworkCitizenPolicy
from mafia_game.policies import StaticCitizenPolicy, StaticMafiaPolicy


@pytest.fixture(scope="session")
def win_counter():
    return {Role.CITIZEN: 0, Role.MAFIA: 0}


games_to_run = 100


@pytest.mark.parametrize("game_number", range(games_to_run))
def test_random_game(game_number, win_counter):
    num_players = 10
    citizen_policy = NeuralNetworkCitizenPolicy(num_players)

    mafia_policy = StaticMafiaPolicy()
    players = [Player(i, Role.CITIZEN, citizen_policy) for i in range(7)]
    players += [Player(i, Role.MAFIA, mafia_policy) for i in range(7, 10)]
    random.shuffle(players)
    for i, player in enumerate(players, 0):
        player.id = i
    game_state = GameState(players)
    game_controller = GameController(game_state)
    winner = game_controller.start_game()
    win_counter[winner] += 1
    print(f"Game #{game_number}: {winner.value} team won")
    if game_number == games_to_run - 1:  # last game
        total_games = win_counter[Role.CITIZEN] + win_counter[Role.MAFIA]
        print(f"Citizen win rate: {win_counter[Role.CITIZEN] / total_games * 100}%")
        print(f"Mafia win rate: {win_counter[Role.MAFIA] / total_games * 100}%")
