"""
Test for the <NEXT_TURN> ephemeral token functionality.

This test demonstrates that:
1. <NEXT_TURN> token is served to the transformer for the active player
2. <NEXT_TURN> token is NOT served to non-active players  
3. <NEXT_TURN> token is NOT stored in the chronological history
4. Player identity is clear from <GAME_START> <PLAYER_X> sequence
"""

import pytest
from mafia_transformer.token_game_interface import create_token_game
from mafia_transformer.token_vocab import TokenID, TOKEN_ID_TO_NAME


def test_next_turn_token_ephemeral_behavior():
    """Test that <NEXT_TURN> token is served ephemerally without polluting history."""
    
    # Initialize game
    game = create_token_game()
    token_state = game.initialize_game(seed=42)
    
    print("🎮 NEXT_TURN Token Test")
    print("=" * 60)
    
    # Get active player
    active_player = token_state.active_player
    print(f"🎯 Active player: {active_player}")
    
    # Test 1: Active player gets <NEXT_TURN> token in observation
    active_observation = game.get_observation_tokens(token_state, active_player)
    active_history = token_state.player_chronological_sequences[active_player]
    
    print(f"\n📊 ACTIVE PLAYER {active_player} OBSERVATION:")
    active_tokens = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in active_observation]
    print(f"   Tokens: {' '.join(active_tokens)}")
    print(f"   Length: {len(active_observation)} tokens")
    print(f"   Has <NEXT_TURN>: {'<NEXT_TURN>' in active_tokens}")
    
    print(f"\n📊 ACTIVE PLAYER {active_player} STORED HISTORY:")
    history_tokens = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in active_history]
    print(f"   Tokens: {' '.join(history_tokens)}")
    print(f"   Length: {len(active_history)} tokens")
    print(f"   Has <NEXT_TURN>: {'<NEXT_TURN>' in history_tokens}")
    
    # Test 2: Non-active players don't get <NEXT_TURN> token
    other_player = (active_player + 1) % 10
    other_observation = game.get_observation_tokens(token_state, other_player)
    other_history = token_state.player_chronological_sequences[other_player]
    
    print(f"\n📊 NON-ACTIVE PLAYER {other_player} OBSERVATION:")
    other_tokens = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in other_observation]
    print(f"   Tokens: {' '.join(other_tokens)}")
    print(f"   Length: {len(other_observation)} tokens")
    print(f"   Has <NEXT_TURN>: {'<NEXT_TURN>' in other_tokens}")
    
    # Test 3: Player identity is clear from sequence start
    print(f"\n🆔 PLAYER IDENTITY FROM SEQUENCE:")
    for player_idx in range(3):  # Show first 3 players
        sequence = token_state.player_chronological_sequences[player_idx]
        sequence_tokens = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in sequence[:4]]
        print(f"   Player {player_idx}: {' '.join(sequence_tokens)}")
    
    # Assertions
    assert TokenID.NEXT_TURN.value in active_observation, "Active player should get <NEXT_TURN> in observation"
    assert TokenID.NEXT_TURN.value not in active_history, "<NEXT_TURN> should NOT be stored in history"
    assert TokenID.NEXT_TURN.value not in other_observation, "Non-active player should NOT get <NEXT_TURN>"
    assert TokenID.NEXT_TURN.value not in other_history, "<NEXT_TURN> should NOT be in any stored history"
    
    # Test 4: Apply an action and verify <NEXT_TURN> is still not stored
    legal_actions = game.get_legal_actions(token_state)
    action_to_apply = legal_actions[0]  # Take first legal action (usually END_TURN)
    
    print(f"\n🎬 APPLYING ACTION:")
    action_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in action_to_apply]
    print(f"   Action: {' '.join(action_names)}")
    
    new_token_state = game.apply_action(token_state, action_to_apply, active_player)
    
    # Check that <NEXT_TURN> is still not in any stored history after action
    for player_idx in range(10):
        player_history = new_token_state.player_chronological_sequences[player_idx]
        assert TokenID.NEXT_TURN.value not in player_history, f"<NEXT_TURN> found in Player {player_idx} history after action"
    
    # Test 5: New active player gets <NEXT_TURN> in observation
    new_active_player = new_token_state.active_player
    new_active_observation = game.get_observation_tokens(new_token_state, new_active_player)
    
    print(f"\n🎯 NEW ACTIVE PLAYER: {new_active_player}")
    new_active_tokens = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in new_active_observation]
    print(f"   Has <NEXT_TURN>: {'<NEXT_TURN>' in new_active_tokens}")
    
    assert TokenID.NEXT_TURN.value in new_active_observation, "New active player should get <NEXT_TURN>"
    
    print("\n✅ ALL TESTS PASSED!")
    print("✅ <NEXT_TURN> token served ephemerally without polluting history")
    print("✅ Player identity clear from <GAME_START> <PLAYER_X> sequence")
    

