"""
Tests for legal action masking functionality.
"""
import pytest
import numpy as np

from mafia_game.game_state import CompleteGameState, DayPhase, VotingPhase, NightKillPhase, NightSheriffPhase
from mafia_game.actions import NominationAction, VoteAction, KillAction, SheriffCheckAction, NullAction
from mafia_game.common import Role, Team
from mafia_transformer.legal_mask import LegalActionMasker, generate_legal_mask, generate_factorized_masks, is_legal_action_sequence
from mafia_transformer.token_vocab import TokenID, VOCAB_SIZE
from mafia_transformer.token_encoder import encode_action


class TestLegalActionMasker:
    
    def setup_method(self):
        """Set up test fixtures."""
        self.masker = LegalActionMasker()
        self.game_state = CompleteGameState.build(use_test_agents=True)
    
    def test_basic_mask_generation(self):
        """Test basic legal mask generation."""
        # Test day phase - should allow nominations and END_TURN
        self.game_state.current_phase = DayPhase()
        mask = self.masker.generate_legal_mask(self.game_state, 0)
        
        # Check mask properties
        assert isinstance(mask, np.ndarray)
        assert mask.shape == (VOCAB_SIZE,)
        assert mask.dtype == bool
        
        # END_TURN should always be legal
        assert mask[TokenID.END_TURN]
        
        # Should have at least one legal action
        assert np.any(mask)
    
    def test_day_phase_legal_actions(self):
        """Test legal actions during day phase."""
        self.game_state.current_phase = DayPhase()
        self.game_state.turn = 1  # Not turn 0, so nominations are allowed
        
        # Player 0 should be able to nominate other alive players
        mask = self.masker.generate_legal_mask(self.game_state, 0)
        
        # NOMINATE verb should be legal
        assert mask[TokenID.NOMINATE]
        
        # Player tokens for alive players (except self) should be legal as targets
        for i in range(10):
            if i != 0 and self.game_state.game_states[i].alive:
                player_token = TokenID.PLAYER_0 + i
                assert mask[player_token], f"Player {i} should be legal target"
    
    def test_voting_phase_legal_actions(self):
        """Test legal actions during voting phase."""
        # Set up voting phase with nominated players
        self.game_state.current_phase = VotingPhase()
        self.game_state.nominated_players = [1, 2]
        self.game_state.voting_round = 0
        
        mask = self.masker.generate_legal_mask(self.game_state, 0)
        
        # VOTE verb should be legal
        assert mask[TokenID.VOTE]
        
        # Only nominated players should be legal targets
        assert mask[TokenID.PLAYER_1]  # Player 1 is nominated
        assert mask[TokenID.PLAYER_2]  # Player 2 is nominated
        assert not mask[TokenID.PLAYER_3]  # Player 3 is not nominated
    
    def test_night_kill_phase_legal_actions(self):
        """Test legal actions during night kill phase."""
        self.game_state.current_phase = NightKillPhase()
        
        # Find a mafia/don player
        mafia_player = None
        for i, state in enumerate(self.game_state.game_states):
            if state.private_data.role in [Role.MAFIA, Role.DON] and state.alive:
                mafia_player = i
                break
        
        assert mafia_player is not None, "Should have at least one alive mafia player"
        
        # Set the active player to the killer
        killer_index = self.game_state.index_of_night_killer()
        mask = self.masker.generate_legal_mask(self.game_state, killer_index)
        
        # Only the killer should be able to use KILL
        if killer_index == mafia_player:
            assert mask[TokenID.KILL]
        else:
            # Other players should not be able to kill
            other_mask = self.masker.generate_legal_mask(self.game_state, 0)  # Assume 0 is not killer
            if self.game_state.game_states[0].private_data.role not in [Role.MAFIA, Role.DON]:
                assert not other_mask[TokenID.KILL]
    
    def test_sheriff_check_phase_legal_actions(self):
        """Test legal actions during sheriff check phase."""
        self.game_state.current_phase = NightSheriffPhase()
        
        # Find the sheriff
        sheriff_player = None
        for i, state in enumerate(self.game_state.game_states):
            if state.private_data.role == Role.SHERIFF and state.alive:
                sheriff_player = i
                break
        
        assert sheriff_player is not None, "Should have a sheriff player"
        
        mask = self.masker.generate_legal_mask(self.game_state, sheriff_player)
        
        # SHERIFF_CHECK should be legal for sheriff
        assert mask[TokenID.SHERIFF_CHECK]
        
        # Other alive players should be legal targets
        for i in range(10):
            if i != sheriff_player and self.game_state.game_states[i].alive:
                player_token = TokenID.PLAYER_0 + i
                assert mask[player_token]
    
    def test_end_turn_always_legal(self):
        """Test that END_TURN is legal except during voting phases."""
        # Test different phases (excluding VotingPhase where END_TURN is not allowed)
        phases = [DayPhase(), NightKillPhase(), NightSheriffPhase()]
        
        for phase in phases:
            self.game_state.current_phase = phase
            for player_index in range(10):
                if self.game_state.game_states[player_index].alive:
                    mask = self.masker.generate_legal_mask(self.game_state, player_index)
                    assert mask[TokenID.END_TURN], f"END_TURN should be legal in {phase} for player {player_index}"
        
        # Test VotingPhase separately - END_TURN should NOT be legal
        self.game_state.current_phase = VotingPhase()
        self.game_state.nominated_players = [1, 2]  # Ensure there are nominated players
        self.game_state.voting_round = 0
        mask = self.masker.generate_legal_mask(self.game_state, 0)
        assert not mask[TokenID.END_TURN], "END_TURN should NOT be legal during voting phase"
    
    def test_factorized_masks(self):
        """Test factorized mask generation."""
        self.game_state.current_phase = DayPhase()
        self.game_state.turn = 1
        
        factorized = self.masker.generate_factorized_masks(self.game_state, 0)
        
        # Check structure
        assert 'verbs' in factorized
        assert 'players' in factorized
        assert 'colors' in factorized
        
        # Check types and shapes
        assert isinstance(factorized['verbs'], np.ndarray)
        assert isinstance(factorized['players'], np.ndarray)
        assert isinstance(factorized['colors'], np.ndarray)
        
        # Verbs should include END_TURN and NOMINATE
        assert factorized['verbs'][0]  # END_TURN is index 0 in VERB_TOKENS
        assert factorized['verbs'][1]  # NOMINATE is index 1 in VERB_TOKENS
    
    def test_legal_action_sequence_validation(self):
        """Test validation of legal action sequences."""
        self.game_state.current_phase = DayPhase()
        self.game_state.turn = 1
        
        # Valid nomination action
        nomination_tokens = [TokenID.NOMINATE, TokenID.PLAYER_1]
        assert self.masker.is_legal_action_sequence(self.game_state, 0, nomination_tokens)
        
        # Valid END_TURN action
        end_turn_tokens = [TokenID.END_TURN]
        assert self.masker.is_legal_action_sequence(self.game_state, 0, end_turn_tokens)
        
        # Invalid: trying to nominate self
        self_nomination_tokens = [TokenID.NOMINATE, TokenID.PLAYER_0]
        assert not self.masker.is_legal_action_sequence(self.game_state, 0, self_nomination_tokens)
        
        # Invalid: trying to kill during day phase
        kill_tokens = [TokenID.KILL, TokenID.PLAYER_1]
        assert not self.masker.is_legal_action_sequence(self.game_state, 0, kill_tokens)
    
    def test_convenience_functions(self):
        """Test convenience functions work correctly."""
        self.game_state.current_phase = DayPhase()
        self.game_state.turn = 1
        
        # Test generate_legal_mask function
        mask1 = generate_legal_mask(self.game_state, 0)
        mask2 = self.masker.generate_legal_mask(self.game_state, 0)
        assert np.array_equal(mask1, mask2)
        
        # Test generate_factorized_masks function
        factorized1 = generate_factorized_masks(self.game_state, 0)
        factorized2 = self.masker.generate_factorized_masks(self.game_state, 0)
        assert np.array_equal(factorized1['verbs'], factorized2['verbs'])
        assert np.array_equal(factorized1['players'], factorized2['players'])
        assert np.array_equal(factorized1['colors'], factorized2['colors'])
        
        # Test is_legal_action_sequence function
        tokens = [TokenID.NOMINATE, TokenID.PLAYER_1]
        result1 = is_legal_action_sequence(self.game_state, 0, tokens)
        result2 = self.masker.is_legal_action_sequence(self.game_state, 0, tokens)
        assert result1 == result2
    
    def test_mask_never_all_zero(self):
        """Test that masks are never all-zero."""
        # Test non-voting phases
        phases = [DayPhase(), NightKillPhase(), NightSheriffPhase()]
        
        for phase in phases:
            self.game_state.current_phase = phase
            for player_index in range(10):
                if self.game_state.game_states[player_index].alive:
                    mask = self.masker.generate_legal_mask(self.game_state, player_index)
                    assert np.any(mask), f"Mask should never be all-zero for {phase} player {player_index}"
        
        # Test VotingPhase with proper setup (nominated players)
        self.game_state.current_phase = VotingPhase()
        self.game_state.nominated_players = [1, 2]  # Ensure there are nominated players
        self.game_state.voting_round = 0
        for player_index in range(10):
            if self.game_state.game_states[player_index].alive:
                mask = self.masker.generate_legal_mask(self.game_state, player_index)
                assert np.any(mask), f"Mask should never be all-zero for VotingPhase player {player_index}"
    
    def test_dead_player_masks(self):
        """Test masks for dead players."""
        # Kill a player
        self.game_state.game_states[5].alive = 0
        
        # Dead players should still get a valid mask (with at least END_TURN)
        mask = self.masker.generate_legal_mask(self.game_state, 5)
        assert mask[TokenID.END_TURN]
        assert np.any(mask)
    
    def test_voting_round_specific_actions(self):
        """Test actions specific to different voting rounds."""
        self.game_state.current_phase = VotingPhase()
        
        # First voting round - vote for nominated players
        self.game_state.nominated_players = [1, 2]
        self.game_state.voting_round = 0
        mask = self.masker.generate_legal_mask(self.game_state, 0)
        assert mask[TokenID.VOTE]
        assert not mask[TokenID.VOTE_ELIMINATE_ALL]
        
        # Third voting round - eliminate all vote
        self.game_state.tied_players = [1, 2]
        self.game_state.voting_round = 2
        mask = self.masker.generate_legal_mask(self.game_state, 0)
        assert mask[TokenID.VOTE_ELIMINATE_ALL]
        assert not mask[TokenID.VOTE]
    
    def test_actions_equal_method(self):
        """Test the _actions_equal method."""
        # Same actions should be equal
        action1 = NominationAction(0, 1)
        action2 = NominationAction(0, 1)
        assert self.masker._actions_equal(action1, action2)
        
        # Different target players
        action3 = NominationAction(0, 2)
        assert not self.masker._actions_equal(action1, action3)
        
        # Different action types
        action4 = VoteAction(0, 1)
        assert not self.masker._actions_equal(action1, action4)
        
        # Different player indices
        action5 = NominationAction(1, 1)
        assert not self.masker._actions_equal(action1, action5)
    
    def test_integration_with_token_encoder(self):
        """Test integration with token encoder."""
        self.game_state.current_phase = DayPhase()
        self.game_state.turn = 1
        
        # Get available actions from game state
        original_active = self.game_state.active_player
        self.game_state.active_player = 0
        available_actions = self.game_state.get_available_actions()
        self.game_state.active_player = original_active
        
        # Check that all available actions have legal tokens
        mask = self.masker.generate_legal_mask(self.game_state, 0)
        
        for action in available_actions:
            tokens = encode_action(action)
            if tokens:
                # Verb token should be legal
                verb_token = tokens[0]
                assert mask[verb_token], f"Verb token {verb_token} should be legal for action {action}"
                
                # Target tokens should be legal if they exist
                for target_token in tokens[1:]:
                    assert mask[target_token], f"Target token {target_token} should be legal for action {action}"
