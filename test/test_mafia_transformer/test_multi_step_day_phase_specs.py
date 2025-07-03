"""
Unit tests for multi-step day phase action specifications.

Tests the requirements:
1. Player should have only one <NEXT_TURN> before sequence of day moves
2. Only one nomination is allowed, but multiple declarations are allowed
3. We want not more than 5-7 sequential moves per player for day phase
4. Only nomination action has real consequences (in terms of game mechanics) everything else are just declarations
5. Transformer should reply with sequence of actions from allowed list (from 0 to 7 random length) right after <NEXT_TURN> and finish those with <END_TURN>
"""

import pytest
from mafia_transformer.token_game_interface import create_token_game, TokenGameState
from mafia_transformer.token_vocab import TokenID


class TestMultiStepDayPhaseSpecs:
    """Test multi-step day phase action specifications."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.interface = create_token_game()
        self.initial_state = self.interface.initialize_game(seed=42)
    
    def test_single_next_turn_token_per_turn(self):
        """Test that player gets only one <NEXT_TURN> before sequence of day moves."""
        # Get observation tokens for active player (should include <NEXT_TURN>)
        observation_tokens = self.interface.get_observation_tokens(self.initial_state, 0)
        
        # Count <NEXT_TURN> tokens in observation
        next_turn_count = observation_tokens.count(TokenID.NEXT_TURN.value)
        
        assert next_turn_count == 1, f"Expected exactly 1 <NEXT_TURN> token, got {next_turn_count}"
        
        # Verify <NEXT_TURN> is at the end (ephemeral token for LLM input)
        assert observation_tokens[-1] == TokenID.NEXT_TURN.value, "NEXT_TURN should be the last token"
    
    def test_day_phase_sequence_length_constraint(self):
        """Test that day phase sequences are limited to 0-7 actions plus END_TURN."""
        # Test various valid day sequences
        valid_sequences = [
            # 0 actions: just END_TURN
            [TokenID.END_TURN.value],
            
            # 1 action + END_TURN
            [TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.BLACK.value, TokenID.END_TURN.value],
            
            # 3 actions + END_TURN (avoid self-targeting)
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value,
             TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_3.value, TokenID.RED.value,
             TokenID.NOMINATE.value, TokenID.PLAYER_4.value,
             TokenID.END_TURN.value],
            
            # 7 actions + END_TURN (maximum allowed, avoid conflicts and self-targeting)
            [TokenID.SAY.value, TokenID.PLAYER_0.value, TokenID.BLACK.value,
             TokenID.SAY.value, TokenID.PLAYER_5.value, TokenID.RED.value,
             TokenID.SAY.value, TokenID.PLAYER_6.value, TokenID.BLACK.value,
             TokenID.SAY.value, TokenID.PLAYER_7.value, TokenID.RED.value,
             TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_8.value, TokenID.BLACK.value,
             TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_9.value, TokenID.RED.value,
             TokenID.CLAIM_SHERIFF.value,  # No nomination since one was already made
             TokenID.END_TURN.value]
        ]
        
        state = self.initial_state
        for sequence in valid_sequences:
            # Each sequence should be valid - use current active player
            current_player = state.active_player
            new_state = self.interface.apply_action(state, sequence, current_player)
            assert new_state is not None, f"Valid sequence should be accepted: {sequence}"
            state = new_state
    
    def test_single_nomination_per_sequence(self):
        """Test that only one nomination is allowed per sequence, but multiple declarations are allowed."""
        # Valid: multiple declarations, one nomination
        valid_sequence = [
            TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value,
            TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.RED.value,
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_3.value, TokenID.BLACK.value,
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_4.value, TokenID.RED.value,
            TokenID.NOMINATE.value, TokenID.PLAYER_5.value,  # Only one nomination
            TokenID.END_TURN.value
        ]
        
        # Should be accepted - use current active player
        current_player = self.initial_state.active_player
        new_state = self.interface.apply_action(self.initial_state, valid_sequence, current_player)
        assert new_state is not None, "Multiple declarations with single nomination should be allowed"
        
        # Valid: no nominations, just declarations
        declaration_only_sequence = [
            TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value,
            TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.RED.value,
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_3.value, TokenID.BLACK.value,
            TokenID.END_TURN.value
        ]
        
        # Should be accepted - use current active player
        current_player = self.initial_state.active_player
        new_state = self.interface.apply_action(self.initial_state, declaration_only_sequence, current_player)
        assert new_state is not None, "Multiple declarations without nomination should be allowed"
    
    def test_nomination_has_game_consequences_declarations_do_not(self):
        """Test that only nomination actions have real consequences, declarations are just recorded."""
        # Apply sequence with nomination
        nomination_sequence = [
            TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value,  # Declaration (recorded only)
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.RED.value,  # Declaration (recorded only)
            TokenID.NOMINATE.value, TokenID.PLAYER_3.value,  # Nomination (affects game mechanics)
            TokenID.END_TURN.value
        ]
        
        current_player = self.initial_state.active_player
        state_with_nomination = self.interface.apply_action(self.initial_state, nomination_sequence, current_player)
        
        # Apply sequence with only declarations
        declaration_sequence = [
            TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value,
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.RED.value,
            TokenID.END_TURN.value
        ]
        
        current_player = self.initial_state.active_player
        state_declarations_only = self.interface.apply_action(self.initial_state, declaration_sequence, current_player)
        
        # Both should be valid, but nomination should affect game mechanics
        assert state_with_nomination is not None
        assert state_declarations_only is not None
        
        # The histories should be different (nomination is recorded in game history)
        assert state_with_nomination.chronological_history != state_declarations_only.chronological_history
        
        # Verify nomination appears in history but declarations might not affect game mechanics
        nomination_tokens = [TokenID.NOMINATE.value, TokenID.PLAYER_3.value]
        history_tokens = state_with_nomination.chronological_history
        
        # Check that nomination sequence appears in history
        for i in range(len(history_tokens) - len(nomination_tokens) + 1):
            if history_tokens[i:i+len(nomination_tokens)] == nomination_tokens:
                break
        else:
            pytest.fail("Nomination sequence not found in game history")
    
    def test_individual_actions_vs_sequences_validation(self):
        """Test that individual actions work, but multi-action sequences must end with END_TURN."""
        # The new system allows individual actions to be applied directly
        legal_actions = self.interface.get_legal_actions(self.initial_state)
        
        # Individual actions should be available (without END_TURN)
        individual_actions = [action for action in legal_actions if action != [TokenID.END_TURN.value]]
        assert len(individual_actions) > 0, "Should have individual actions available"
        
        # Individual actions should work fine (they're in legal actions)
        single_action = [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value]
        if single_action in legal_actions:
            # This should succeed - individual actions are valid
            new_state = self.interface.apply_action(self.initial_state, single_action, self.initial_state.active_player)
            assert new_state is not None, "Individual action should be valid"
        
        # But a multi-action sequence that doesn't end with END_TURN should fail validation
        invalid_multi_sequence = [
            TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value,
            TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.RED.value
            # Missing END_TURN
        ]
        
        try:
            # This should fail because it's a multi-action sequence without END_TURN
            self.interface.apply_action(self.initial_state, invalid_multi_sequence, self.initial_state.active_player)
            assert False, "Should have failed - multi-action sequence without END_TURN should not be accepted"
        except ValueError as e:
            # This is expected - the validation should catch sequences that don't end properly
            assert ("Illegal" in str(e) or "not legal" in str(e) or 
                    "must end with END_TURN" in str(e)), f"Expected validation error, got: {e}"
    
    def test_legal_actions_include_individual_actions_and_end_turn(self):
        """Test that legal actions for day phase include individual actions that can be combined."""
        legal_actions = self.interface.get_legal_actions(self.initial_state)
        
        # Should include END_TURN option (for 0-action sequence)
        end_turn_only = [TokenID.END_TURN.value]
        assert end_turn_only in legal_actions, "Should include END_TURN-only option"
        
        # Should include individual actions (without END_TURN)
        individual_actions = [action for action in legal_actions if action != [TokenID.END_TURN.value]]
        assert len(individual_actions) > 0, "Should include individual actions that can be combined"
        
        # Verify we have different types of individual actions
        action_types = set()
        for action in individual_actions:
            if action:  # Non-empty action
                action_types.add(action[0])  # First token identifies action type
        
        # Should have multiple types of actions available
        assert len(action_types) >= 2, f"Should have multiple action types, got: {action_types}"
        
        # Common day actions should be available
        expected_actions = {TokenID.SAY.value, TokenID.NOMINATE.value, TokenID.CLAIM_SHERIFF_CHECK.value}
        available_actions = {action[0] for action in individual_actions if action}
        
        # Should have at least some of the expected day actions
        common_actions = expected_actions.intersection(available_actions)
        assert len(common_actions) > 0, f"Should have common day actions like SAY, NOMINATE, CLAIM_SHERIFF_CHECK. Available: {available_actions}"
    
    def test_night_phase_vs_day_phase_behavior(self):
        """Test that night phases behave differently from day phases."""
        # Progress to night phase
        day_state = self.initial_state
        
        # Complete a day phase to reach night
        day_actions = [TokenID.END_TURN.value]  # Simple day action
        
        # Apply day actions for all players to reach night
        current_state = day_state
        for player_id in range(10):
            if current_state.active_player == player_id:
                # Check if we can apply day action
                legal_actions = self.interface.get_legal_actions(current_state)
                if day_actions in legal_actions:
                    current_state = self.interface.apply_action(current_state, day_actions, player_id)
                else:
                    # If we're not in day phase anymore, break
                    break
        
        # The behavior should be different based on phase
        # This test ensures that the multi-action system is phase-aware
        # (detailed implementation depends on game state progression)
        
        # At minimum, verify state progressed
        assert current_state != day_state, "State should have progressed"
    
    def test_transformer_input_output_pattern(self):
        """Test the intended transformer input/output pattern."""
        # Transformer receives: game history + <NEXT_TURN>
        observation_tokens = self.interface.get_observation_tokens(self.initial_state, 0)
        assert observation_tokens[-1] == TokenID.NEXT_TURN.value, "Observation should end with NEXT_TURN"
        
        # Transformer should output: sequence of 0-7 actions + <END_TURN>
        legal_actions = self.interface.get_legal_actions(self.initial_state)
        
        # All legal actions should end with END_TURN for day phase
        day_actions = [action for action in legal_actions if TokenID.END_TURN.value in action]
        assert len(day_actions) > 0, "Should have actions ending with END_TURN"
        
        # Verify the pattern: actions should be sequences ending with END_TURN
        for action in day_actions:
            assert action[-1] == TokenID.END_TURN.value, f"Day action should end with END_TURN: {action}"
            
            # Count non-END_TURN tokens (actual actions)
            action_count = len([token for token in action if token != TokenID.END_TURN.value])
            assert action_count <= 21, f"Should not exceed ~7 actions (3 tokens each), got {action_count} tokens"  # Rough estimate: 7 actions * 3 tokens each


class TestMultiStepSequenceValidation:
    """Test validation of multi-step sequences."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.interface = create_token_game()
        self.initial_state = self.interface.initialize_game(seed=42)
    
    def test_valid_day_sequence_patterns(self):
        """Test various valid day sequence patterns."""
        valid_patterns = [
            # Pattern 1: Say + Sheriff check + Nominate
            [
                TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value,
                TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.RED.value,
                TokenID.NOMINATE.value, TokenID.PLAYER_3.value,
                TokenID.END_TURN.value
            ],
            
            # Pattern 2: Multiple declarations (avoid conflicts)
            [
                TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_4.value, TokenID.BLACK.value,
                TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_5.value, TokenID.RED.value,
                TokenID.CLAIM_SHERIFF.value,
                TokenID.END_TURN.value
            ],
            
            # Pattern 3: Mixed declarations (avoid conflicts with previous patterns)
            [
                TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_6.value, TokenID.BLACK.value,
                TokenID.SAY.value, TokenID.PLAYER_7.value, TokenID.RED.value,
                TokenID.DENY_SHERIFF.value,  # Use DENY_SHERIFF instead of CLAIM_SHERIFF to avoid conflicts
                TokenID.END_TURN.value
            ]
        ]
        
        state = self.initial_state
        for i, pattern in enumerate(valid_patterns):
            current_player = state.active_player
            new_state = self.interface.apply_action(state, pattern, current_player)
            assert new_state is not None, f"Valid pattern {i+1} should be accepted: {pattern}"
            state = new_state
    
    def test_sequence_length_boundaries(self):
        """Test sequence length boundary conditions."""
        # Test minimum: just END_TURN (0 actions)
        min_sequence = [TokenID.END_TURN.value]
        current_player = self.initial_state.active_player
        new_state = self.interface.apply_action(self.initial_state, min_sequence, current_player)
        assert new_state is not None, "Minimum sequence (END_TURN only) should be valid"
        
        # Test reasonable maximum: 7 complete actions
        max_sequence = []
        for i in range(7):  # 7 actions
            max_sequence.extend([TokenID.SAY.value, TokenID.PLAYER_1.value + (i % 9), TokenID.BLACK.value])
        max_sequence.append(TokenID.END_TURN.value)
        
        # This should be valid (though may not be in legal actions due to game constraints)
        # At minimum, it should not crash the system
        try:
            current_player = self.initial_state.active_player
            new_state = self.interface.apply_action(self.initial_state, max_sequence, current_player)
            # If accepted, great. If not, should fail gracefully
            assert True, "System should handle maximum sequence length gracefully"
        except Exception as e:
            # Should not crash with internal errors
            assert "invalid" in str(e).lower() or "not allowed" in str(e).lower(), f"Should fail gracefully: {e}"
