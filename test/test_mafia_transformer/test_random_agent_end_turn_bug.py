"""
Unit tests to catch the bug where TokenRandomAgent generates illegal action sequences
with END_TURN tokens in the middle of day phase action sequences.
"""
import pytest
from unittest.mock import Mock, patch
import random

from mafia_game.game_state import GameState
from mafia_transformer.token_random_agent import TokenRandomAgent
from mafia_transformer.token_vocab import TokenID


@pytest.fixture
def game_state():
    """Set up test game state."""
    game_state = Mock(spec=GameState)
    game_state.current_phase = Mock()
    game_state.current_phase.__class__.__name__ = "Day1Phase"
    game_state.turn = 1
    
    # Mock some available actions
    mock_actions = [
        Mock(action_type="say", target=0, color="red"),
        Mock(action_type="claim_sheriff_check", target=1, color="black"),
        Mock(action_type="nominate", target=2),
        Mock(action_type="end_turn")
    ]
    game_state.get_available_actions = Mock(return_value=mock_actions)
    
    return game_state


@pytest.fixture
def agent(game_state):
    """Create TokenRandomAgent with mocked game state."""
    return TokenRandomAgent(game_state)


def test_day_phase_sequence_no_internal_end_turn(agent):
    """Test that day phase sequences don't have END_TURN tokens in the middle."""
    # Set random seed for reproducibility
    random.seed(42)
    
    # Get action from agent
    action_sequence = agent.get_action(player_index=0)
    
    # If it's a token sequence (list of integers), check for illegal pattern
    if isinstance(action_sequence, list) and all(isinstance(x, int) for x in action_sequence):
        # Find all END_TURN tokens
        end_turn_positions = [i for i, token in enumerate(action_sequence) 
                            if token == TokenID.END_TURN.value]
        
        # END_TURN should only appear at the end of the sequence
        if end_turn_positions:
            # Should only be one END_TURN and it should be at the last position
            assert len(end_turn_positions) == 1, \
                f"Multiple END_TURN tokens found at positions: {end_turn_positions}"
            assert end_turn_positions[0] == len(action_sequence) - 1, \
                f"END_TURN token found at position {end_turn_positions[0]} but should be at end (position {len(action_sequence) - 1})"


def test_day_phase_multiple_sequences_no_internal_end_turn(agent):
    """Test multiple random sequences to catch the bug more reliably."""
    for seed in range(10):  # Test with different random seeds
        random.seed(seed)
        
        action_sequence = agent.get_action(player_index=0)
        
        # If it's a token sequence, check for illegal pattern
        if isinstance(action_sequence, list) and all(isinstance(x, int) for x in action_sequence):
            # Find all END_TURN tokens
            end_turn_positions = [i for i, token in enumerate(action_sequence) 
                                if token == TokenID.END_TURN.value]
            
            # Check that END_TURN only appears at the end
            if end_turn_positions:
                assert len(end_turn_positions) == 1, \
                    f"Seed {seed}: Multiple END_TURN tokens found at positions: {end_turn_positions}"
                assert end_turn_positions[0] == len(action_sequence) - 1, \
                    f"Seed {seed}: END_TURN token found at position {end_turn_positions[0]} but should be at end"


def test_specific_failing_case(agent):
    """Test the specific case that was failing in the server log."""
    # Set seed to reproduce the failing case from server log
    random.seed(557)  # This was the random-seed in the failing UAT
    
    action_sequence = agent.get_action(player_index=2)  # Player 2 was failing
    
    # Check the sequence
    if isinstance(action_sequence, list) and all(isinstance(x, int) for x in action_sequence):
        # Convert to readable format for debugging
        from mafia_transformer.token_vocab import TOKEN_ID_TO_NAME
        token_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in action_sequence]
        
        # Find END_TURN tokens
        end_turn_positions = [i for i, token in enumerate(action_sequence) 
                            if token == TokenID.END_TURN.value]
        
        # Should not have END_TURN in the middle
        if len(end_turn_positions) > 1:
            pytest.fail(f"Multiple END_TURN tokens found in sequence: {token_names}\n"
                       f"END_TURN at positions: {end_turn_positions}")
        elif len(end_turn_positions) == 1 and end_turn_positions[0] != len(action_sequence) - 1:
            pytest.fail(f"END_TURN token found in middle of sequence: {token_names}\n"
                       f"END_TURN at position {end_turn_positions[0]} but sequence length is {len(action_sequence)}")


@patch('mafia_transformer.token_encoder.encode_action')
def test_encode_action_returns_with_end_turn(mock_encode, agent):
    """Test case where encode_action returns sequences with END_TURN that should be handled properly."""
    # Mock encode_action to return sequences that include END_TURN (simulating the bug condition)
    # This mimics the actual bug where END_TURN tokens appear in unexpected places
    mock_encode.side_effect = [
        [TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.END_TURN.value, TokenID.PLAYER_1.value, TokenID.BLACK.value],  # END_TURN in middle
        [TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.END_TURN.value, TokenID.RED.value],  # END_TURN in middle
        [TokenID.NOMINATE.value, TokenID.PLAYER_3.value, TokenID.END_TURN.value],  # END_TURN at end
        [TokenID.END_TURN.value]  # Just END_TURN
    ]
    
    random.seed(42)
    action_sequence = agent.get_action(player_index=0)
    
    # Check that the agent properly handles these sequences
    if isinstance(action_sequence, list) and all(isinstance(x, int) for x in action_sequence):
        # Should not have multiple END_TURN tokens or END_TURN in middle
        end_turn_count = action_sequence.count(TokenID.END_TURN.value)
        assert end_turn_count <= 1, "Should have at most one END_TURN token"
        
        if end_turn_count == 1:
            end_turn_pos = action_sequence.index(TokenID.END_TURN.value)
            assert end_turn_pos == len(action_sequence) - 1, \
                "END_TURN should only be at the end of sequence"


if __name__ == '__main__':
    pytest.main([__file__])