def test_player_identity_from_sequence():
    """Test that player identity is clear from the sequence without needing <NEXT_TURN>."""
    
    game = create_token_game()
    token_state = game.initialize_game(seed=123)
    
    print("\n🆔 PLAYER IDENTITY TEST")
    print("=" * 60)
    
    # Each player should see their own ID in their sequence
    for player_idx in range(10):
        sequence = token_state.player_chronological_sequences[player_idx]
        
        # The sequence should start with: <GAME_START> <PLAYER_X> <YOUR_ROLE> <ROLE> [<MAFIA_TEAM> <PLAYER_X> ...] <DAY_1>
        assert len(sequence) >= 5, f"Player {player_idx} sequence too short"
        
        game_start_token = sequence[0]
        player_id_token = sequence[1]
        role_marker_token = sequence[2]
        role_token = sequence[3]
        
        # Verify structure
        assert game_start_token == TokenID.GAME_START.value, f"Player {player_idx} missing GAME_START"
        assert player_id_token == TokenID.PLAYER_0.value + player_idx, f"Player {player_idx} has wrong ID"
        assert role_marker_token == TokenID.YOUR_ROLE.value, f"Player {player_idx} missing YOUR_ROLE"
        
        # Find DAY_1 token - it may be at different positions depending on whether player is mafia
        day_1_found = False
        for i, token in enumerate(sequence):
            if token == TokenID.DAY_1.value:
                day_1_found = True
                break
        
        assert day_1_found, f"Player {player_idx} missing DAY_1"
        
        # Show the sequence start (show more tokens to account for team info)
        display_length = min(8, len(sequence))
        sequence_tokens = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in sequence[:display_length]]
        print(f"   Player {player_idx}: {' '.join(sequence_tokens)}")
    
    print("\n✅ Player identity clearly established in each sequence!")


def test_transformer_observation_format():
    """Test the complete observation format that would be fed to a transformer."""
    
    game = create_token_game()
    token_state = game.initialize_game(seed=456)
    
    print("\n🤖 TRANSFORMER OBSERVATION FORMAT")
    print("=" * 60)
    
    active_player = token_state.active_player
    observation_tokens = game.get_observation_tokens(token_state, active_player)
    
    print(f"🎯 Active Player: {active_player}")
    print(f"📊 Observation Length: {len(observation_tokens)} tokens")
    
    # Convert to readable format
    readable_tokens = []
    for token in observation_tokens:
        readable_tokens.append(TOKEN_ID_TO_NAME.get(token, f"UNK_{token}"))
    
    print(f"📝 Full Observation:")
    print(f"   {' '.join(readable_tokens)}")
    
    # Key checks for transformer input
    assert observation_tokens[0] == TokenID.GAME_START.value, "Should start with GAME_START"
    assert observation_tokens[1] == TokenID.PLAYER_0.value + active_player, "Should have player ID"
    assert observation_tokens[-1] == TokenID.NEXT_TURN.value, "Should end with NEXT_TURN for active player"
    
    # Show structure breakdown
    print(f"\n🏗️  STRUCTURE BREAKDOWN:")
    print(f"   Start: {readable_tokens[0]} {readable_tokens[1]}")
    print(f"   Role: {readable_tokens[2]} {readable_tokens[3]}")
    print(f"   Phase: {readable_tokens[4]}")
    if len(readable_tokens) > 6:
        print(f"   Team: {readable_tokens[5]} {readable_tokens[6] if len(readable_tokens) > 6 else 'None'}")
    print(f"   Turn Signal: {readable_tokens[-1]}")
    
    print("\n✅ Transformer observation format validated!")


if __name__ == "__main__":
    test_next_turn_token_ephemeral_behavior()
    test_player_identity_from_sequence()
    test_transformer_observation_format()
