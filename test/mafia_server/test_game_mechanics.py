import pytest
import random
import numpy as np
from mafia_server.models import (
    Role, Team, Phase, Player, GameState,
    ActionRequest, ActionResponse, GameEvent
)

@pytest.fixture
def game_state():
    """Fixture to create a standard game state for testing"""
    return GameState.new_game()

def test_phase_transition():
    """Test that phases transition correctly"""
    game = GameState.new_game()
    
    # Initial phase should be DECLARATION
    assert game.current_phase == Phase.DECLARATION
    
    # After all players have made declarations/nominations
    for _ in range(10):
        game._advance_player()
    
    # Game should transition to VOTING phase
    game._transition_phase()
    assert game.current_phase == Phase.VOTING
    
    # After voting is complete
    for _ in range(10):
        game._advance_player()
    
    # Game should transition to NIGHT_KILL phase
    game._transition_phase()
    assert game.current_phase == Phase.NIGHT_KILL

    # After night kill
    game._advance_player()
    
    # Game should transition to NIGHT_DON phase
    game._transition_phase()
    assert game.current_phase == Phase.NIGHT_DON
    
    # After don check
    game._advance_player()
    
    # Game should transition to NIGHT_SHERIFF phase
    game._transition_phase()
    assert game.current_phase == Phase.NIGHT_SHERIFF
    
    # After sheriff check
    game._advance_player()
    
    # Game should transition back to DECLARATION phase for the next turn
    game._transition_phase()
    assert game.current_phase == Phase.DECLARATION
    assert game.turn == 1

def test_get_valid_actions(game_state):
    """Test that valid actions are correctly determined based on phase and player role"""
    # Find sheriff and don
    sheriff_index = None
    don_index = None
    mafia_indices = []
    
    for i, player in enumerate(game_state.players):
        if player.role == Role.SHERIFF:
            sheriff_index = i
        elif player.role == Role.DON:
            don_index = i
        elif player.role == Role.MAFIA:
            mafia_indices.append(i)
    
    assert sheriff_index is not None, "Sheriff not found"
    assert don_index is not None, "Don not found"
    assert len(mafia_indices) > 0, "No mafia players found"
    
    # Test DECLARATION phase for regular player
    game_state.active_player = 0
    if game_state.players[0].role not in [Role.SHERIFF, Role.DON]:
        actions = game_state.get_valid_actions()
        assert "declaration" in actions
        assert "sheriff_claims" in actions
        assert "nomination" in actions
    
    # Test NIGHT_KILL phase - this should only work for Don first, then Mafia if Don is dead
    game_state.current_phase = Phase.NIGHT_KILL
    
    # First, test with Don (should be active killer)
    game_state.active_player = don_index
    actions = game_state.get_valid_actions()
    assert "kill" in actions, f"Don player {don_index} should have kill action"
    
    # If Don is dead, first Mafia should get kill action
    game_state.players[don_index].alive = False
    game_state.active_player = mafia_indices[0]
    actions = game_state.get_valid_actions()
    assert "kill" in actions, f"First Mafia player {mafia_indices[0]} should have kill action when Don is dead"
    
    # Test NIGHT_DON phase for Don
    game_state.current_phase = Phase.NIGHT_DON
    game_state.players[don_index].alive = True  # Revive Don for this test
    game_state.active_player = don_index
    actions = game_state.get_valid_actions()
    assert "don_check" in actions
    
    # Non-Don players should not have don_check action
    game_state.active_player = 0
    if game_state.players[0].role != Role.DON:
        actions = game_state.get_valid_actions()
        assert "don_check" not in actions
    
    # Test NIGHT_SHERIFF phase for Sheriff
    game_state.current_phase = Phase.NIGHT_SHERIFF
    game_state.active_player = sheriff_index
    actions = game_state.get_valid_actions()
    assert "sheriff_check" in actions
    
    # Non-Sheriff players should not have sheriff_check action
    game_state.active_player = 0
    if game_state.players[0].role != Role.SHERIFF:
        actions = game_state.get_valid_actions()
        assert "sheriff_check" not in actions

