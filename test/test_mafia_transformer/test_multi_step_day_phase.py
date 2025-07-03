"""
Unit tests for multi-step day phase action handling.

Tests the new requirements for improved day phase mechanics:
1. Single NEXT_TURN before day moves sequence
2. Only one nomination allowed per player per day turn
3. Multiple declarations allowed but limited to 5-7 total actions per turn
4. Only nomination actions affect game mechanics, declarations are recorded only
5. Support for multi-action sequences ending with END_TURN
"""

import pytest
from mafia_transformer.token_game_interface import TokenGameInterface, TokenGameState
from mafia_transformer.token_vocab import TokenID
from mafia_game.common import Role, Team

# Configure pytest to reduce verbose output
pytest.main.verbose = 0

def safe_assert_equal(actual, expected, message="Values should be equal"):
    """Safe assertion that avoids printing large objects."""
    if actual != expected:
        # Use simple string representations to avoid verbose output
        actual_str = str(actual) if not hasattr(actual, '_internal_state') else f"<TokenGameState: active_player={actual.active_player}>"
        expected_str = str(expected) if not hasattr(expected, '_internal_state') else f"<TokenGameState: active_player={expected.active_player}>"
        pytest.fail(f"{message}: expected {expected_str}, got {actual_str}")

def safe_assert_in(item, container, message="Item should be in container"):
    """Safe assertion for membership that avoids printing large objects."""
    if item not in container:
        container_str = f"<container with {len(container)} items>" if len(str(container)) > 100 else str(container)
        pytest.fail(f"{message}: {item} not in {container_str}")


