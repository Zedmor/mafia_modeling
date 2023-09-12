import pytest
import torch

from mafia_game.models import (
    Player,
    Role,
    GameState,
    GameAction,
    GameActionType,
    Belief,
)
from mafia_game.nn_policy import NeuralNetworkCitizenPolicy


@pytest.fixture
def game_state():
    players = [Player(i, Role.CITIZEN, None) for i in range(10)]
    game_state = GameState(players)
    game_state.game_actions = [
        GameAction(GameActionType.DECLARATION, players[0], players[1], Belief.MAFIA),
        GameAction(GameActionType.NOMINATION, players[0], players[1]),
        GameAction(GameActionType.VOTE, players[0], players[1]),
        GameAction(GameActionType.KILL, players[0], players[1]),
        GameAction(
            GameActionType.FINAL_DECLARATION, players[0], players[1], Belief.MAFIA
        ),
    ]
    return game_state


@pytest.fixture
def policy():
    return NeuralNetworkCitizenPolicy(num_players=10)


def test_get_game_state_vector(game_state, policy):
    vector = game_state.get_game_state_vector(game_state.players[0])
    assert len(vector) == 3030
    assert vector[0] == 1
    assert vector[1] == 0


def test_get_state_vector(game_state, policy):
    vector = game_state.get_state_vector(
        game_state.players[0], "make_declarations"
    )
    assert len(vector) == 3030 + 4
    assert vector[0] == 1
    assert vector[1] == 0


def test_get_declarations_from_vector(game_state, policy):
    action_vector = torch.randn(20)
    declarations = policy._get_declarations_from_vector(action_vector, game_state)
    assert len(declarations) <= 3
    for declaration in declarations:
        assert isinstance(declaration[0], Player)
        assert isinstance(declaration[1], Belief)


def test_get_vote_from_vector(game_state, policy):
    game_state.nominated_players = [game_state.players[0]]
    action_vector = torch.randn(94)
    masked = action_vector.masked_fill(~game_state.create_mask("vote"), -1e9)
    vote = policy._get_vote_from_vector(masked, game_state)
    assert isinstance(vote, Player)
    assert vote.id == 0


def test_get_nomination_from_vector(game_state, policy):
    action_vector = torch.randn(10)
    nomination = policy._get_nomination_from_vector(action_vector, game_state)
    assert isinstance(nomination, Player) or nomination is None


def test_create_mask(game_state):
    mask = game_state.create_mask("vote")
    vector = torch.Tensor([1] * 94)
    masked = vector.masked_fill(~mask, -1e9)
    assert masked[33] < 0
    game_state.nominated_players.append(game_state.players[0])

    mask = game_state.create_mask("vote")
    vector = torch.Tensor([1] * 94)
    masked = vector.masked_fill(~mask, -1e9)
    assert masked[0] > 0
