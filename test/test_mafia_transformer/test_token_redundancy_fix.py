"""
Test suite for the token redundancy fix.

Tests that the history recording no longer contains redundant player tokens
and that the cleaner format is used:
- Old format: <PLAYER_1> <PLAYER_1> <CLAIM_SHERIFF_CHECK> <PLAYER_8> <RED> <PLAYER_1> <CLAIM_SHERIFF_CHECK> <PLAYER_2> <BLACK> <PLAYER_1> <END_TURN>
- New format: <PLAYER_1> <CLAIM_SHERIFF_CHECK> <PLAYER_8> <RED> <CLAIM_SHERIFF_CHECK> <PLAYER_2> <BLACK> <END_TURN>
"""

import pytest
from mafia_transformer.token_game_interface import TokenGameInterface, create_token_game
from mafia_transformer.token_vocab import TokenID, TOKEN_ID_TO_NAME


class TestTokenRedundancyFix:
    """Test the removal of redundant player tokens from history recording."""
    
    def setup_method(self):
        """Set up a fresh game interface for each test."""
        self.game_interface = create_token_game()
        self.initial_state = self.game_interface.initialize_game(seed=42)
    
    def test_single_day_action_format(self):
        """Test that single day actions don't have redundant player tokens."""
        # Apply a single day action
        action_tokens = [TokenID.SAY.value, TokenID.PLAYER_3.value, TokenID.RED.value, TokenID.END_TURN.value]
        
        new_state = self.game_interface.apply_action(
            self.initial_state, 
            action_tokens, 
            self.initial_state.active_player
        )
        
        # Check that the sequence doesn't have redundant player tokens
        player_sequence = new_state.player_chronological_sequences[0]
        
        # Find the action in the sequence
        action_start_idx = None
        for i in range(len(player_sequence) - 3):
            if (player_sequence[i] == TokenID.PLAYER_0.value and
                player_sequence[i + 1] == TokenID.SAY.value and
                player_sequence[i + 2] == TokenID.PLAYER_3.value and
                player_sequence[i + 3] == TokenID.RED.value):
                action_start_idx = i
                break
        
        assert action_start_idx is not None, "Could not find the action in player sequence"
        
        # Verify format: <PLAYER_0> <SAY> <PLAYER_3> <RED> <END_TURN>
        expected_sequence = [
            TokenID.PLAYER_0.value,  # Player token once
            TokenID.SAY.value,       # Action
            TokenID.PLAYER_3.value,  # Target
            TokenID.RED.value,       # Color
            TokenID.END_TURN.value   # End turn
        ]
        
        actual_sequence = player_sequence[action_start_idx:action_start_idx + 5]
        assert actual_sequence == expected_sequence, f"Expected {expected_sequence}, got {actual_sequence}"
    
    def test_multi_action_day_sequence_format(self):
        """Test that multi-action sequences don't have redundant player tokens."""
        # Apply a multi-action day sequence
        action_tokens = [
            TokenID.SAY.value, TokenID.PLAYER_3.value, TokenID.RED.value,
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_4.value, TokenID.BLACK.value,
            TokenID.NOMINATE.value, TokenID.PLAYER_5.value,
            TokenID.END_TURN.value
        ]
        
        new_state = self.game_interface.apply_action(
            self.initial_state, 
            action_tokens, 
            self.initial_state.active_player
        )
        
        # Check that the sequence doesn't have redundant player tokens
        player_sequence = new_state.player_chronological_sequences[0]
        
        # Find the action sequence in the player's chronological sequence
        action_start_idx = None
        for i in range(len(player_sequence) - 8):
            if (player_sequence[i] == TokenID.PLAYER_0.value and
                player_sequence[i + 1] == TokenID.SAY.value):
                action_start_idx = i
                break
        
        assert action_start_idx is not None, "Could not find the action sequence in player sequence"
        
        # Verify format: <PLAYER_0> <SAY> <PLAYER_3> <RED> <CLAIM_SHERIFF_CHECK> <PLAYER_4> <BLACK> <NOMINATE> <PLAYER_5> <END_TURN>
        expected_sequence = [
            TokenID.PLAYER_0.value,              # Player token once at start
            TokenID.SAY.value, TokenID.PLAYER_3.value, TokenID.RED.value,  # First action
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_4.value, TokenID.BLACK.value,  # Second action
            TokenID.NOMINATE.value, TokenID.PLAYER_5.value,  # Third action
            TokenID.END_TURN.value               # End turn
        ]
        
        actual_sequence = player_sequence[action_start_idx:action_start_idx + len(expected_sequence)]
        assert actual_sequence == expected_sequence, f"Expected {expected_sequence}, got {actual_sequence}"
    
    def test_no_redundant_player_tokens_in_multi_action(self):
        """Test that multi-action sequences don't contain redundant player tokens between actions."""
        # Apply a multi-action day sequence
        action_tokens = [
            TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value,
            TokenID.CLAIM_SHERIFF.value,
            TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.BLACK.value,
            TokenID.END_TURN.value
        ]
        
        new_state = self.game_interface.apply_action(
            self.initial_state, 
            action_tokens, 
            self.initial_state.active_player
        )
        
        # Check that the sequence format is clean
        player_sequence = new_state.player_chronological_sequences[0]
        
        # Convert to readable format for debugging
        readable_sequence = [TOKEN_ID_TO_NAME.get(token, f"UNK_{token}") for token in player_sequence]
        
        # Count occurrences of PLAYER_0 in the action portion
        # Find the last DAY_1 marker and count PLAYER_0 tokens after it
        last_day_marker_idx = None
        for i in range(len(player_sequence) - 1, -1, -1):
            if player_sequence[i] == TokenID.DAY_1.value:
                last_day_marker_idx = i
                break
        
        assert last_day_marker_idx is not None, "Could not find DAY_1 marker"
        
        # Count PLAYER_0 tokens after the day marker (this should be exactly 1 for the action sequence)
        player_0_count = 0
        for i in range(last_day_marker_idx + 1, len(player_sequence)):
            if player_sequence[i] == TokenID.PLAYER_0.value:
                player_0_count += 1
        
        # There should be exactly 1 PLAYER_0 token (at the start of the action sequence)
        assert player_0_count == 1, f"Expected exactly 1 PLAYER_0 token in action sequence, found {player_0_count}. Sequence: {readable_sequence}"
    
    def test_backward_compatibility_with_single_actions(self):
        """Test that single actions still work correctly with the new format."""
        # Test various single actions
        test_actions = [
            [TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.RED.value, TokenID.END_TURN.value],
            [TokenID.NOMINATE.value, TokenID.PLAYER_3.value, TokenID.END_TURN.value],
            [TokenID.CLAIM_SHERIFF.value, TokenID.END_TURN.value],
            [TokenID.END_TURN.value]  # Just end turn
        ]
        
        current_state = self.initial_state
        
        for action_tokens in test_actions:
            try:
                new_state = self.game_interface.apply_action(
                    current_state, 
                    action_tokens, 
                    current_state.active_player
                )
                
                # Verify that the action was recorded properly
                player_sequence = new_state.player_chronological_sequences[0]
                assert len(player_sequence) > len(current_state.player_chronological_sequences[0])
                
                # Move to next state for next test
                current_state = new_state
                
            except Exception as e:
                pytest.fail(f"Single action {action_tokens} failed: {e}")
    
    def test_parse_action_sequence_handles_redundancy_correctly(self):
        """Test that the action sequence parser works correctly with the new format."""
        # Test the internal parser method
        test_sequence = [
            TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value,
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value,
            TokenID.END_TURN.value
        ]
        
        parsed_actions = self.game_interface._parse_action_sequence(test_sequence)
        
        expected_actions = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value],
            [TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value],
            [TokenID.END_TURN.value]
        ]
        
        assert parsed_actions == expected_actions, f"Expected {expected_actions}, got {parsed_actions}"
    
    def test_get_performed_actions_works_with_new_format(self):
        """Test that tracking of performed actions works with the new cleaner format."""
        # Apply individual actions but don't end the turn yet
        first_action = [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value]
        second_action = [TokenID.CLAIM_SHERIFF.value]
        
        # Apply first action
        state_after_first = self.game_interface.apply_action(
            self.initial_state, 
            first_action, 
            self.initial_state.active_player
        )
        
        # Apply second action  
        state_after_second = self.game_interface.apply_action(
            state_after_first, 
            second_action, 
            state_after_first.active_player
        )
        
        # Get performed actions (while still the same player's turn)
        performed_actions = self.game_interface._get_performed_actions_this_turn(state_after_second)
        
        # Should contain the actions we just performed
        expected_actions = {
            (TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value),
            (TokenID.CLAIM_SHERIFF.value,)
        }
        
        assert performed_actions == expected_actions, f"Expected {expected_actions}, got {performed_actions}"
    
    def test_observation_tokens_are_consistent(self):
        """Test that observation tokens are consistent with the new format."""
        # Apply some actions
        action_tokens = [
            TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.BLACK.value,
            TokenID.NOMINATE.value, TokenID.PLAYER_3.value,
            TokenID.END_TURN.value
        ]
        
        new_state = self.game_interface.apply_action(
            self.initial_state, 
            action_tokens, 
            self.initial_state.active_player
        )
        
        # Get observation tokens for the active player
        observation_tokens = self.game_interface.get_observation_tokens(new_state, new_state.active_player)
        
        # Should not contain redundant player tokens in the action sequences
        readable_tokens = [TOKEN_ID_TO_NAME.get(token, f"UNK_{token}") for token in observation_tokens]
        
        # Count consecutive PLAYER_X tokens (which would indicate redundancy)
        consecutive_player_count = 0
        max_consecutive_players = 0
        
        for i, token in enumerate(observation_tokens):
            if token >= TokenID.PLAYER_0.value and token <= TokenID.PLAYER_9.value:
                consecutive_player_count += 1
                max_consecutive_players = max(max_consecutive_players, consecutive_player_count)
            else:
                consecutive_player_count = 0
        
        # There should be no more than 1 consecutive PLAYER_X token in most cases
        # (except for mafia team declarations which can have multiple player tokens)
        # But definitely no more than 3 (for the initial mafia team setup)
        assert max_consecutive_players <= 3, f"Found {max_consecutive_players} consecutive player tokens, suggesting redundancy. Tokens: {readable_tokens}"
    
    def test_existing_tests_still_pass_with_format_change(self):
        """Test that the format change doesn't break existing functionality."""
        # This is a meta-test to ensure we haven't broken existing functionality
        # Run a simple game flow
        
        current_state = self.initial_state
        
        # Apply a series of actions that should work
        test_sequence = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value, TokenID.END_TURN.value],
            [TokenID.NOMINATE.value, TokenID.PLAYER_2.value, TokenID.END_TURN.value],
            [TokenID.CLAIM_SHERIFF.value, TokenID.END_TURN.value],
        ]
        
        for i, action_tokens in enumerate(test_sequence):
            try:
                new_state = self.game_interface.apply_action(
                    current_state, 
                    action_tokens, 
                    current_state.active_player
                )
                
                # Basic sanity checks
                assert new_state is not None
                assert len(new_state.player_chronological_sequences) == 10
                assert new_state.active_player >= 0
                
                current_state = new_state
                
            except Exception as e:
                pytest.fail(f"Action sequence {i} failed: {action_tokens} -> {e}")
    
    def test_comparison_old_vs_new_format(self):
        """Test that demonstrates the token efficiency improvement."""
        # Apply a multi-action sequence
        action_tokens = [
            TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value,
            TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value,
            TokenID.NOMINATE.value, TokenID.PLAYER_3.value,
            TokenID.END_TURN.value
        ]
        
        new_state = self.game_interface.apply_action(
            self.initial_state, 
            action_tokens, 
            self.initial_state.active_player
        )
        
        # Get the action portion from the sequence
        player_sequence = new_state.player_chronological_sequences[0]
        
        # Find the action sequence
        last_day_idx = None
        for i in range(len(player_sequence) - 1, -1, -1):
            if player_sequence[i] == TokenID.DAY_1.value:
                last_day_idx = i
                break
        
        action_portion = player_sequence[last_day_idx + 1:]
        
        # Count tokens in new format
        new_format_tokens = len(action_portion)
        
        # Calculate what the old format would have been
        # Old format: <PLAYER_0> <PLAYER_0> <SAY> <PLAYER_1> <RED> <PLAYER_0> <CLAIM_SHERIFF_CHECK> <PLAYER_2> <BLACK> <PLAYER_0> <NOMINATE> <PLAYER_3> <PLAYER_0> <END_TURN>
        # That's: 1 + 1 + 3 + 1 + 3 + 1 + 2 + 1 + 1 = 14 tokens
        old_format_tokens = 14
        
        # New format with phase transitions: <DAY_PHASE_START> <YOUR_TURN> <PLAYER_0> <SAY> <PLAYER_1> <RED> <CLAIM_SHERIFF_CHECK> <PLAYER_2> <BLACK> <NOMINATE> <PLAYER_3> <END_TURN> <PLAYER_1>
        # That's: 1 (phase start) + 1 (YOUR_TURN) + 1 + 3 + 3 + 2 + 1 + 1 (next player) = 13 tokens
        # Note: YOUR_TURN is added at initialization for the initial active player
        expected_new_format_tokens = 13
        
        assert new_format_tokens == expected_new_format_tokens, f"Expected {expected_new_format_tokens} tokens in new format, got {new_format_tokens}"
        
        # Calculate savings
        token_savings = old_format_tokens - new_format_tokens
        savings_percentage = (token_savings / old_format_tokens) * 100
        
        print(f"Token efficiency improvement:")
        print(f"  Old format: {old_format_tokens} tokens")
        print(f"  New format: {new_format_tokens} tokens") 
        print(f"  Savings: {token_savings} tokens ({savings_percentage:.1f}%)")
        
        # We should see some savings, though modest due to phase transition tokens
        assert token_savings > 0, f"No token savings achieved"
        assert savings_percentage > 5, f"Expected >5% savings, got {savings_percentage:.1f}%"


if __name__ == "__main__":
    pytest.main([__file__])