def test_voting_mechanics(game_state):
    """Test the mechanics of the voting process"""
    # Nominate two players
    game_state.nominated_players = [2, 4]
    
    # Set up votes
    game_state.current_phase = Phase.VOTING
    
    # Simulate voting
    # 4 votes for player 2
    for i in range(4):
        if game_state.players[i].alive:
            game_state.players[i].vote_for = 2
    
    # 3 votes for player 4
    for i in range(4, 7):
        if game_state.players[i].alive:
            game_state.players[i].vote_for = 4
    
    # Process votes
    eliminated_player = game_state._resolve_votes()
    
    # Player 2 should be eliminated
    assert eliminated_player == 2
    assert not game_state.players[2].alive

def test_voting_tie(game_state):
    """Test handling of voting ties"""
    # Nominate two players
    game_state.nominated_players = [2, 4]
    
    # Set up votes for a tie (3 each)
    game_state.current_phase = Phase.VOTING
    
    # 3 votes for player 2
    for i in range(3):
        if game_state.players[i].alive:
            game_state.players[i].vote_for = 2
    
    # 3 votes for player 4
    for i in range(3, 6):
        if game_state.players[i].alive:
            game_state.players[i].vote_for = 4
    
    # Process votes
    eliminated_player = game_state._resolve_votes()
    
    # No player should be eliminated, and we should have tied_players
    assert eliminated_player is None
    assert game_state.voting_round == 1
    assert set(game_state.tied_players) == {2, 4}
    
    # Second round of voting
    # 4 votes for player 2
    for i in range(4):
        if game_state.players[i].alive:
            game_state.players[i].vote_for = 2
    
    # 3 votes for player 4
    for i in range(4, 7):
        if game_state.players[i].alive:
            game_state.players[i].vote_for = 4
    
    # Process votes again
    eliminated_player = game_state._resolve_votes()
    
    # Player 2 should be eliminated
    assert eliminated_player == 2
    assert not game_state.players[2].alive
    assert game_state.voting_round == 0  # Reset after resolution

def test_eliminate_all_vote(game_state):
    """Test the eliminate-all voting mechanism for double ties"""
    # Set up a double tie scenario
    game_state.nominated_players = [2, 4]
    game_state.current_phase = Phase.VOTING
    game_state.voting_round = 1
    game_state.tied_players = [2, 4]
    
    # Simulate first round tie
    for i in range(3):
        if game_state.players[i].alive:
            game_state.players[i].vote_for = 2
    
    for i in range(3, 6):
        if game_state.players[i].alive:
            game_state.players[i].vote_for = 4
    
    # Process votes, should result in second tie
    eliminated_player = game_state._resolve_votes()
    assert eliminated_player is None
    assert game_state.voting_round == 2
    
    # Now simulate eliminate-all vote (6 yes votes out of 10)
    for i in range(6):
        game_state.eliminate_all_votes[i] = 1  # Yes
    
    for i in range(6, 10):
        game_state.eliminate_all_votes[i] = 0  # No
    
    # Process eliminate-all vote
    game_state._resolve_eliminate_all_vote()
    
    # Both players should be eliminated
    assert not game_state.players[2].alive
    assert not game_state.players[4].alive
    assert game_state.voting_round == 0  # Reset after resolution

def test_win_conditions(game_state):
    """Test the win conditions for both teams"""
    # Test Red team win (eliminate all Black team players)
    for player in game_state.players:
        if player.role in [Role.MAFIA, Role.DON]:
            player.alive = False
    
    winner = game_state.check_win_condition()
    assert winner == Team.RED
    
    # Reset for Black team win test
    game_state = GameState.new_game()
    
    # Kill enough Red team players so Black team has majority
    red_players = [i for i, p in enumerate(game_state.players) 
                  if p.role in [Role.CITIZEN, Role.SHERIFF]]
    
    # Kill all but one Red team player
    for idx in red_players[:-1]:
        game_state.players[idx].alive = False
    
    winner = game_state.check_win_condition()
    assert winner == Team.BLACK

