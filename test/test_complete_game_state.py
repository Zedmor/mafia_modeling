import pytest

from mafia_game.common import MAX_TURNS, Team
from mafia_game.game_state import (
    ARRAY_SIZE,
    CompleteGameState,
    DayPhase,
    EndPhase,
    GameState,
    NightDonPhase,
    PrivateData,
    PublicData,
    Role,
)
import numpy as np

# Assuming MAX_PLAYERS is defined in your_game_module
MAX_PLAYERS = 10


# Helper function to create a GameState with dummy data for testing
def create_dummy_game_state(player_role):
    private_data = PrivateData(role=player_role)
    public_data = PublicData()
    return GameState(private_data=private_data, public_data=public_data)


# Test serialization of CompleteGameState
def test_complete_game_state_serialization():
    complete_game_state = CompleteGameState(
        game_states=[create_dummy_game_state(Role.CITIZEN) for _ in range(MAX_PLAYERS)],
        team_won=Team.RED_TEAM,
        turn=5,
    )
    serialized_state = complete_game_state.serialize()
    assert isinstance(serialized_state, np.ndarray)
    assert serialized_state.size == MAX_PLAYERS * ARRAY_SIZE + 4

    reconstructed_object = CompleteGameState.deserialize(serialized_state)
    assert reconstructed_object.turn == 5
    assert reconstructed_object.team_won == Team.RED_TEAM


# Test deserialization of CompleteGameState
def test_complete_game_state_deserialization():
    # Create a serialized state with dummy data
    game_states = [
        create_dummy_game_state(Role.CITIZEN).serialize() for _ in range(MAX_PLAYERS)
    ]
    active_player = 5
    game_phase = DayPhase()
    team_won = Team.UNKNOWN
    turn = 5
    serialized_state = np.concatenate(
        [
            np.concatenate(game_states),
            np.array([active_player]),
            np.array([game_phase.value]),
            np.array([turn]),
            np.array([team_won]),
        ]
    )
    deserialized_state = CompleteGameState.deserialize(serialized_state)
    assert isinstance(deserialized_state, CompleteGameState)
    assert len(deserialized_state.game_states) == MAX_PLAYERS
    assert deserialized_state.turn == 5
    assert deserialized_state.team_won == Team.UNKNOWN
    for game_state in deserialized_state.game_states:
        assert game_state.private_data.role == Role.CITIZEN


# Test deserializing from a specific player's perspective
@pytest.mark.parametrize("player_index", range(MAX_PLAYERS))
def test_deserialize_from_specific_player_perspective(player_index):
    # Create a serialized state with dummy data
    game_phase = NightDonPhase()
    active_player = 5
    game_states = [
        create_dummy_game_state(
            Role.CITIZEN if i == player_index else Role.MAFIA
        ).serialize()
        for i in range(MAX_PLAYERS)
    ]
    turn = 0
    team_won = Team.UNKNOWN
    serialized_state = np.concatenate(
        [
            np.concatenate(game_states),
            np.array([active_player]),
            np.array([game_phase.value]),
            np.array([turn]),
            np.array([team_won]),
        ]
    )

    complete_game_state = CompleteGameState.deserialize(serialized_state)
    player_perspective_state = complete_game_state.deserialize_from(player_index)

    # The specified player's role should be correct, and all others should be UNKNOWN
    for i, game_state in enumerate(player_perspective_state.game_states):
        if i == player_index:
            assert game_state.private_data.role == Role.CITIZEN
        else:
            assert game_state.private_data.role == Role.UNKNOWN


# Test updating the turn in GameState
def test_game_state_update_turn():
    private_data = PrivateData(role=Role.CITIZEN)
    public_data = PublicData()
    game_state = GameState(private_data=private_data, public_data=public_data)
    complete_game_state = CompleteGameState(game_states=[game_state])
    complete_game_state.update_turn()
    assert complete_game_state.turn == 1


# Test updating the turn beyond the maximum in GameState
def test_game_state_update_turn_max():
    private_data = PrivateData(role=Role.CITIZEN)
    public_data = PublicData()
    game_state = GameState(private_data=private_data, public_data=public_data)
    complete_game_state = CompleteGameState(
        game_states=[game_state], turn=MAX_TURNS - 1
    )
    with pytest.raises(ValueError):
        complete_game_state.update_turn()


def create_game_state_with_role(role: Role, alive: int = 1):
    return GameState(
        private_data=PrivateData(role=role), public_data=PublicData(), alive=alive
    )


@pytest.fixture
def complete_game_state():
    # Create a complete game state with all players as CITIZEN and alive
    game_states = [
        create_game_state_with_role(Role.CITIZEN) for _ in range(MAX_PLAYERS)
    ]
    return CompleteGameState(
        game_states=game_states,
        current_phase=DayPhase(),
        active_player=0,
        turn=0,
        team_won=Team.UNKNOWN,
    )


def test_check_end_conditions_mafia_wins(complete_game_state):
    # Set up a scenario where the Mafia wins (more Mafia than Citizens)
    for i in range(3):
        complete_game_state.game_states[i].private_data.role = Role.MAFIA
    for i in range(3, 7):
        complete_game_state.game_states[i].alive = 0  # Eliminate some Citizens

    complete_game_state.check_end_conditions()
    assert complete_game_state.team_won == Team.BLACK_TEAM
    assert isinstance(complete_game_state.current_phase, EndPhase)


def test_check_end_conditions_citizens_win(complete_game_state):
    # Set up a scenario where the Citizens win (all Mafia eliminated)
    for i in range(3):
        complete_game_state.game_states[i].private_data.role = Role.MAFIA
        complete_game_state.game_states[i].alive = 0  # Eliminate all Mafia

    complete_game_state.check_end_conditions()
    assert complete_game_state.team_won == Team.RED_TEAM
    assert isinstance(complete_game_state.current_phase, EndPhase)


def test_check_end_conditions_no_winner(complete_game_state):
    # Set up a scenario where there is no winner yet
    for i in range(2):
        complete_game_state.game_states[i].private_data.role = Role.MAFIA
    complete_game_state.game_states[
        2
    ].private_data.role = Role.DON  # Keep one Mafia alive

    complete_game_state.check_end_conditions()
    assert complete_game_state.team_won == Team.UNKNOWN
    assert not isinstance(complete_game_state.current_phase, EndPhase)
