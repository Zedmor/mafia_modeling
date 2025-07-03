"""
Unit test to demonstrate and validate the end turn context bug.

The issue: When a player starts their turn and immediately ends it without taking
any actions, subsequent players don't see that the previous player took their turn.
This breaks game context understanding.

Expected behavior: All players should see the complete sequence of who took turns,
even if they only ended their turn without other actions.
"""

import pytest
from src.mafia_transformer.token_game_server import TokenGameServer
from src.mafia_transformer.token_vocab import TokenID


def test_end_turn_context_preserved():
    """
    Test that when a player ends their turn without other actions,
    subsequent players can see that the previous player took their turn.
    """
    # Initialize game server
    server = TokenGameServer(seed=42)
    
    # Start the game
    server.start_game()
    initial_response = server.get_player_state(0)
    
    # Verify Player 0 starts the game
    assert initial_response.success
    assert initial_response.player_state is not None
    assert initial_response.player_state.is_active
    
    # Player 0 immediately ends their turn (like in the bug report)
    action_response = server.apply_player_action(0, [TokenID.END_TURN.value])
    assert action_response.success
    
    # Get Player 1's view of the game state
    player_1_response = server.get_player_state(1)
    
    # Expected: Player 1 should see that Player 0 took their turn and ended it
    assert player_1_response.success
    assert player_1_response.player_state is not None
    
    # Use get_observation_tokens to get the full token sequence including ephemeral NEXT_TURN
    from src.mafia_transformer.token_game_interface import create_token_game
    interface = create_token_game()
    # Create a token state from the server response
    token_state = server.current_state
    tokens = interface.get_observation_tokens(token_state, 1)
    
    # Find the sequence after DAY_1
    day_1_index = None
    for i, token in enumerate(tokens):
        if token == TokenID.DAY_1.value:
            day_1_index = i
            break
    
    assert day_1_index is not None, "DAY_1 token not found"
    
    # The sequence after DAY_1 should be: <DAY_PHASE_START> <PLAYER_0> <END_TURN> <PLAYER_1> <YOUR_TURN> <NEXT_TURN>
    # Note: DAY_PHASE_START (53) then PLAYER_0 (13) END_TURN (0) PLAYER_1 (14) YOUR_TURN (54) NEXT_TURN (55)
    # YOUR_TURN is now stored in chronological sequences for training, NEXT_TURN is added ephemerally
    expected_sequence = [TokenID.DAY_PHASE_START.value, TokenID.PLAYER_0.value, TokenID.END_TURN.value, TokenID.PLAYER_1.value, TokenID.YOUR_TURN.value, TokenID.NEXT_TURN.value]
    actual_sequence = tokens[day_1_index + 1:day_1_index + 1 + len(expected_sequence)]
    
    assert actual_sequence == expected_sequence, (
        f"Expected sequence after DAY_1: {expected_sequence}, "
        f"but got: {actual_sequence}. "
        f"Full token sequence: {tokens[day_1_index:day_1_index + 10]}"
    )


def test_end_turn_context_with_multiple_players():
    """
    Test that end turn context is preserved across multiple players
    when some players take actions and others just end their turn.
    """
    server = TokenGameServer(seed=123)
    server.start_game()
    
    # Player 0 takes an action then ends turn
    server.apply_player_action(0, [TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value, TokenID.END_TURN.value])
    
    # Player 1 just ends turn without any action
    server.apply_player_action(1, [TokenID.END_TURN.value])
    
    # Player 2 takes an action then ends turn
    server.apply_player_action(2, [TokenID.NOMINATE.value, TokenID.PLAYER_3.value, TokenID.END_TURN.value])
    
    # Get Player 3's view
    player_3_response = server.get_player_state(3)
    assert player_3_response.success
    tokens = player_3_response.player_state.chronological_history
    
    # Find DAY_1 sequence
    day_1_index = None
    for i, token in enumerate(tokens):
        if token == TokenID.DAY_1:
            day_1_index = i
            break
    
    assert day_1_index is not None
    
    # Expected sequence should show all player turns including Player 1's END_TURN
    # Look for the pattern where Player 1 appears followed by END_TURN
    found_player_1_end_turn = False
    for i in range(day_1_index, len(tokens) - 1):
        if (tokens[i] == TokenID.PLAYER_1.value and 
            i + 1 < len(tokens) and 
            tokens[i + 1] == TokenID.END_TURN.value):
            found_player_1_end_turn = True
            break
    
    assert found_player_1_end_turn, (
        f"Player 1's END_TURN not found in sequence. "
        f"Tokens around DAY_1: {tokens[day_1_index:day_1_index + 20]}"
    )


def test_readable_format_shows_end_turn():
    """
    Test that the readable format also shows when players end their turn
    without taking other actions.
    """
    server = TokenGameServer(seed=456)
    server.start_game()
    
    # Player 0 just ends turn
    server.apply_player_action(0, [TokenID.END_TURN.value])
    
    # Get Player 1's view and use the interface to get readable format
    player_1_response = server.get_player_state(1)
    assert player_1_response.success
    
    # Use the server's format_tokens_readable function to get readable format
    from src.mafia_transformer.token_game_server import format_tokens_readable
    readable = format_tokens_readable(player_1_response.player_state.chronological_history)
    
    # The readable format should mention Player 0's turn
    assert "Player 0:" in readable, f"Player 0 turn not mentioned in readable format: {readable}"
    assert "END_TURN" in readable, f"END_TURN not shown in readable format: {readable}"


if __name__ == "__main__":
    test_end_turn_context_preserved()
    test_end_turn_context_with_multiple_players() 
    test_readable_format_shows_end_turn()
    print("All tests passed!")
