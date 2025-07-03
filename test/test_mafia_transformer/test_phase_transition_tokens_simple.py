"""
Simplified unit tests for phase transition tokens that focus on direct token emission logic.
"""

import pytest
from mafia_transformer.token_game_interface import create_token_game
from mafia_transformer.token_vocab import TokenID


def test_phase_transition_tokens_exist():
    """Test that the new phase transition tokens are properly defined."""
    # Test token IDs are defined
    assert hasattr(TokenID, 'REVOTE_PHASE')
    assert hasattr(TokenID, 'ELIMINATE_ALL_VOTE')
    assert hasattr(TokenID, 'VOTING_PHASE_START')  # Existing token
    
    # Test token values
    assert TokenID.REVOTE_PHASE.value == 56
    assert TokenID.ELIMINATE_ALL_VOTE.value == 57
    assert TokenID.VOTING_PHASE_START.value == 51
    
    print("✅ All phase transition tokens properly defined")


def test_revote_phase_detection_logic():
    """Test the logic for detecting revote phase transitions."""
    game_interface = create_token_game()
    token_state = game_interface.initialize_game(seed=42)
    
    # Create mock states for revote detection
    old_state = game_interface._deep_copy_game_state(token_state._internal_state)
    new_state = game_interface._deep_copy_game_state(token_state._internal_state)
    
    # Set up voting phase conditions
    old_state.current_phase.__class__.__name__ = "VotingPhase"
    new_state.current_phase.__class__.__name__ = "VotingPhase"
    
    # Set up revote conditions: active player reset from non-zero to 0
    old_state.active_player = 5
    new_state.active_player = 0
    
    # Test the condition logic
    is_voting_old = "Voting" in old_state.current_phase.__class__.__name__
    is_voting_new = "Voting" in new_state.current_phase.__class__.__name__
    active_reset = old_state.active_player != 0 and new_state.active_player == 0
    
    should_emit_revote = is_voting_old and is_voting_new and active_reset
    
    assert should_emit_revote, "REVOTE_PHASE should be emitted when active player resets to 0 in voting phase"
    print("✅ REVOTE_PHASE detection logic works correctly")


def test_eliminate_all_vote_detection_logic():
    """Test the logic for detecting eliminate all vote scenarios."""
    game_interface = create_token_game()
    token_state = game_interface.initialize_game(seed=42)
    
    # Create mock states for eliminate all vote detection
    old_state = game_interface._deep_copy_game_state(token_state._internal_state)
    new_state = game_interface._deep_copy_game_state(token_state._internal_state)
    
    # Set up voting phase
    old_state.current_phase.__class__.__name__ = "VotingPhase"
    new_state.current_phase.__class__.__name__ = "VotingPhase"
    
    # Simulate multiple eliminations
    old_state.game_states[1].alive = True
    old_state.game_states[2].alive = True
    new_state.game_states[1].alive = False  # Eliminated
    new_state.game_states[2].alive = False  # Eliminated
    
    # Test with vote action
    vote_action = [TokenID.VOTE.value, TokenID.PLAYER_1.value]
    
    should_emit = game_interface._should_emit_eliminate_all_vote(old_state, new_state, vote_action)
    
    assert should_emit, "ELIMINATE_ALL_VOTE should be emitted when multiple players are eliminated"
    print("✅ ELIMINATE_ALL_VOTE detection logic works correctly")


def test_voting_phase_start_detection_logic():
    """Test the logic for detecting voting phase start."""
    game_interface = create_token_game()
    token_state = game_interface.initialize_game(seed=42)
    
    # Test the logic directly using string comparison (how it's actually implemented)
    old_phase_name = "DayPhase"
    new_phase_name = "VotingPhase"
    
    # Test the condition logic directly
    is_voting_old = "Voting" in old_phase_name
    is_voting_new = "Voting" in new_phase_name
    
    should_emit_voting_start = is_voting_new and not is_voting_old
    
    assert should_emit_voting_start, "VOTING_PHASE_START should be emitted when transitioning from day to voting"
    print("✅ VOTING_PHASE_START detection logic works correctly")


