"""
Integration tests for the complete token system with the existing game engine.
Tests the full pipeline: GameState -> Actions -> Tokens -> Legal Masks -> Actions -> GameState
"""
import pytest
import numpy as np
from typing import List

from mafia_game.game_state import CompleteGameState, DayPhase, VotingPhase, NightKillPhase, NightSheriffPhase, NightDonPhase, EndPhase
from mafia_game.actions import (
    Action, NullAction, NominationAction, VoteAction, KillAction, 
    SheriffCheckAction, DonCheckAction, SheriffDeclarationAction,
    PublicSheriffDeclarationAction, EliminateAllNominatedVoteAction
)
from mafia_game.common import Role, Team
from mafia_transformer.token_vocab import TokenID, VOCAB_SIZE
from mafia_transformer.token_encoder import TokenEncoder, encode_action, decode_action
from mafia_transformer.legal_mask import LegalActionMasker, generate_legal_mask


class TestTokenSystemIntegration:
    """Integration tests for the complete token system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.game_state = CompleteGameState.build(use_test_agents=True)
        self.encoder = TokenEncoder()
        self.masker = LegalActionMasker()
    
    def test_complete_action_pipeline(self):
        """Test the complete pipeline from game state to actions and back."""
        # Set up a specific game scenario
        self.game_state.current_phase = DayPhase()
        self.game_state.turn = 1
        player_index = 0
        
        # 1. Get available actions from game engine
        original_active = self.game_state.active_player
        self.game_state.active_player = player_index
        available_actions = self.game_state.get_available_actions()
        self.game_state.active_player = original_active
        
        # 2. Encode actions to tokens
        encoded_actions = []
        for action in available_actions:
            tokens = self.encoder.encode_action(action)
            encoded_actions.append((action, tokens))
        
        # 3. Generate legal mask
        legal_mask = self.masker.generate_legal_mask(self.game_state, player_index)
        
        # 4. Validate that all encoded actions have legal tokens
        for original_action, tokens in encoded_actions:
            assert len(tokens) > 0, f"Action {original_action} should encode to at least one token"
            
            # Check that all tokens in the action are legal
            for token in tokens:
                assert legal_mask[token], f"Token {token} should be legal for action {original_action}"
        
        # 5. Decode tokens back to actions and verify round-trip
        for original_action, tokens in encoded_actions:
            decoded_action = self.encoder.decode_action(tokens, player_index)
            
            # Verify the decoded action matches the original
            assert type(decoded_action) == type(original_action)
            assert decoded_action.player_index == original_action.player_index
            
            # Check action-specific attributes
            if hasattr(original_action, 'target_player'):
                assert decoded_action.target_player == original_action.target_player
            if hasattr(original_action, 'i_am_sheriff'):
                assert decoded_action.i_am_sheriff == original_action.i_am_sheriff
            if hasattr(original_action, 'eliminate_all'):
                assert decoded_action.eliminate_all == original_action.eliminate_all
    
    def test_phase_specific_integration(self):
        """Test integration across different game phases."""
        phases_and_expected_actions = [
            (DayPhase(), [NominationAction, NullAction]),
            (VotingPhase(), [VoteAction, EliminateAllNominatedVoteAction, NullAction]),
            (NightKillPhase(), [KillAction, NullAction]),
            (NightSheriffPhase(), [SheriffCheckAction, NullAction]),
            (NightDonPhase(), [DonCheckAction, NullAction]),
        ]
        
        for phase, expected_action_types in phases_and_expected_actions:
            self.game_state.current_phase = phase
            
            if isinstance(phase, VotingPhase):
                # Set up voting scenario
                self.game_state.nominated_players = [1, 2]
                self.game_state.voting_round = 0
            
            # Test for different players based on their roles
            for player_index in range(10):
                if not self.game_state.game_states[player_index].alive:
                    continue
                
                player_role = self.game_state.game_states[player_index].private_data.role
                
                # Skip irrelevant combinations
                if isinstance(phase, NightKillPhase):
                    killer_index = self.game_state.index_of_night_killer()
                    if player_index != killer_index:
                        continue
                elif isinstance(phase, NightSheriffPhase) and player_role != Role.SHERIFF:
                    continue
                elif isinstance(phase, NightDonPhase) and player_role != Role.DON:
                    continue
                
                # Get available actions
                original_active = self.game_state.active_player
                self.game_state.active_player = player_index
                available_actions = self.game_state.get_available_actions()
                self.game_state.active_player = original_active
                
                # Verify expected action types are available
                available_types = [type(action) for action in available_actions]
                
                # NullAction availability depends on phase - not available during voting
                if not isinstance(phase, VotingPhase):
                    assert NullAction in available_types, f"NullAction should be available in {phase} for player {player_index}"
                else:
                    # During voting, players must vote - cannot abstain
                    assert NullAction not in available_types, f"NullAction should NOT be available during VotingPhase for player {player_index}"
                    # Must have vote actions available
                    vote_types = [VoteAction, EliminateAllNominatedVoteAction]
                    has_vote_action = any(vtype in available_types for vtype in vote_types)
                    assert has_vote_action, f"Must have vote actions available during VotingPhase for player {player_index}"
                
                # Test token encoding/decoding for all available actions
                for action in available_actions:
                    tokens = encode_action(action)
                    assert len(tokens) > 0, f"Action {action} should encode to tokens"
                    
                    decoded = decode_action(tokens, player_index)
                    assert type(decoded) == type(action), f"Round-trip failed for {action}"
                
                # Test legal mask generation
                mask = generate_legal_mask(self.game_state, player_index)
                assert np.any(mask), f"Mask should not be all-zero for {phase} player {player_index}"
                
                # END_TURN is only legal outside of voting phase (players cannot abstain from voting)
                if not isinstance(phase, VotingPhase):
                    assert mask[TokenID.END_TURN], "END_TURN should be legal outside of voting phase"
                else:
                    assert not mask[TokenID.END_TURN], "END_TURN should NOT be legal during voting phase"
    
    def test_game_simulation_with_tokens(self):
        """Test running a short game simulation using only token-based actions."""
        # Run a few turns of the game using token-based action selection
        max_actions = 20
        action_count = 0
        
        while not self.game_state.is_terminal() and action_count < max_actions:
            current_player = self.game_state.active_player
            
            # Get available actions through the game engine
            available_actions = self.game_state.get_available_actions()
            
            # Some players may have no available actions (e.g., dead players, wrong role for phase)
            if len(available_actions) == 0:
                # Skip this player by executing a phase transition or moving to next player
                # This can happen when a dead player is active or player has no role-specific actions
                self.game_state.transition_to_next_phase()
                continue
            
            # Convert to tokens and back
            token_actions = []
            for action in available_actions:
                tokens = encode_action(action)
                decoded_action = decode_action(tokens, current_player)
                token_actions.append(decoded_action)
            
            # Verify we can reconstruct the same actions
            assert len(token_actions) == len(available_actions)
            
            # Generate legal mask and verify it covers all available actions
            mask = generate_legal_mask(self.game_state, current_player)
            for action in available_actions:
                tokens = encode_action(action)
                for token in tokens:
                    assert mask[token], f"Token {token} should be legal for available action {action}"
            
            # Choose a simple action (prefer NullAction for simplicity, but not during voting)
            chosen_action = None
            from mafia_game.game_state import VotingPhase
            
            # During voting phase, players cannot use NullAction - they must vote
            if not isinstance(self.game_state.current_phase, VotingPhase):
                for action in available_actions:
                    if isinstance(action, NullAction):
                        chosen_action = action
                        break
            
            if chosen_action is None:
                chosen_action = available_actions[0]  # Fallback to first action
            
            # Execute the action
            try:
                self.game_state.execute_action(chosen_action)
                action_count += 1
            except Exception as e:
                pytest.fail(f"Failed to execute action {chosen_action}: {e}")
    
    def test_voting_scenario_integration(self):
        """Test complete voting scenario with token system."""
        # Set up a voting scenario
        self.game_state.current_phase = DayPhase()
        self.game_state.turn = 1
        
        # First, have players nominate someone
        self.game_state.active_player = 0
        nomination = NominationAction(0, 1)
        
        # Verify nomination can be encoded/decoded
        tokens = encode_action(nomination)
        decoded = decode_action(tokens, 0)
        assert isinstance(decoded, NominationAction)
        assert decoded.target_player == 1
        
        # Execute nomination
        self.game_state.execute_action(nomination)
        
        # Skip other players (use NullAction)
        while isinstance(self.game_state.current_phase, DayPhase):
            null_action = NullAction(self.game_state.active_player)
            self.game_state.execute_action(null_action)
        
        # Should now be in voting phase
        assert isinstance(self.game_state.current_phase, VotingPhase)
        assert 1 in self.game_state.nominated_players
        
        # Test voting actions with tokens
        current_player = self.game_state.active_player
        available_actions = self.game_state.get_available_actions()
        
        # Should have vote actions for nominated players
        vote_actions = [a for a in available_actions if isinstance(a, VoteAction)]
        assert len(vote_actions) > 0, "Should have vote actions available"
        
        # Test token encoding for vote actions
        for vote_action in vote_actions:
            tokens = encode_action(vote_action)
            assert tokens[0] == TokenID.VOTE, "First token should be VOTE"
            assert tokens[1] == TokenID.PLAYER_0 + vote_action.target_player, "Second token should be target player"
            
            decoded = decode_action(tokens, current_player)
            assert decoded.target_player == vote_action.target_player
    
    def test_night_phase_integration(self):
        """Test night phase actions with token system."""
        # Set up night kill phase
        self.game_state.current_phase = NightKillPhase()
        
        # Find the killer
        killer_index = self.game_state.index_of_night_killer()
        assert killer_index >= 0, "Should have a valid killer"
        
        # Test kill action encoding
        available_actions = []
        original_active = self.game_state.active_player
        self.game_state.active_player = killer_index
        available_actions = self.game_state.get_available_actions()
        self.game_state.active_player = original_active
        
        kill_actions = [a for a in available_actions if isinstance(a, KillAction)]
        
        if kill_actions:  # If kill actions are available
            kill_action = kill_actions[0]
            tokens = encode_action(kill_action)
            assert tokens[0] == TokenID.KILL, "First token should be KILL"
            
            decoded = decode_action(tokens, killer_index)
            assert isinstance(decoded, KillAction)
            assert decoded.target_player == kill_action.target_player
        
        # Test sheriff check phase
        self.game_state.current_phase = NightSheriffPhase()
        
        # Find sheriff
        sheriff_player = None
        for i, state in enumerate(self.game_state.game_states):
            if state.private_data.role == Role.SHERIFF and state.alive:
                sheriff_player = i
                break
        
        if sheriff_player is not None:
            original_active = self.game_state.active_player
            self.game_state.active_player = sheriff_player
            available_actions = self.game_state.get_available_actions()
            self.game_state.active_player = original_active
            
            sheriff_actions = [a for a in available_actions if isinstance(a, SheriffCheckAction)]
            
            if sheriff_actions:
                sheriff_action = sheriff_actions[0]
                tokens = encode_action(sheriff_action)
                assert tokens[0] == TokenID.SHERIFF_CHECK, "First token should be SHERIFF_CHECK"
                
                decoded = decode_action(tokens, sheriff_player)
                assert isinstance(decoded, SheriffCheckAction)
                assert decoded.target_player == sheriff_action.target_player
    
    def test_error_handling_integration(self):
        """Test error handling in the integrated token system."""
        # Test invalid token sequences
        invalid_sequences = [
            [],  # Empty sequence
            [999],  # Invalid token ID
            [TokenID.KILL, TokenID.KILL],  # Invalid combination
            [TokenID.NOMINATE],  # Missing required target
            [TokenID.NOMINATE, TokenID.PLAYER_0, TokenID.PLAYER_1],  # Too many arguments
        ]
        
        for invalid_tokens in invalid_sequences:
            try:
                if invalid_tokens:  # Skip empty for this test
                    action = decode_action(invalid_tokens, 0)
                    # If decode succeeds, check if it's legal
                    is_legal = self.masker.is_legal_action_sequence(self.game_state, 0, invalid_tokens)
                    # Some invalid sequences might decode but be illegal
            except (ValueError, IndexError):
                # Expected for truly invalid sequences
                pass
    
    def test_performance_characteristics(self):
        """Test performance of token system operations."""
        import time
        
        # Test encoding performance
        actions = [
            NominationAction(0, 1),
            VoteAction(0, 1),
            KillAction(0, 1),
            SheriffCheckAction(0, 1),
            NullAction(0),
        ]
        
        # Time encoding operations
        start_time = time.time()
        for _ in range(1000):
            for action in actions:
                tokens = encode_action(action)
                decoded = decode_action(tokens, 0)
        encoding_time = time.time() - start_time
        
        # Should be reasonably fast (less than 1 second for 5000 operations)
        assert encoding_time < 1.0, f"Token encoding/decoding too slow: {encoding_time:.3f}s"
        
        # Test mask generation performance
        start_time = time.time()
        for _ in range(100):
            mask = generate_legal_mask(self.game_state, 0)
        mask_time = time.time() - start_time
        
        # Should be reasonably fast (less than 1 second for 100 operations)
        assert mask_time < 1.0, f"Legal mask generation too slow: {mask_time:.3f}s"
    
    def test_all_action_types_coverage(self):
        """Test that all action types in the game can be handled by the token system."""
        action_types = [
            NullAction,
            NominationAction,
            VoteAction,
            KillAction,
            SheriffCheckAction,
            DonCheckAction,
            SheriffDeclarationAction,
            PublicSheriffDeclarationAction,
            EliminateAllNominatedVoteAction,
        ]
        
        for action_type in action_types:
            # Create a sample action of this type
            if action_type == NullAction:
                action = action_type(0)
            elif action_type in [NominationAction, VoteAction, KillAction, SheriffCheckAction, DonCheckAction]:
                action = action_type(0, 1)
            elif action_type == SheriffDeclarationAction:
                action = action_type(0, True)
            elif action_type == PublicSheriffDeclarationAction:
                action = action_type(0, 1, Team.RED_TEAM)
            elif action_type == EliminateAllNominatedVoteAction:
                action = action_type(0, True)
            
            # Test encoding/decoding
            try:
                tokens = encode_action(action)
                assert len(tokens) > 0, f"Action {action_type} should encode to at least one token"
                
                decoded = decode_action(tokens, 0)
                assert type(decoded) == action_type, f"Round-trip failed for {action_type}"
                
            except Exception as e:
                pytest.fail(f"Failed to handle action type {action_type}: {e}")
    
    def test_game_state_consistency(self):
        """Test that token operations don't break game state consistency."""
        # Save initial state
        initial_state = self.game_state.serialize()
        
        # Perform various token operations
        for player_index in range(10):
            if self.game_state.game_states[player_index].alive:
                # Generate mask (should not modify state)
                mask = generate_legal_mask(self.game_state, player_index)
                
                # Get available actions (should not modify state)
                original_active = self.game_state.active_player
                self.game_state.active_player = player_index
                actions = self.game_state.get_available_actions()
                self.game_state.active_player = original_active
                
                # Encode/decode actions (should not modify state)
                for action in actions:
                    tokens = encode_action(action)
                    decoded = decode_action(tokens, player_index)
        
        # Verify state is unchanged
        final_state = self.game_state.serialize()
        assert np.array_equal(initial_state, final_state), "Token operations should not modify game state"
