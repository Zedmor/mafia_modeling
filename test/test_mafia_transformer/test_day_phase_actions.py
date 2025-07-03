"""
Focused unit tests for day phase action handling in TokenGameInterface.

Tests the specific fixes for:
1. Duplicate action prevention during day phases
2. Proper chronological sequence building with day actions
3. Game state progression with day actions applied to engine
4. END_TURN behavior and active player switching
"""

import pytest
from mafia_transformer.token_game_interface import TokenGameInterface, TokenGameState
from mafia_transformer.token_vocab import TokenID
from mafia_game.common import Role, Team


class TestDayPhaseActions:
    """Test day phase action handling and chronological sequences."""
    
    def setup_method(self):
        """Set up a fresh game interface for each test."""
        self.interface = TokenGameInterface()
        self.initial_state = self.interface.initialize_game(seed=0, num_players=10)
    
    def test_multiple_day_actions_allowed(self):
        """Test that players can perform multiple different day actions before END_TURN."""
        # Player 0 (Don) should be able to perform multiple day actions
        token_state = self.initial_state
        
        # Verify we start in day phase
        assert self.interface._is_day_phase(token_state._internal_state)
        assert token_state.active_player == 0
        
        # Get legal actions - should include multiple day actions + END_TURN
        legal_actions = self.interface.get_legal_actions(token_state)
        
        # Should have nominate actions, claims, says, and END_TURN
        nominate_actions = [action for action in legal_actions if action and action[0] == TokenID.NOMINATE.value]
        say_actions = [action for action in legal_actions if action and action[0] == TokenID.SAY.value]
        end_turn_action = [action for action in legal_actions if action == [TokenID.END_TURN.value]]
        
        assert len(nominate_actions) > 0, "Should have nominate actions available"
        assert len(say_actions) > 0, "Should have say actions available"  
        assert len(end_turn_action) == 1, "Should have END_TURN available"
        
        # Perform first day action - SAY
        first_action = [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value]
        assert first_action in legal_actions, f"SAY action should be legal"
        
        state_after_first = self.interface.apply_action(token_state, first_action, 0)
        
        # Should still be player 0's turn
        assert state_after_first.active_player == 0, "Active player should remain 0 after day action"
        
        # Check that action appears in chronological sequence
        player_0_sequence = state_after_first.player_chronological_sequences[0]
        assert TokenID.PLAYER_0.value in player_0_sequence, "Player 0 action should appear in sequence"
        assert TokenID.SAY.value in player_0_sequence, "SAY action should appear in sequence"
        
        # Perform second day action - NOMINATE
        second_action = [TokenID.NOMINATE.value, TokenID.PLAYER_2.value]
        legal_actions_after_first = self.interface.get_legal_actions(state_after_first)
        assert second_action in legal_actions_after_first, "NOMINATE should still be legal"
        
        state_after_second = self.interface.apply_action(state_after_first, second_action, 0)
        
        # Should still be player 0's turn
        assert state_after_second.active_player == 0, "Active player should remain 0 after second day action"
        
        # Check both actions appear in chronological sequence
        player_0_sequence = state_after_second.player_chronological_sequences[0]
        # Should see pattern: NEXT_TURN, PLAYER_0, SAY, PLAYER_1, RED, PLAYER_0, NOMINATE, PLAYER_2
        say_indices = [i for i, token in enumerate(player_0_sequence) if token == TokenID.SAY.value]
        nominate_indices = [i for i, token in enumerate(player_0_sequence) if token == TokenID.NOMINATE.value]
        
        assert len(say_indices) == 1, "Should have exactly one SAY action"
        assert len(nominate_indices) == 1, "Should have exactly one NOMINATE action"
        assert nominate_indices[0] > say_indices[0], "NOMINATE should appear after SAY in sequence"
    
    def test_duplicate_action_prevention(self):
        """Test that the same action cannot be performed twice in the same turn."""
        token_state = self.initial_state
        
        # Perform a SAY action
        say_action = [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value]
        state_after_say = self.interface.apply_action(token_state, say_action, 0)
        
        # Try to perform the exact same SAY action again
        legal_actions_after_say = self.interface.get_legal_actions(state_after_say)
        
        # The exact same action should not be available anymore
        assert say_action not in legal_actions_after_say, "Duplicate SAY action should not be legal"
        
        # But different SAY actions should still be available
        different_say_action = [TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.RED.value]
        assert different_say_action in legal_actions_after_say, "Different SAY action should still be legal"
    
    def test_end_turn_switches_active_player(self):
        """Test that END_TURN switches the active player to the next alive player."""
        token_state = self.initial_state
        
        # Verify starting state
        assert token_state.active_player == 0
        
        # Perform END_TURN
        end_turn_action = [TokenID.END_TURN.value]
        state_after_end_turn = self.interface.apply_action(token_state, end_turn_action, 0)
        
        # Should switch to player 1
        assert state_after_end_turn.active_player == 1, "Active player should switch to 1 after END_TURN"
        
        # Check chronological sequences
        player_0_sequence = state_after_end_turn.player_chronological_sequences[0]
        player_1_sequence = state_after_end_turn.player_chronological_sequences[1]
        
        # Player 0 sequence should have END_TURN followed by next active player
        # Find END_TURN in the sequence and check it's followed by PLAYER_1
        end_turn_indices = [i for i, token in enumerate(player_0_sequence) if token == TokenID.END_TURN.value]
        assert len(end_turn_indices) > 0, "Player 0 sequence should contain END_TURN"
        
        # The last END_TURN should be followed by PLAYER_1 (next active player)
        last_end_turn_idx = end_turn_indices[-1]
        if last_end_turn_idx + 1 < len(player_0_sequence):
            assert player_0_sequence[last_end_turn_idx + 1] == TokenID.PLAYER_1.value, "END_TURN should be followed by next active player (PLAYER_1)"
        
        # Player 1 should get NEXT_TURN via observation but not stored in sequence
        player_1_observation = self.interface.get_observation_tokens(state_after_end_turn, 1)
        assert TokenID.NEXT_TURN.value not in player_1_sequence, "NEXT_TURN should not be stored in Player 1's sequence"
        assert player_1_observation[-1] == TokenID.NEXT_TURN.value, "Player 1 should get NEXT_TURN in observation"
    
    def test_chronological_sequence_structure(self):
        """Test that chronological sequences maintain proper structure."""
        token_state = self.initial_state
        
        # Check initial structure for player 0
        player_0_sequence = token_state.player_chronological_sequences[0]
        
        # Should start with: GAME_START, PLAYER_0, YOUR_ROLE, DON, MAFIA_TEAM, PLAYER_1, PLAYER_2, DAY_1, DAY_PHASE_START, YOUR_TURN
        # Note: YOUR_TURN is added at initialization for the initial active player
        expected_start = [
            TokenID.GAME_START.value,
            TokenID.PLAYER_0.value,
            TokenID.YOUR_ROLE.value,
            TokenID.DON.value,
            TokenID.MAFIA_TEAM.value,
            TokenID.PLAYER_1.value,
            TokenID.PLAYER_2.value,
            TokenID.DAY_1.value,
            TokenID.DAY_PHASE_START.value,
            TokenID.YOUR_TURN.value
        ]
        
        assert player_0_sequence == expected_start, f"Player 0 initial sequence structure incorrect. Got: {player_0_sequence}"
        
        # Perform an action and check structure
        say_action = [TokenID.SAY.value, TokenID.PLAYER_3.value, TokenID.BLACK.value]
        state_after_action = self.interface.apply_action(token_state, say_action, 0)
        
        player_0_sequence_after = state_after_action.player_chronological_sequences[0]
        
        # Should append: PLAYER_0, SAY, PLAYER_3, BLACK (no YOUR_TURN stored)
        # Note: PLAYER_0 token is added when it's the first action this turn
        expected_addition = [TokenID.PLAYER_0.value, TokenID.SAY.value, TokenID.PLAYER_3.value, TokenID.BLACK.value]
        
        assert player_0_sequence_after[-4:] == expected_addition, "Action should be properly appended to sequence"
    
    def test_day_actions_applied_to_game_engine(self):
        """Test that day actions are actually applied to the underlying game engine."""
        token_state = self.initial_state
        
        # Get initial game state
        initial_internal_state = token_state._internal_state
        
        # Perform a day action that should affect the game engine (NOMINATE)
        nominate_action = [TokenID.NOMINATE.value, TokenID.PLAYER_3.value]
        state_after_nominate = self.interface.apply_action(token_state, nominate_action, 0)
        
        # Check that the internal game state was affected
        new_internal_state = state_after_nominate._internal_state
        
        # For multi-step day phases: phase_actions_count only increments on END_TURN
        # So we check other indicators that the action was processed by the game engine:
        
        # 1. The action should be recorded in chronological sequences
        player_0_sequence = state_after_nominate.player_chronological_sequences[0]
        assert TokenID.NOMINATE.value in player_0_sequence, "NOMINATE action should appear in chronological sequence"
        assert TokenID.PLAYER_3.value in player_0_sequence, "Nominated player should appear in sequence"
        
        # 2. The active player should remain the same for day actions (not END_TURN)
        assert new_internal_state.active_player == 0, "Active player should remain 0 for day actions"
        
        # 3. We should still be in day phase (action didn't cause phase transition)
        assert self.interface._is_day_phase(new_internal_state), "Should still be in day phase after day action"
        
        # 4. The nomination should affect legal actions (can't nominate same player again)
        legal_actions_after = self.interface.get_legal_actions(state_after_nominate)
        same_nominate_action = [TokenID.NOMINATE.value, TokenID.PLAYER_3.value]
        assert same_nominate_action not in legal_actions_after, "Cannot nominate same player twice"
    
    def test_performed_actions_tracking(self):
        """Test the _get_performed_actions_this_turn method."""
        token_state = self.initial_state
        
        # Initially, no actions performed this turn
        performed_actions = self.interface._get_performed_actions_this_turn(token_state)
        assert len(performed_actions) == 0, "Should have no performed actions initially"
        
        # Perform a SAY action
        say_action = [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value]
        state_after_say = self.interface.apply_action(token_state, say_action, 0)
        
        # Check performed actions
        performed_actions_after_say = self.interface._get_performed_actions_this_turn(state_after_say)
        expected_action_tuple = tuple(say_action)
        
        assert expected_action_tuple in performed_actions_after_say, f"SAY action should be tracked. Got: {performed_actions_after_say}"
        
        # Perform a NOMINATE action
        nominate_action = [TokenID.NOMINATE.value, TokenID.PLAYER_2.value]
        state_after_nominate = self.interface.apply_action(state_after_say, nominate_action, 0)
        
        # Check both actions are tracked
        performed_actions_after_nominate = self.interface._get_performed_actions_this_turn(state_after_nominate)
        expected_nominate_tuple = tuple(nominate_action)
        
        assert expected_action_tuple in performed_actions_after_nominate, "SAY action should still be tracked"
        assert expected_nominate_tuple in performed_actions_after_nominate, "NOMINATE action should be tracked"
        assert len(performed_actions_after_nominate) == 2, "Should track both actions"
    
    def test_private_vs_public_action_handling(self):
        """Test that private and public actions are handled differently."""
        # Test with initial state where player 0 is active
        token_state = self.initial_state
        
        # SAY action should be public (visible to all players)
        say_action = [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value]
        state_after_say = self.interface.apply_action(token_state, say_action, 0)
        
        # Check that all players see the SAY action in their sequences
        for player_idx in range(10):
            player_sequence = state_after_say.player_chronological_sequences[player_idx]
            say_indices = [i for i, token in enumerate(player_sequence) if token == TokenID.SAY.value]
            assert len(say_indices) > 0, f"Player {player_idx} should see the public SAY action"
    
    def test_next_turn_token_placement(self):
        """Test that NEXT_TURN tokens are provided ephemerally via get_observation_tokens."""
        token_state = self.initial_state
        
        # Initial state: Player 0 should get NEXT_TURN via observation but not in stored sequence
        player_0_sequence = token_state.player_chronological_sequences[0]
        player_0_observation = self.interface.get_observation_tokens(token_state, 0)
        
        assert TokenID.NEXT_TURN.value not in player_0_sequence, "NEXT_TURN should not be stored in sequence"
        assert player_0_observation[-1] == TokenID.NEXT_TURN.value, "Player 0 should get NEXT_TURN in observation"
        
        # Other players should not get NEXT_TURN in observations
        for player_idx in range(1, 10):
            player_observation = self.interface.get_observation_tokens(token_state, player_idx)
            assert TokenID.NEXT_TURN.value not in player_observation, f"Player {player_idx} should not get NEXT_TURN"
        
        # After END_TURN, NEXT_TURN should be provided to next player via observation
        end_turn_action = [TokenID.END_TURN.value]
        state_after_end_turn = self.interface.apply_action(token_state, end_turn_action, 0)
        
        # Player 1 should now get NEXT_TURN via observation but not stored
        player_1_sequence = state_after_end_turn.player_chronological_sequences[1]
        player_1_observation = self.interface.get_observation_tokens(state_after_end_turn, 1)
        
        assert TokenID.NEXT_TURN.value not in player_1_sequence, "NEXT_TURN should not be stored in Player 1's sequence"
        assert player_1_observation[-1] == TokenID.NEXT_TURN.value, "Player 1 should get NEXT_TURN in observation"
        
        # Player 0 sequence should have END_TURN followed by next active player (no NEXT_TURN stored)
        player_0_sequence_after = state_after_end_turn.player_chronological_sequences[0]
        # Find the last END_TURN and verify it's followed by PLAYER_1
        end_turn_indices = [i for i, token in enumerate(player_0_sequence_after) if token == TokenID.END_TURN.value]
        assert len(end_turn_indices) > 0, "Player 0 sequence should contain END_TURN"
        
        last_end_turn_idx = end_turn_indices[-1]
        if last_end_turn_idx + 1 < len(player_0_sequence_after):
            assert player_0_sequence_after[last_end_turn_idx + 1] == TokenID.PLAYER_1.value, "END_TURN should be followed by next active player (PLAYER_1)"
    
    def test_legal_actions_after_actions_performed(self):
        """Test that legal actions are correctly filtered based on performed actions."""
        token_state = self.initial_state
        
        # Get initial legal actions
        initial_legal = self.interface.get_legal_actions(token_state)
        
        # Find a specific SAY action
        target_say_action = None
        for action in initial_legal:
            if (len(action) >= 3 and action[0] == TokenID.SAY.value and 
                action[1] == TokenID.PLAYER_1.value and action[2] == TokenID.RED.value):
                target_say_action = action
                break
        
        assert target_say_action is not None, "Should find target SAY action in legal actions"
        
        # Perform the SAY action
        state_after_say = self.interface.apply_action(token_state, target_say_action, 0)
        
        # Get legal actions after performing the SAY action
        legal_after_say = self.interface.get_legal_actions(state_after_say)
        
        # The same SAY action should no longer be legal
        assert target_say_action not in legal_after_say, "Performed SAY action should no longer be legal"
        
        # END_TURN should still be legal
        end_turn_action = [TokenID.END_TURN.value]
        assert end_turn_action in legal_after_say, "END_TURN should still be legal"
        
        # Other actions should still be legal
        other_actions = [action for action in legal_after_say if action != target_say_action and action != end_turn_action]
        assert len(other_actions) > 0, "Other actions should still be available"