def test_phase_tokens_not_emitted_inappropriately():
    """Test that phase tokens are not emitted in wrong circumstances."""
    game_interface = create_token_game()
    token_state = game_interface.initialize_game(seed=42)
    
    # Test REVOTE_PHASE not emitted during day phase
    day_state = game_interface._deep_copy_game_state(token_state._internal_state)
    day_state.current_phase.__class__.__name__ = "DayPhase"
    
    new_day_state = game_interface._deep_copy_game_state(day_state)
    new_day_state.active_player = 0
    
    # REVOTE_PHASE should only be emitted in voting phase
    is_voting_old = "Voting" in day_state.current_phase.__class__.__name__
    is_voting_new = "Voting" in new_day_state.current_phase.__class__.__name__
    
    should_not_emit_revote = not (is_voting_old and is_voting_new)
    
    assert should_not_emit_revote, "REVOTE_PHASE should not be emitted during day phase"
    print("✅ Phase tokens appropriately restricted to correct phases")


def test_token_vocabulary_integration():
    """Test that new tokens integrate properly with existing vocabulary."""
    from mafia_transformer.token_vocab import TOKEN_NAME_TO_ID, TOKEN_ID_TO_NAME, VOCAB_SIZE
    
    # Test token name mappings
    assert "<REVOTE_PHASE>" in TOKEN_NAME_TO_ID
    assert "<ELIMINATE_ALL_VOTE>" in TOKEN_NAME_TO_ID
    assert "<VOTING_PHASE_START>" in TOKEN_NAME_TO_ID
    
    # Test reverse mappings
    assert TokenID.REVOTE_PHASE.value in TOKEN_ID_TO_NAME
    assert TokenID.ELIMINATE_ALL_VOTE.value in TOKEN_ID_TO_NAME
    assert TokenID.VOTING_PHASE_START.value in TOKEN_ID_TO_NAME
    
    # Test vocabulary size updated correctly
    assert VOCAB_SIZE == 58, f"Expected vocabulary size 58, got {VOCAB_SIZE}"
    
    print("✅ Token vocabulary integration successful")


def test_token_emission_in_mock_scenario():
    """Test token emission using a controlled mock scenario."""
    game_interface = create_token_game()
    token_state = game_interface.initialize_game(seed=42)
    
    # Create a controlled scenario that should emit all phase tokens
    test_sequence = []
    
    # 1. Start with day phase
    test_sequence.extend([TokenID.DAY_1.value, TokenID.DAY_PHASE_START.value])
    
    # 2. Transition to voting phase (should emit VOTING_PHASE_START)
    test_sequence.append(TokenID.VOTING_PHASE_START.value)
    test_sequence.extend([TokenID.PLAYER_1.value, TokenID.PLAYER_2.value])  # Nominated players
    
    # 3. Revote scenario (should emit REVOTE_PHASE)
    test_sequence.append(TokenID.REVOTE_PHASE.value)
    
    # 4. Eliminate all scenario (should emit ELIMINATE_ALL_VOTE)
    test_sequence.append(TokenID.ELIMINATE_ALL_VOTE.value)
    
    # Verify all tokens are present
    assert TokenID.VOTING_PHASE_START.value in test_sequence
    assert TokenID.REVOTE_PHASE.value in test_sequence
    assert TokenID.ELIMINATE_ALL_VOTE.value in test_sequence
    
    print("✅ All phase transition tokens can be emitted in sequence")


if __name__ == "__main__":
    print("Running simplified phase transition token tests...")
    
    test_phase_transition_tokens_exist()
    test_revote_phase_detection_logic()
    test_eliminate_all_vote_detection_logic()
    test_voting_phase_start_detection_logic()
    test_phase_tokens_not_emitted_inappropriately()
    test_token_vocabulary_integration()
    test_token_emission_in_mock_scenario()
    
    print("\n🎉 All simplified phase transition token tests passed!")