def test_night_kill_mechanics(game_state):
    """Test night kill mechanics"""
    # Find a mafia player
    mafia_player = None
    for i, player in enumerate(game_state.players):
        if player.role == Role.MAFIA or player.role == Role.DON:
            mafia_player = i
            break
    
    assert mafia_player is not None
    
    # Set up night kill
    game_state.current_phase = Phase.NIGHT_KILL
    game_state.active_player = mafia_player
    
    # Target player 3 for killing
    kill_target = 3
    
    # Apply kill
    game_state.apply_kill(kill_target)
    
    # Player should be marked for night kill but not yet dead
    # (deaths processed at end of night phase)
    assert game_state.night_kills[kill_target]
    assert game_state.players[kill_target].alive
    
    # Process night phase end
    game_state._process_night_end()
    
    # Now the player should be dead
    assert not game_state.players[kill_target].alive

def test_sheriff_check_mechanics(game_state):
    """Test sheriff check mechanics"""
    # Find the sheriff
    sheriff_index = None
    for i, player in enumerate(game_state.players):
        if player.role == Role.SHERIFF:
            sheriff_index = i
            break
    
    assert sheriff_index is not None
    
    # Find a mafia player to check
    mafia_index = None
    for i, player in enumerate(game_state.players):
        if player.role == Role.MAFIA or player.role == Role.DON:
            mafia_index = i
            break
    
    assert mafia_index is not None
    
    # Find a red player to check
    citizen_index = None
    for i, player in enumerate(game_state.players):
        if player.role == Role.CITIZEN:
            citizen_index = i
            break
    
    assert citizen_index is not None
    
    # Setup sheriff check phase
    game_state.current_phase = Phase.NIGHT_SHERIFF
    game_state.active_player = sheriff_index
    
    # Check mafia player
    result = game_state.apply_sheriff_check(mafia_index)
    assert result == Team.BLACK
    
    # Check citizen player
    result = game_state.apply_sheriff_check(citizen_index)
    assert result == Team.RED
    
    # Verify the sheriff's private info is updated
    assert sheriff_index in game_state.private_checks
    assert mafia_index in game_state.private_checks[sheriff_index]
    assert game_state.private_checks[sheriff_index][mafia_index] == Team.BLACK
    assert citizen_index in game_state.private_checks[sheriff_index]
    assert game_state.private_checks[sheriff_index][citizen_index] == Team.RED

def test_don_check_mechanics(game_state):
    """Test Don check mechanics"""
    # Find the don
    don_index = None
    for i, player in enumerate(game_state.players):
        if player.role == Role.DON:
            don_index = i
            break
    
    assert don_index is not None
    
    # Find the sheriff
    sheriff_index = None
    for i, player in enumerate(game_state.players):
        if player.role == Role.SHERIFF:
            sheriff_index = i
            break
    
    assert sheriff_index is not None
    
    # Find a citizen
    citizen_index = None
    for i, player in enumerate(game_state.players):
        if player.role == Role.CITIZEN:
            citizen_index = i
            break
    
    assert citizen_index is not None
    
    # Setup don check phase
    game_state.current_phase = Phase.NIGHT_DON
    game_state.active_player = don_index
    
    # Check sheriff
    result = game_state.apply_don_check(sheriff_index)
    assert result is True
    
    # Check citizen
    result = game_state.apply_don_check(citizen_index)
    assert result is False
    
    # Verify the don's private info is updated
    assert don_index in game_state.private_checks
    assert sheriff_index in game_state.private_checks[don_index]
    assert game_state.private_checks[don_index][sheriff_index] is True
    assert citizen_index in game_state.private_checks[don_index]
    assert game_state.private_checks[don_index][citizen_index] is False