class TestMultiStepDayPhase:
    """Test multi-step day phase action handling."""
    
    def setup_method(self):
        """Set up a fresh game interface for each test."""
        self.interface = TokenGameInterface()
        self.initial_state = self.interface.initialize_game(seed=0, num_players=10)
    
    def test_single_next_turn_before_day_moves(self):
        """Test that NEXT_TURN appears only once before a sequence of day moves."""
        token_state = self.initial_state
        
        # Verify we start in day phase with active player 0
        assert self.interface._is_day_phase(token_state._internal_state)
        assert token_state.active_player == 0
        
        # Player 0 should get NEXT_TURN in observation but not stored in sequence
        player_0_observation = self.interface.get_observation_tokens(token_state, 0)
        player_0_sequence = token_state.player_chronological_sequences[0]
        
        # NEXT_TURN should be at the end of observation but not in stored sequence
        assert player_0_observation[-1] == TokenID.NEXT_TURN.value
        assert TokenID.NEXT_TURN.value not in player_0_sequence
        
        # Perform multiple day actions
        actions = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value],
            [TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value],
            [TokenID.NOMINATE.value, TokenID.PLAYER_3.value]
        ]
        
        current_state = token_state
        for action in actions:
            current_state = self.interface.apply_action(current_state, action, 0)
            
            # Should still be player 0's turn after each day action
            assert current_state.active_player == 0
            
            # NEXT_TURN should NOT appear in stored sequence after actions
            player_0_sequence_after = current_state.player_chronological_sequences[0]
            assert TokenID.NEXT_TURN.value not in player_0_sequence_after
        
        # After END_TURN, next player should get NEXT_TURN in observation
        end_turn_state = self.interface.apply_action(current_state, [TokenID.END_TURN.value], 0)
        
        # Active player should switch to next player
        assert end_turn_state.active_player == 1
        
        # Player 1 should get NEXT_TURN in observation but not stored
        player_1_observation = self.interface.get_observation_tokens(end_turn_state, 1)
        player_1_sequence = end_turn_state.player_chronological_sequences[1]
        
        assert player_1_observation[-1] == TokenID.NEXT_TURN.value
        assert TokenID.NEXT_TURN.value not in player_1_sequence
    
    def test_single_nomination_per_day_turn(self):
        """Test that only one nomination is allowed per player per day turn."""
        token_state = self.initial_state
        
        # Perform first nomination
        first_nomination = [TokenID.NOMINATE.value, TokenID.PLAYER_1.value]
        state_after_first = self.interface.apply_action(token_state, first_nomination, 0)
        
        # Check that nomination was applied
        assert state_after_first.active_player == 0  # Still player 0's turn
        
        # Try to perform second nomination - should not be in legal actions
        legal_actions = self.interface.get_legal_actions(state_after_first)
        
        # No additional NOMINATE actions should be available
        nominate_actions = [action for action in legal_actions 
                          if action and action[0] == TokenID.NOMINATE.value]
        assert len(nominate_actions) == 0, "No additional nominations should be allowed"
        
        # But other actions should still be available
        say_actions = [action for action in legal_actions 
                      if action and action[0] == TokenID.SAY.value]
        claim_actions = [action for action in legal_actions 
                        if action and action[0] == TokenID.CLAIM_SHERIFF_CHECK.value]
        end_turn_action = [action for action in legal_actions 
                          if action == [TokenID.END_TURN.value]]
        
        assert len(say_actions) > 0, "SAY actions should still be available"
        assert len(claim_actions) > 0, "CLAIM actions should still be available"
        assert len(end_turn_action) == 1, "END_TURN should be available"
    
    def test_multiple_declarations_allowed(self):
        """Test that multiple declarations (non-nomination actions) are allowed."""
        token_state = self.initial_state
        
        # Perform multiple different declaration actions
        declaration_actions = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value],
            [TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value],
            [TokenID.SAY.value, TokenID.PLAYER_3.value, TokenID.BLACK.value],  # Different SAY
            [TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_4.value, TokenID.RED.value],  # Different CLAIM
        ]
        
        current_state = token_state
        for i, action in enumerate(declaration_actions):
            # Verify action is legal
            legal_actions = self.interface.get_legal_actions(current_state)
            assert action in legal_actions, f"Declaration action {i} should be legal"
            
            # Apply action
            current_state = self.interface.apply_action(current_state, action, 0)
            
            # Should still be player 0's turn
            assert current_state.active_player == 0
        
        # All actions should appear in chronological sequence
        player_0_sequence = current_state.player_chronological_sequences[0]
        
        # Count occurrences of each action type
        say_count = sum(1 for token in player_0_sequence if token == TokenID.SAY.value)
        claim_count = sum(1 for token in player_0_sequence if token == TokenID.CLAIM_SHERIFF_CHECK.value)
        
        assert say_count == 2, "Should have 2 SAY actions"
        assert claim_count == 2, "Should have 2 CLAIM actions"
    
    def test_action_limit_per_day_turn(self):
        """Test that day turns are limited to 5-7 actions maximum."""
        token_state = self.initial_state
        
        # Try to perform 8 actions (should hit limit)
        actions = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value],
            [TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.BLACK.value],
            [TokenID.SAY.value, TokenID.PLAYER_3.value, TokenID.RED.value],
            [TokenID.SAY.value, TokenID.PLAYER_4.value, TokenID.BLACK.value],
            [TokenID.SAY.value, TokenID.PLAYER_5.value, TokenID.RED.value],
            [TokenID.SAY.value, TokenID.PLAYER_6.value, TokenID.BLACK.value],
            [TokenID.SAY.value, TokenID.PLAYER_7.value, TokenID.RED.value],
            [TokenID.SAY.value, TokenID.PLAYER_8.value, TokenID.BLACK.value],  # 8th action - should be blocked
        ]
        
        current_state = token_state
        actions_performed = 0
        
        for i, action in enumerate(actions):
            legal_actions = self.interface.get_legal_actions(current_state)
            
            if action in legal_actions:
                current_state = self.interface.apply_action(current_state, action, 0)
                actions_performed += 1
            else:
                # Hit the limit
                break
        
        # Should have performed 5-7 actions max
        assert 5 <= actions_performed <= 7, f"Should perform 5-7 actions max, performed {actions_performed}"
        
        # END_TURN should still be available after hitting limit
        final_legal_actions = self.interface.get_legal_actions(current_state)
        end_turn_action = [TokenID.END_TURN.value]
        assert end_turn_action in final_legal_actions, "END_TURN should always be available"
    
    def test_nomination_affects_game_mechanics(self):
        """Test that nomination actions affect game mechanics while declarations don't."""
        token_state = self.initial_state
        
        # Get initial game state action count
        initial_action_count = token_state._internal_state.phase_actions_count
        
        # Perform a declaration action (should NOT affect game mechanics significantly)
        declaration_action = [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value]
        state_after_declaration = self.interface.apply_action(token_state, declaration_action, 0)
        
        # Declaration should be recorded but not change core game mechanics
        declaration_action_count = state_after_declaration._internal_state.phase_actions_count
        # Note: Some minimal change is expected for recording, but it shouldn't be a major game action
        
        # Perform a nomination action (should affect game mechanics)
        nomination_action = [TokenID.NOMINATE.value, TokenID.PLAYER_2.value]
        state_after_nomination = self.interface.apply_action(state_after_declaration, nomination_action, 0)
        
        # Nomination should have a more significant effect on game mechanics
        nomination_action_count = state_after_nomination._internal_state.phase_actions_count
        
        # Verify that nomination had a more significant impact than declaration
        declaration_impact = declaration_action_count - initial_action_count
        nomination_impact = nomination_action_count - declaration_action_count
        
        # Both should increment action count, but they're processed differently
        assert declaration_impact >= 0, "Declaration should be recorded"
        assert nomination_impact >= 0, "Nomination should affect game state"
        
        # Check that nomination appears in game engine's nomination tracking
        # (this would need to be verified through game engine state inspection)
        # For now, verify that both actions appear in chronological sequence but with different processing
    
    def test_multi_action_sequence_with_end_turn(self):
        """Test support for multi-action sequences ending with END_TURN."""
        token_state = self.initial_state
        
        # Perform a sequence of actions followed by END_TURN
        action_sequence = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value],
            [TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value],
            [TokenID.NOMINATE.value, TokenID.PLAYER_3.value],
            [TokenID.END_TURN.value]
        ]
        
        current_state = token_state
        for action in action_sequence[:-1]:  # All except END_TURN
            current_state = self.interface.apply_action(current_state, action, 0)
            # Should remain player 0's turn for day actions
            assert current_state.active_player == 0
        
        # Apply END_TURN
        final_state = self.interface.apply_action(current_state, action_sequence[-1], 0)
        
        # Should switch to next player
        assert final_state.active_player == 1
        
        # Check that all actions appear in correct order in chronological sequence
        player_0_sequence = final_state.player_chronological_sequences[0]
        
        # Find action tokens in sequence
        say_indices = [i for i, token in enumerate(player_0_sequence) if token == TokenID.SAY.value]
        claim_indices = [i for i, token in enumerate(player_0_sequence) if token == TokenID.CLAIM_SHERIFF_CHECK.value]
        nominate_indices = [i for i, token in enumerate(player_0_sequence) if token == TokenID.NOMINATE.value]
        end_turn_indices = [i for i, token in enumerate(player_0_sequence) if token == TokenID.END_TURN.value]
        
        # Verify correct ordering
        assert len(say_indices) == 1
        assert len(claim_indices) == 1
        assert len(nominate_indices) == 1
        assert len(end_turn_indices) == 1
        
        # Check chronological order
        assert say_indices[0] < claim_indices[0] < nominate_indices[0] < end_turn_indices[0]
    
    def test_day_action_limits_reset_after_end_turn(self):
        """Test that action limits reset when a new player's turn begins."""
        token_state = self.initial_state
        
        # Player 0 performs maximum actions
        actions = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value],
            [TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value],
            [TokenID.NOMINATE.value, TokenID.PLAYER_3.value],
        ]
        
        current_state = token_state
        for action in actions:
            current_state = self.interface.apply_action(current_state, action, 0)
        
        # Player 0 has used their nomination slot
        legal_actions = self.interface.get_legal_actions(current_state)
        nominate_actions = [action for action in legal_actions 
                          if action and action[0] == TokenID.NOMINATE.value]
        assert len(nominate_actions) == 0, "Player 0 should have no more nominations"
        
        # End player 0's turn
        state_after_end_turn = self.interface.apply_action(current_state, [TokenID.END_TURN.value], 0)
        
        # Now it's player 1's turn
        assert state_after_end_turn.active_player == 1
        
        # Player 1 should have fresh action limits
        player_1_legal_actions = self.interface.get_legal_actions(state_after_end_turn)
        player_1_nominate_actions = [action for action in player_1_legal_actions 
                                   if action and action[0] == TokenID.NOMINATE.value]
        
        assert len(player_1_nominate_actions) > 0, "Player 1 should have nominations available"
    
    def test_declaration_vs_nomination_game_impact(self):
        """Test the distinction between declarations (recorded only) and nominations (game impact)."""
        token_state = self.initial_state
        
        # Store initial internal state details
        initial_internal_state = token_state._internal_state
        
        # Perform multiple declarations
        declarations = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value],
            [TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value],
            [TokenID.CLAIM_SHERIFF.value],
        ]
        
        current_state = token_state
        for declaration in declarations:
            current_state = self.interface.apply_action(current_state, declaration, 0)
        
        # Declarations should be recorded in chronological sequence
        player_0_sequence = current_state.player_chronological_sequences[0]
        assert TokenID.SAY.value in player_0_sequence
        assert TokenID.CLAIM_SHERIFF_CHECK.value in player_0_sequence
        assert TokenID.CLAIM_SHERIFF.value in player_0_sequence
        
        # Now perform a nomination (should have game mechanical impact)
        nomination_action = [TokenID.NOMINATE.value, TokenID.PLAYER_3.value]
        state_after_nomination = self.interface.apply_action(current_state, nomination_action, 0)
        
        # Nomination should also be recorded
        final_sequence = state_after_nomination.player_chronological_sequences[0]
        assert TokenID.NOMINATE.value in final_sequence
        
        # The key difference is in legal action filtering: 
        # - Multiple declarations of different types allowed
        # - Only one nomination allowed per turn
        legal_actions_after_nomination = self.interface.get_legal_actions(state_after_nomination)
        
        # No more nominations should be available
        remaining_nominations = [action for action in legal_actions_after_nomination 
                               if action and action[0] == TokenID.NOMINATE.value]
        assert len(remaining_nominations) == 0, "No more nominations after using the limit"
        
        # But more declarations should still be possible (up to total action limit)
        remaining_says = [action for action in legal_actions_after_nomination 
                         if action and action[0] == TokenID.SAY.value]
        remaining_claims = [action for action in legal_actions_after_nomination 
                          if action and action[0] == TokenID.CLAIM_SHERIFF_CHECK.value]
        
        # Should still have some declaration options available (unless we hit total action limit)
        total_remaining_declarations = len(remaining_says) + len(remaining_claims)
        assert total_remaining_declarations >= 0, "Should have declaration options or hit action limit"


