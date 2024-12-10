from unittest.mock import MagicMock

import pytest
from mafia_game.game_state import CompleteGameState, GameState, PrivateData, PublicData
from mafia_game.actions import *
from mafia_game.common import Team, Role, MAX_PLAYERS


# Helper function to create a default game state for testing
def create_test_game_state():
    game_states = [
        GameState(
            private_data=PrivateData(role=Role.UNKNOWN),
            public_data=PublicData(),
        )
        for _ in range(MAX_PLAYERS)
    ]
    complete_game_state = CompleteGameState(game_states=game_states)
    return complete_game_state



# Test KillAction
def test_kill_action():
    game_state = create_test_game_state()
    action = KillAction(player_index=0, target_player=1)
    action.apply(game_state)
    assert game_state.game_states[0].public_data.kills.checks[game_state.turn][1] == 1
    assert game_state.game_states[1].alive == 0


# Test NominationAction
def test_nomination_action():
    game_state = create_test_game_state()
    action = NominationAction(player_index=0, target_player=1)
    action.apply(game_state)
    assert (
        game_state.game_states[0].public_data.nominations.checks[game_state.turn][1]
        == 1
    )


def test_sheriff_check_action():
    game_state = create_test_game_state()
    # Set the role of the target player to MAFIA for the test
    game_state.game_states[1].private_data.role = Role.MAFIA
    action = SheriffCheckAction(player_index=0, target_player=1)
    action.apply(game_state)
    assert (
        game_state.game_states[0].private_data.sheriff_checks.checks[game_state.turn][1]
        == Team.BLACK_TEAM.value
    )


# Test DonCheckAction
def test_don_check_action():
    game_state = create_test_game_state()
    # Set the role of the target player to SHERIFF for the test
    game_state.game_states[1].private_data.role = Role.SHERIFF
    action = DonCheckAction(player_index=0, target_player=1)
    action.apply(game_state)
    assert (
        game_state.game_states[0].private_data.don_checks.checks[game_state.turn][1]
        == 1
    )


# Test SheriffDeclarationAction
def test_sheriff_declaration_action():
    game_state = create_test_game_state()
    action = SheriffDeclarationAction(player_index=0, i_am_sheriff=True)
    action.apply(game_state)
    assert (
        game_state.game_states[0].public_data.sheriff_declaration[game_state.turn] == 1
    )


# Test PublicSheriffDeclarationAction
def test_public_sheriff_declaration_action():
    game_state = create_test_game_state()
    action = PublicSheriffDeclarationAction(
        player_index=0, target_player=1, team=Team.BLACK_TEAM
    )
    action.apply(game_state)
    assert (
        game_state.game_states[0].public_data.public_sheriff_checks.checks[
            game_state.turn
        ][1]
        == Team.BLACK_TEAM.value
    )


# Test VoteAction
def test_vote_action():
    game_state = create_test_game_state()
    action = VoteAction(player_index=0, target_player=1)
    action.apply(game_state)
    assert game_state.game_states[0].public_data.votes.checks[game_state.turn][1] == 1


@pytest.fixture
def mock_game_state():
    game_state = MagicMock(spec=CompleteGameState)
    game_state.game_states = [
        MagicMock(alive=True, private_data=MagicMock(role=Role.CITIZEN))
        for _ in range(10)
    ]
    game_state.turn = 0
    game_state.nominated_players = []
    return game_state


# Test the from_index method of PublicSheriffDeclarationAction
def test_public_sheriff_declaration_action_from_index(mock_game_state):
    player_index = 0
    action_index = 5  # Should correspond to the second player and RED_TEAM
    action = PublicSheriffDeclarationAction.from_index(
        action_index, mock_game_state, player_index
    )
    assert isinstance(action, PublicSheriffDeclarationAction)
    assert action.target_player == 2
    assert action.role == Team.RED_TEAM


# Test the apply method of KillAction
def test_kill_action_apply(mock_game_state):
    player_index = 0
    target_player = 1
    action = KillAction(player_index, target_player)
    action.apply(mock_game_state)
    assert not mock_game_state.game_states[target_player].alive


def test_public_sheriff_declaration_action_from_index(mock_game_state):
    player_index = 0
    # Test various action indices
    for action_index in range(20):
        action = PublicSheriffDeclarationAction.from_index(action_index, mock_game_state, player_index)
        expected_target_player = action_index // 2
        expected_team = Team.BLACK_TEAM if action_index % 2 == 0 else Team.RED_TEAM
        assert isinstance(action, PublicSheriffDeclarationAction)
        assert action.target_player == expected_target_player
        assert action.role == expected_team

# Test that from_index handles out-of-range indices by wrapping around or clamping
def test_public_sheriff_declaration_action_from_index_out_of_range(mock_game_state):
    player_index = 0
    # Test out-of-range action indices
    out_of_range_indices = [-1, 20, 21]  # Assuming there are 10 players and indices should be in range [0, 19]
    for action_index in out_of_range_indices:
        # Wrap around or clamp the action_index to a valid range
        valid_action_index = action_index % 20 if action_index >= 0 else 0
        action = PublicSheriffDeclarationAction.from_index(valid_action_index, mock_game_state, player_index)
        expected_target_player = valid_action_index // 2
        expected_team = Team.BLACK_TEAM if valid_action_index % 2 == 0 else Team.RED_TEAM
        assert action.target_player == expected_target_player
        assert action.role == expected_team

# Test that from_index handles negative indices by wrapping around
def test_public_sheriff_declaration_action_from_index_negative(mock_game_state):
    player_index = 0
    # Test negative action indices
    negative_indices = [-2, -3, -19]
    for action_index in negative_indices:
        # Wrap around to a valid range
        valid_action_index = action_index % 20
        action = PublicSheriffDeclarationAction.from_index(valid_action_index, mock_game_state, player_index)
        expected_target_player = valid_action_index // 2
        expected_team = Team.BLACK_TEAM if valid_action_index % 2 == 0 else Team.RED_TEAM
        assert action.target_player == expected_target_player
        assert action.role == expected_team
