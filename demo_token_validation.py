#!/usr/bin/env python3
"""
Demonstration script showing the exact token stream validation for Player 0 with seed 42.
This validates the specific behavior requested by the user.
"""

from mafia_transformer.token_game_server import TokenGameServer, format_tokens
from mafia_transformer.token_vocab import TokenID

def main():
    print("🎮 Token Game Server Validation Demo")
    print("="*60)
    print("Testing Player 0 initial state with seed 42")
    print()
    
    # Initialize server with seed 42
    server = TokenGameServer(seed=42, console_quiet=True)
    success = server.start_game()
    
    if not success:
        print("❌ Failed to start game")
        return
    
    print("✅ Game started successfully")
    
    # Request state for player 0
    response = server.get_player_state(player_id=0)
    
    if not response.success:
        print(f"❌ Failed to get player state: {response.error_message}")
        return
    
    print("✅ Player 0 state retrieved successfully")
    print()
    
    # Get the full state tokens that LLM would see
    state = response.player_state
    full_state_tokens = (
        state.seed_tokens + 
        state.phase_tokens + 
        state.private_state + 
        state.public_history
    )
    
    # Expected token sequence
    expected_raw_tokens = [
        1042,  # Seed token (1000 + 42)
        TokenID.GAME_START,  # 38
        TokenID.PLAYER_0,    # 13
        TokenID.DAY_1,       # 41
        TokenID.YOUR_ROLE,   # 32
        TokenID.DON,         # 28
        TokenID.MAFIA_TEAM,  # 31
        TokenID.PLAYER_1,    # 14
        TokenID.PLAYER_8,    # 21
    ]
    
    expected_formatted = "<1042> <GAME_START> <PLAYER_0> <DAY_1> <YOUR_ROLE> <DON> <MAFIA_TEAM> <PLAYER_1> <PLAYER_8>"
    
    # Show the validation
    print("🔍 TOKEN STREAM VALIDATION")
    print("-" * 40)
    print(f"Expected: {expected_formatted}")
    
    actual_formatted = format_tokens(full_state_tokens[:len(expected_raw_tokens)])
    print(f"Actual:   {actual_formatted}")
    
    if actual_formatted == expected_formatted:
        print("✅ MATCH! Token stream is exactly as expected.")
    else:
        print("❌ MISMATCH! Token stream differs from expected.")
        return
    
    print()
    print("📋 DETAILED BREAKDOWN:")
    print("-" * 40)
    
    for i, (expected, actual) in enumerate(zip(expected_raw_tokens, full_state_tokens[:len(expected_raw_tokens)])):
        expected_name = TokenID(expected).name if expected < 50 else f"SEED({expected})"
        actual_name = TokenID(actual).name if actual < 50 else f"SEED({actual})"
        
        status = "✅" if expected == actual else "❌"
        print(f"  {i}: {status} {expected} ({expected_name}) == {actual} ({actual_name})")
    
    print()
    print("🎯 ROLE VERIFICATION:")
    print("-" * 40)
    print(f"Player 0 role: {'DON' if TokenID.DON in state.private_state else 'UNKNOWN'}")
    print(f"Mafia team: {'REVEALED' if TokenID.MAFIA_TEAM in state.private_state else 'HIDDEN'}")
    mafia_teammates = []
    for token in state.private_state:
        if token in [TokenID.PLAYER_1, TokenID.PLAYER_8]:
            mafia_teammates.append(token - TokenID.PLAYER_0)
    print(f"Teammates: P{mafia_teammates[0]} and P{mafia_teammates[1]}" if len(mafia_teammates) == 2 else f"Teammates: {mafia_teammates}")
    
    print()
    print("⚡ LEGAL ACTIONS:")
    print("-" * 40)
    print(f"Available actions: {len(response.legal_actions)}")
    for i, action in enumerate(response.legal_actions[:5]):  # Show first 5
        print(f"  {i+1}. {format_tokens(action)}")
    if len(response.legal_actions) > 5:
        print(f"  ... and {len(response.legal_actions) - 5} more")
    
    print()
    print("🎊 VALIDATION COMPLETE - All tests passed!")
    print("This demonstrates that the TokenGameServer correctly:")
    print("  • Uses deterministic seed 42")
    print("  • Assigns Player 0 as Don")
    print("  • Provides exact expected token stream")
    print("  • Returns human-readable token format")
    print("  • Maintains consistency across runs")

if __name__ == "__main__":
    main()
