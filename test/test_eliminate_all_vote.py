import numpy as np
import pytest
import torch

from mafia_game.actions import EliminateAllNominatedVoteAction
from mafia_game.common import Role, Team
from mafia_game.game_state import CompleteGameState, VotingPhase


def test_eliminate_all_nominated_vote_action_creation():
    # Test creating the action
    action = EliminateAllNominatedVoteAction(player_index=0, eliminate_all=True)
    assert action.player_index == 0
    assert action.eliminate_all is True
    
    action = EliminateAllNominatedVoteAction(player_index=1, eliminate_all=False)
    assert action.player_index == 1
    assert action.eliminate_all is False


def test_eliminate_all_nominated_vote_action_from_index():
    # Test creating the action from index
    game = CompleteGameState.build()
    
    # Index 0 should create action with eliminate_all=False
    action = EliminateAllNominatedVoteAction.from_index(0, game, 1)
    assert action.player_index == 1
    assert action.eliminate_all is False
    
    # Index 1 should create action with eliminate_all=True
    action = EliminateAllNominatedVoteAction.from_index(1, game, 2)
    assert action.player_index == 2
    assert action.eliminate_all is True


def test_eliminate_all_nominated_vote_action_apply():
    # Test applying the action
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 2
    
    # Player 0 votes to eliminate all
    action = EliminateAllNominatedVoteAction(0, True)
    action.apply(game)
    assert game.eliminate_all_votes[0] == 1
    
    # Player 1 votes not to eliminate all
    action = EliminateAllNominatedVoteAction(1, False)
    action.apply(game)
    assert game.eliminate_all_votes[1] == 0


def test_eliminate_all_nominated_vote_action_mask():
    # Test the action mask
    game = CompleteGameState.build()
    
    # The mask should always be [1, 1] (both options available)
    mask = EliminateAllNominatedVoteAction.generate_action_mask(game, 0)
    assert torch.all(torch.eq(mask, torch.ones(2, dtype=torch.float32)))


def test_resolve_eliminate_all_vote_majority_yes():
    # Test resolving the eliminate all vote with majority yes
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 2
    
    # Set up 6 yes votes out of 10 players
    for i in range(6):
        game.eliminate_all_votes[i] = 1
    
    # Resolve the vote
    game.resolve_eliminate_all_vote()
    
    # Both tied players should be eliminated
    assert game.game_states[1].alive == 0
    assert game.game_states[2].alive == 0
    
    # Voting state should be reset
    assert game.voting_round == 0
    assert len(game.tied_players) == 0
    assert np.all(game.eliminate_all_votes == 0)


def test_resolve_eliminate_all_vote_majority_no():
    # Test resolving the eliminate all vote with majority no
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 2
    
    # Set up 4 yes votes out of 10 players
    for i in range(4):
        game.eliminate_all_votes[i] = 1
    
    # Resolve the vote
    game.resolve_eliminate_all_vote()
    
    # Both tied players should still be alive
    assert game.game_states[1].alive == 1
    assert game.game_states[2].alive == 1
    
    # Voting state should be reset
    assert game.voting_round == 0
    assert len(game.tied_players) == 0
    assert np.all(game.eliminate_all_votes == 0)


def test_resolve_eliminate_all_vote_with_dead_players():
    # Test resolving the eliminate all vote with some dead players
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 2
    
    # Kill some players
    game.game_states[3].alive = 0
    game.game_states[4].alive = 0
    
    # Set up 5 yes votes out of 8 alive players (should be majority)
    for i in range(5):
        game.eliminate_all_votes[i] = 1
    
    # Resolve the vote
    game.resolve_eliminate_all_vote()
    
    # Both tied players should be eliminated
    assert game.game_states[1].alive == 0
    assert game.game_states[2].alive == 0


def test_voting_phase_transition_with_eliminate_all_vote():
    # Test the voting phase transition with eliminate all vote
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 2
    game.current_phase = VotingPhase()
    
    # Set up 6 yes votes
    for i in range(6):
        game.eliminate_all_votes[i] = 1
    
    # Get the next phase
    next_phase = game.current_phase.next_phase(game)
    
    # Should transition to NightKillPhase
    assert next_phase.__class__.__name__ == "NightKillPhase"
    
    # Tied players should be eliminated
    assert game.game_states[1].alive == 0
    assert game.game_states[2].alive == 0


def test_get_available_action_classes_in_third_voting_round():
    # Test getting available action classes in third voting round
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 2
    game.current_phase = VotingPhase()
    
    # Get available action classes
    action_classes = game.get_available_action_classes()
    
    # Should only include EliminateAllNominatedVoteAction
    assert len(action_classes) == 1
    assert action_classes[0] == EliminateAllNominatedVoteAction


def test_full_voting_sequence_with_eliminate_all():
    # Test a full voting sequence ending with eliminate all vote
    game = CompleteGameState.build()
    game.nominated_players = [1, 2]
    game.current_phase = VotingPhase()
    
    # First round: tie between players 1 and 2
    for i in range(2):
        game.game_states[i].public_data.votes.checks[game.turn].checks[1] = 1
    
    for i in range(2, 4):
        game.game_states[i].public_data.votes.checks[game.turn].checks[2] = 1
    
    # Resolve first round votes
    game.resolve_votes()
    assert game.voting_round == 1
    assert 1 in game.tied_players
    assert 2 in game.tied_players
    
    # Second round: tie again
    for i in range(2):
        game.game_states[i].public_data.votes.checks[game.turn].checks[1] = 1
    
    for i in range(2, 4):
        game.game_states[i].public_data.votes.checks[game.turn].checks[2] = 1
    
    # Resolve second round votes
    game.resolve_votes()
    assert game.voting_round == 2
    assert 1 in game.tied_players
    assert 2 in game.tied_players
    
    # Third round: vote to eliminate all
    for i in range(6):
        game.eliminate_all_votes[i] = 1  # Vote yes
    
    # Resolve eliminate all vote
    game.resolve_eliminate_all_vote()
    assert game.voting_round == 0
    assert len(game.tied_players) == 0
    assert game.game_states[1].alive == 0
    assert game.game_states[2].alive == 0