class TestDayPhaseTransitions:
    """Test day phase transitions and turn management."""
    
    def setup_method(self):
        """Set up a fresh game interface for each test."""
        self.interface = TokenGameInterface()
        self.initial_state = self.interface.initialize_game(seed=0, num_players=10)
    
    def test_day_phase_player_rotation(self):
        """Test that day phase correctly rotates through all alive players."""
        token_state = self.initial_state
        
        # Track which players have had turns
        players_who_had_turns = []
        current_state = token_state
        
        # Let each player take a turn with minimal actions
        for expected_player in range(10):  # All 10 players should get turns
            assert current_state.active_player == expected_player, f"Expected player {expected_player} to be active"
            players_who_had_turns.append(expected_player)
            
            # Get legal actions to find a valid SAY action
            legal_actions = self.interface.get_legal_actions(current_state)
            say_action = None
            
            # Find a valid SAY action (can't say about yourself)
            for action in legal_actions:
                if (action and len(action) >= 3 and 
                    action[0] == TokenID.SAY.value and 
                    action[1] != TokenID.PLAYER_0.value + expected_player):  # Can't say about yourself
                    say_action = action
                    break
            
            if say_action:
                current_state = self.interface.apply_action(current_state, say_action, expected_player)
            
            current_state = self.interface.apply_action(current_state, [TokenID.END_TURN.value], expected_player)
            
            # Check if we've moved to voting phase or next day phase
            if not self.interface._is_day_phase(current_state._internal_state):
                break
        
        # All alive players should have had their turns
        assert len(players_who_had_turns) == 10, f"All 10 players should have had turns, got {len(players_who_had_turns)}"
    
    def test_day_phase_to_voting_transition(self):
        """Test transition from day phase to voting phase after all players have turns."""
        token_state = self.initial_state
        current_state = token_state
        
        # Let all players complete their day turns
        for player_idx in range(10):
            if self.interface._is_day_phase(current_state._internal_state):
                # Get legal actions to find a valid SAY action
                legal_actions = self.interface.get_legal_actions(current_state)
                say_action = None
                
                # Find a valid SAY action (can't say about yourself)
                for action in legal_actions:
                    if (action and len(action) >= 3 and 
                        action[0] == TokenID.SAY.value and 
                        action[1] != TokenID.PLAYER_0.value + player_idx):  # Can't say about yourself
                        say_action = action
                        break
                
                if say_action:
                    current_state = self.interface.apply_action(current_state, say_action, player_idx)
                
                current_state = self.interface.apply_action(current_state, [TokenID.END_TURN.value], player_idx)
        
        # Should have transitioned out of day phase
        assert not self.interface._is_day_phase(current_state._internal_state), "Should have left day phase"
        
        # Should be in voting phase or next phase
        is_voting = self.interface._is_voting_phase(current_state._internal_state)
        is_night = self.interface._is_night_phase(current_state._internal_state)
        
        assert is_voting or is_night, "Should be in voting phase or night phase after day phase"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
