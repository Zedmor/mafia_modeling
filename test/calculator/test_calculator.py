import numpy as np
import pytest
from calculator_old.models import (
    BeliefType,
    Player,
    Game,
    Belief,
    BeliefCalculator,
    create_initial_belief_matrix,
)


@pytest.fixture
def game_with_players():
    players = [Player(player_id=i, role=None) for i in range(4)]
    game = Game(players)
    return game


@pytest.fixture
def belief_calculator(game_with_players):
    return BeliefCalculator(game_with_players)


def test_belief_calculator_initialization(belief_calculator):
    assert isinstance(belief_calculator, BeliefCalculator)
    assert belief_calculator.probabilities == {}


def test_calculate_probabilities_no_beliefs(belief_calculator):
    belief_calculator.calculate_probabilities()
    for player_id in belief_calculator.probabilities:
        assert belief_calculator.probabilities[player_id] == 0


def test_update_beliefs_and_calculate_probabilities(
    belief_calculator, game_with_players
):
    # Record some beliefs
    game_with_players.players[0].record_belief(
        target_player=1, belief_type=BeliefType.RED, belief_strength=0.8
    )
    game_with_players.players[1].record_belief(
        target_player=2, belief_type=BeliefType.BLACK, belief_strength=0.5
    )

    # Update beliefs and calculate probabilities
    belief_calculator.update_beliefs(
        source_player=game_with_players.players[0],
        target_player=1,
        belief_type=BeliefType.RED,
        belief_strength=0.8,
    )
    belief_calculator.update_beliefs(
        source_player=game_with_players.players[1],
        target_player=2,
        belief_type=BeliefType.BLACK,
        belief_strength=0.5,
    )

    # Check updated combined beliefs
    belief_calculator.calculate_probabilities()
    assert belief_calculator.probabilities[1] == 0.8
    assert belief_calculator.probabilities[2] == -0.5


def test_create_weighted_initial_belief_matrix():
    game = Game(players=[Player(player_id=i) for i in range(4)])
    game.players[0].add_belief(
        Belief(
            source_player=0,
            target_player=1,
            belief_type=BeliefType.BLACK,
            belief_strength=0.5,
        )
    )
    game.players[0].add_belief(
        Belief(
            source_player=0,
            target_player=1,
            belief_type=BeliefType.RED,
            belief_strength=0.8,
        )
    )
    game.players[1].add_belief(
        Belief(
            source_player=1,
            target_player=2,
            belief_type=BeliefType.RED,
            belief_strength=0.9,
        )
    )

    belief_matrix = create_initial_belief_matrix(game)

    # Calculate expected values
    player_0_belief_1 = (1 * -0.5 + 2 * 0.8) / (
        1 + 2
    )  # Weighted average for player 0's beliefs about player 1
    player_1_belief_2 = (
        0.9  # Player 1's belief about player 2 (only one belief, so it's the same)
    )

    expected_matrix = np.array(
        [
            [1.0, player_0_belief_1, 0.0, 0.0],
            [0.0, 1.0, player_1_belief_2, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )

    np.testing.assert_almost_equal(belief_matrix, expected_matrix, decimal=5)


@pytest.mark.parametrize(
    "initial_beliefs, expected_updated_beliefs",
    [
        # Scenario 1: Simple influence with no conflicts
        (
            {
                0: [(1, BeliefType.RED, 0.95)],
                1: [(2, BeliefType.RED, 0.95)],
                2: [(3, BeliefType.RED, 0.95)],
                3: [(0, BeliefType.RED, 0.95)],
            },
            np.array(
                [
                    [1.0, 0.95, 0.45, 0.21],
                    [0.21, 1.0, 0.95, 0.45],
                    [0.45, 0.21, 1.0, 0.95],
                    [0.95, 0.45, 0.21, 1.0],
                ]
            ),
        ),
        # Scenario 2: Conflicting beliefs
        (
            {
                0: [(1, BeliefType.RED, 0.95), (2, BeliefType.BLACK, 1)],
                1: [(0, BeliefType.RED, 0.95), (2, BeliefType.RED, 0.95)],
                2: [(3, BeliefType.RED, 0.95)],
                3: [(2, BeliefType.BLACK, 0.95)],
            },
            np.array(
                [
                    [1.0, 0.95, -1.0, 0.27],
                    [0.95, 1.0, 0.26, 0.58],
                    [0.0, 0.0, 1.0, 0.95],
                    [0.0, 0.0, -0.95, 1.0],
                ]
            ),
        ),
        # Add more scenarios as needed
    ],
)
def test_update_belief_matrix(initial_beliefs, expected_updated_beliefs):
    # Create a game with players and beliefs based on the scenario
    game = Game(players=[Player(player_id=i) for i in range(4)])
    for player_id, beliefs in initial_beliefs.items():
        for target_player, belief_type, belief_strength in beliefs:
            game.players[player_id].add_belief(
                Belief(
                    source_player=player_id,
                    target_player=target_player,
                    belief_type=belief_type,
                    belief_strength=belief_strength,
                )
            )

    # Create the initial belief matrix
    initial_matrix = create_initial_belief_matrix(game)

    calculator = BeliefCalculator(game)

    # Update the belief matrix
    updated_matrix = calculator.update_belief_matrix(initial_matrix)

    # Check if the updated belief matrix matches the expected matrix
    np.testing.assert_almost_equal(updated_matrix, expected_updated_beliefs, decimal=2)


def test_update_belief_matrix_simple():
    players = [Player(player_id=i, role=None) for i in range(2)]
    game = Game(players)
    original_matrix = np.array([[1, 0.6], [0, 1]])
    calculator = BeliefCalculator(game)
    updated_matrix = calculator.update_belief_matrix(original_matrix)
    np.testing.assert_almost_equal(updated_matrix, original_matrix)