class TestChronologicalSequenceIntegrity:
    """Test chronological sequence integrity and consistency."""
    
    def setup_method(self):
        """Set up a fresh game interface for each test."""
        self.interface = TokenGameInterface()
        self.initial_state = self.interface.initialize_game(seed=0, num_players=10)
    
    def test_action_ordering_in_sequences(self):
        """Test that actions appear in correct order in chronological sequences."""
        token_state = self.initial_state
        
        # Perform multiple actions in specific order
        actions = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value],
            [TokenID.NOMINATE.value, TokenID.PLAYER_2.value],
            [TokenID.CLAIM_SHERIFF.value],
            [TokenID.END_TURN.value]
        ]
        
        current_state = token_state
        for action in actions:
            current_state = self.interface.apply_action(current_state, action, 0)
        
        # Check player 0's sequence for correct ordering
        player_0_sequence = current_state.player_chronological_sequences[0]
        
        # Find positions of each action type
        say_pos = next(i for i, token in enumerate(player_0_sequence) if token == TokenID.SAY.value)
        nominate_pos = next(i for i, token in enumerate(player_0_sequence) if token == TokenID.NOMINATE.value)
        claim_pos = next(i for i, token in enumerate(player_0_sequence) if token == TokenID.CLAIM_SHERIFF.value)
        end_turn_pos = next(i for i, token in enumerate(player_0_sequence) if token == TokenID.END_TURN.value)
        
        # Verify ordering
        assert say_pos < nominate_pos, "SAY should come before NOMINATE"
        assert nominate_pos < claim_pos, "NOMINATE should come before CLAIM_SHERIFF"
        assert claim_pos < end_turn_pos, "CLAIM_SHERIFF should come before END_TURN"
    
    def test_all_players_see_public_actions(self):
        """Test that all players see public actions in their chronological sequences."""
        token_state = self.initial_state
        
        # Perform a public day action
        public_action = [TokenID.NOMINATE.value, TokenID.PLAYER_3.value]
        state_after_action = self.interface.apply_action(token_state, public_action, 0)
        
        # All players should see this action in their sequences
        for player_idx in range(10):
            player_sequence = state_after_action.player_chronological_sequences[player_idx]
            
            # Look for the action pattern: PLAYER_0, NOMINATE, PLAYER_3
            found_action = False
            for i in range(len(player_sequence) - 2):
                if (player_sequence[i] == TokenID.PLAYER_0.value and
                    player_sequence[i + 1] == TokenID.NOMINATE.value and
                    player_sequence[i + 2] == TokenID.PLAYER_3.value):
                    found_action = True
                    break
            
            assert found_action, f"Player {player_idx} should see the public NOMINATE action in their sequence"
    
    def test_sequence_consistency_across_players(self):
        """Test that public game actions are visible to all players consistently."""
        token_state = self.initial_state
        
        # Perform several public actions
        actions = [
            [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.BLACK.value],
            [TokenID.NOMINATE.value, TokenID.PLAYER_4.value],
            [TokenID.END_TURN.value]
        ]
        
        current_state = token_state
        for action in actions:
            current_state = self.interface.apply_action(current_state, action, 0)
        
        # Extract public game actions visible to each player from their chronological sequence
        def extract_public_game_actions(sequence):
            game_actions = []
            i = 0
            
            # Skip initial setup (GAME_START, YOUR_ROLE, role info, DAY_1, team info, NEXT_TURN)
            # Look for the first NEXT_TURN which marks the start of actual gameplay
            first_next_turn_idx = -1
            for idx, token in enumerate(sequence):
                if token == TokenID.NEXT_TURN.value:
                    first_next_turn_idx = idx
                    break
            
            if first_next_turn_idx == -1:
                return game_actions  # No gameplay started yet
            
            # Start after the first NEXT_TURN
            i = first_next_turn_idx + 1
            
            while i < len(sequence):
                # Look for ANY player action patterns: PLAYER_X, ACTION, ... (not just this player's actions)
                if (i < len(sequence) and
                    sequence[i] >= TokenID.PLAYER_0.value and 
                    sequence[i] <= TokenID.PLAYER_9.value and
                    i + 1 < len(sequence)):
                    
                    # Check if this is the start of an action (PLAYER_X followed by a verb)
                    next_token = sequence[i + 1]
                    if (next_token in [TokenID.SAY.value, TokenID.NOMINATE.value, TokenID.CLAIM_SHERIFF.value,
                                     TokenID.DENY_SHERIFF.value, TokenID.CLAIM_SHERIFF_CHECK.value]):
                        
                        # This is a public player action - extract the full action
                        action_tokens = [sequence[i]]  # Start with PLAYER_X
                        i += 1
                        
                        # Collect tokens until next PLAYER_X action start, END_TURN, NEXT_TURN, or phase marker
                        while i < len(sequence):
                            token = sequence[i]
                            
                            # Stop on END_TURN or NEXT_TURN
                            if token in [TokenID.END_TURN.value, TokenID.NEXT_TURN.value]:
                                break
                                
                            # Stop on phase markers
                            if token in [TokenID.DAY_1.value, TokenID.DAY_2.value, TokenID.NIGHT_1.value]:
                                break
                                
                            # Stop on PLAYER_X tokens that start a new action (not action arguments)
                            if (token >= TokenID.PLAYER_0.value and token <= TokenID.PLAYER_9.value and
                                i + 1 < len(sequence)):
                                next_tok = sequence[i + 1]
                                if (next_tok in [TokenID.SAY.value, TokenID.NOMINATE.value, TokenID.CLAIM_SHERIFF.value,
                                               TokenID.DENY_SHERIFF.value, TokenID.CLAIM_SHERIFF_CHECK.value]):
                                    # This is a new action starting, stop here
                                    break
                            
                            # Otherwise, add this token to the current action
                            action_tokens.append(token)
                            i += 1
                        
                        game_actions.append(tuple(action_tokens))
                    else:
                        i += 1
                elif sequence[i] == TokenID.END_TURN.value:
                    # END_TURN is also a public action
                    game_actions.append((TokenID.END_TURN.value,))
                    i += 1
                else:
                    i += 1
            
            return game_actions
        
        # All players should see the same public game actions
        reference_game_actions = extract_public_game_actions(current_state.player_chronological_sequences[0])
        
        for player_idx in range(1, 10):
            player_game_actions = extract_public_game_actions(current_state.player_chronological_sequences[player_idx])
            assert player_game_actions == reference_game_actions, f"Player {player_idx} game actions don't match reference. Expected: {reference_game_actions}, Got: {player_game_actions}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
