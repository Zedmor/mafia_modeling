#!/usr/bin/env python3
"""Debug script to understand sequence format after our changes."""

from mafia_transformer.token_game_interface import create_token_game
from mafia_transformer.token_vocab import TokenID, TOKEN_ID_TO_NAME

# Create game and initial state
game_interface = create_token_game()
initial_state = game_interface.initialize_game(seed=42)

print("=== INITIAL STATE ===")
player_sequence = initial_state.player_chronological_sequences[0]
readable_sequence = [TOKEN_ID_TO_NAME.get(token, f'UNK_{token}') for token in player_sequence]
print('Initial sequence:', readable_sequence)

# Apply the same action from the failing test
action_tokens = [
    TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value,
    TokenID.CLAIM_SHERIFF.value,
    TokenID.END_TURN.value
]

print(f"\n=== APPLYING ACTION ===")
print(f"Action tokens: {[TOKEN_ID_TO_NAME.get(token, f'UNK_{token}') for token in action_tokens]}")

new_state = game_interface.apply_action(
    initial_state, 
    action_tokens, 
    initial_state.active_player
)

print(f"\n=== AFTER ACTION ===")
player_sequence = new_state.player_chronological_sequences[0]
readable_sequence = [TOKEN_ID_TO_NAME.get(token, f'UNK_{token}') for token in player_sequence]
print('Player sequence after action:', readable_sequence)

# Test what _get_performed_actions_this_turn returns
performed_actions = game_interface._get_performed_actions_this_turn(new_state)
print(f"\nPerformed actions found: {performed_actions}")

# Expected actions
expected_actions = {
    (TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value),
    (TokenID.CLAIM_SHERIFF.value,)
}
print(f"Expected actions: {expected_actions}")

# Debug the action sequence that was collected
print(f"\n=== DEBUG ACTION SEQUENCE PARSING ===")
# Manually replicate what the method does
player_sequence = new_state.player_chronological_sequences[0]

# Find END_TURN
for i in range(len(player_sequence) - 1, -1, -1):
    if player_sequence[i] == TokenID.END_TURN.value:
        print(f"Found END_TURN at index {i}")
        
        # Collect backwards to PLAYER_X
        action_tokens = []
        j = i - 1
        while j >= 0:
            prev_token = player_sequence[j]
            if (prev_token >= TokenID.PLAYER_0.value and 
                prev_token <= TokenID.PLAYER_9.value):
                print(f"Found PLAYER token at index {j}: {TOKEN_ID_TO_NAME.get(prev_token)}")
                break
            action_tokens.insert(0, prev_token)
            j -= 1
        
        print(f"Collected action tokens: {[TOKEN_ID_TO_NAME.get(t, f'UNK_{t}') for t in action_tokens]}")
        
        # Test parsing
        temp_sequence = action_tokens + [TokenID.END_TURN.value]
        print(f"Temp sequence for parsing: {[TOKEN_ID_TO_NAME.get(t, f'UNK_{t}') for t in temp_sequence]}")
        
        individual_actions = game_interface._parse_action_sequence(temp_sequence)
        print(f"Parsed individual actions: {individual_actions}")
        
        # Convert to readable
        readable_actions = []
        for action in individual_actions:
            readable_action = [TOKEN_ID_TO_NAME.get(t, f'UNK_{t}') for t in action]
            readable_actions.append(readable_action)
        print(f"Readable parsed actions: {readable_actions}")
        
        break

# Debug the parsing process
print(f"\n=== DEBUG PARSING ===")
print(f"Active player: {new_state.active_player}")

# Find where we are in the sequence
print("Looking for turn boundary markers...")
for i in range(len(player_sequence) - 1, -1, -1):
    token = player_sequence[i]
    if token == TokenID.END_TURN.value:
        print(f"Found END_TURN at index {i}")
    elif token in [TokenID.DAY_1.value, TokenID.DAY_2.value]:
        print(f"Found phase marker {TOKEN_ID_TO_NAME.get(token)} at index {i}")
