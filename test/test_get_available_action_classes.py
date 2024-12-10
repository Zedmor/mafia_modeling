import pytest
from mafia_game.game_state import CompleteGameState, GameState, PrivateData, PublicData
from mafia_game.common import Role, Team, MAX_PLAYERS
from mafia_game.actions import (
    NominationAction,
    SheriffDeclarationAction,
    PublicSheriffDeclarationAction,
    VoteAction,
    KillAction,
    DonCheckAction,
    SheriffCheckAction,
)
from mafia_game.game_state import (
    DayPhase,
    VotingPhase,
    NightKillPhase,
    NightDonPhase,
    NightSheriffPhase,
)


# Helper function to create a game state with a specific role for testing
def create_game_state_with_role(role: Role, alive: bool = True):
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


def test_get_available_action_classes_day_phase(complete_game_state):
    complete_game_state.current_phase = DayPhase()
    available_actions = complete_game_state.get_available_action_classes()
    assert set(available_actions) == {
        NominationAction,
        SheriffDeclarationAction,
        PublicSheriffDeclarationAction,
    }


def test_get_available_action_classes_voting_phase(complete_game_state):
    complete_game_state.current_phase = VotingPhase()
    available_actions = complete_game_state.get_available_action_classes()
    assert set(available_actions) == {VoteAction}


def test_get_available_action_classes_night_kill_phase(complete_game_state):
    complete_game_state.current_phase = NightKillPhase()
    complete_game_state.game_states[
        complete_game_state.active_player
    ].private_data.role = Role.MAFIA
    available_actions = complete_game_state.get_available_action_classes()
    assert set(available_actions) == {KillAction}


def test_get_available_action_classes_night_don_phase(complete_game_state):
    complete_game_state.current_phase = NightDonPhase()
    complete_game_state.game_states[
        complete_game_state.active_player
    ].private_data.role = Role.DON
    available_actions = complete_game_state.get_available_action_classes()
    assert set(available_actions) == {DonCheckAction}


def test_get_available_action_classes_night_sheriff_phase(complete_game_state):
    complete_game_state.current_phase = NightSheriffPhase()
    complete_game_state.game_states[
        complete_game_state.active_player
    ].private_data.role = Role.SHERIFF
    available_actions = complete_game_state.get_available_action_classes()
    assert set(available_actions) == {SheriffCheckAction}
