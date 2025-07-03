#!/usr/bin/env python3
"""
Test script to verify that multi-step day turns only apply nominations to game engine
while recording all actions in chronological sequences.
"""

from src.mafia_transformer.token_game_interface import TokenGameInterface
from src.mafia_transformer.token_vocab import TokenID

def test_nomination_only_affects_game_mechanics():
    """Test that in multi-step day turns, only nominations affect game mechanics."""
    
    interface = TokenGameInterface()
    token_state = interface.initialize_game(seed=42, num_players=10)
    
    print("=== Testing Multi-Step Day Turn with Nomination Fix ===")
    print(f"Initial active player: {token_state.active_player}")
    
    # Check initial nomination state in game engine
    initial_nominations = token_state._internal_state.nominated_players.copy()
    print(f"Initial nominated players: {initial_nominations}")
    
    # Perform a multi-step day turn with various actions including nomination
    multi_action_sequence = [
        TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value,        # Declaration
        TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.PLAYER_2.value, TokenID.BLACK.value,  # Declaration
        TokenID.NOMINATE.value, TokenID.PLAYER_3.value,                      # Nomination (should affect game)
        TokenID.SAY.value, TokenID.PLAYER_4.value, TokenID.BLACK.value,     # Another declaration
        TokenID.END_TURN.value
    ]
    
    print(f"Applying multi-action sequence: {[hex(t) for t in multi_action_sequence]}")
    
    # Apply the multi-action sequence
    new_state = interface.apply_action(token_state, multi_action_sequence, token_state.active_player)
    
    # Check the game engine state after actions
    final_nominations = new_state._internal_state.nominated_players.copy()
    print(f"Final nominated players: {final_nominations}")
    
    # Verify that only the nomination affected the game engine
    expected_nominations = initial_nominations + [3]  # Player 3 was nominated
    
    if final_nominations == expected_nominations:
        print("✅ SUCCESS: Only nomination was applied to game engine!")
        print(f"   Expected: {expected_nominations}")
        print(f"   Actual: {final_nominations}")
    else:
        print("❌ FAILED: Unexpected nomination state!")
        print(f"   Expected: {expected_nominations}")
        print(f"   Actual: {final_nominations}")
        return False
    
    # Check that all actions were recorded in chronological sequences
    player_sequence = new_state.player_chronological_sequences[token_state.active_player]
    
    # Count actions in sequence
    say_count = player_sequence.count(TokenID.SAY.value)
    claim_check_count = player_sequence.count(TokenID.CLAIM_SHERIFF_CHECK.value)
    nominate_count = player_sequence.count(TokenID.NOMINATE.value)
    end_turn_count = player_sequence.count(TokenID.END_TURN.value)
    
    print(f"\n=== Actions recorded in chronological sequence ===")
    print(f"SAY actions: {say_count}")
    print(f"CLAIM_SHERIFF_CHECK actions: {claim_check_count}")
    print(f"NOMINATE actions: {nominate_count}")
    print(f"END_TURN actions: {end_turn_count}")
    
    # Verify all actions were recorded
    if say_count == 2 and claim_check_count == 1 and nominate_count == 1 and end_turn_count == 1:
        print("✅ SUCCESS: All actions recorded in chronological sequence!")
    else:
        print("❌ FAILED: Not all actions recorded correctly!")
        return False
    
    print(f"\n=== Active player transition ===")
    print(f"Previous active player: {token_state.active_player}")
    print(f"New active player: {new_state.active_player}")
    
    if new_state.active_player != token_state.active_player:
        print("✅ SUCCESS: Active player changed after END_TURN!")
    else:
        print("❌ FAILED: Active player did not change!")
        return False
    
    return True

def test_single_nomination_only():
    """Test that a single nomination action still works correctly."""
    
    print("\n=== Testing Single Nomination Action ===")
    
    interface = TokenGameInterface()
    token_state = interface.initialize_game(seed=123, num_players=10)
    
    # Check initial nomination state
    initial_nominations = token_state._internal_state.nominated_players.copy()
    print(f"Initial nominated players: {initial_nominations}")
    
    # Apply single nomination
    nomination_action = [TokenID.NOMINATE.value, TokenID.PLAYER_5.value]
    state_after_nomination = interface.apply_action(token_state, nomination_action, token_state.active_player)
    
    # Check nominations in game engine
    after_nomination = state_after_nomination._internal_state.nominated_players.copy()
    print(f"After single nomination: {after_nomination}")
    
    # Apply END_TURN
    end_turn_state = interface.apply_action(state_after_nomination, [TokenID.END_TURN.value], token_state.active_player)
    final_nominations = end_turn_state._internal_state.nominated_players.copy()
    
    print(f"Final nominations after END_TURN: {final_nominations}")
    
    expected = initial_nominations + [5]
    if final_nominations == expected:
        print("✅ SUCCESS: Single nomination applied correctly!")
        return True
    else:
        print("❌ FAILED: Single nomination not applied!")
        return False

if __name__ == "__main__":
    print("Testing nomination fix for multi-step day turns...")
    
    success1 = test_nomination_only_affects_game_mechanics()
    success2 = test_single_nomination_only()
    
    if success1 and success2:
        print("\n🎉 ALL TESTS PASSED! Nomination fix is working correctly.")
    else:
        print("\n💥 SOME TESTS FAILED! Please check the implementation.")
