#!/usr/bin/env python3
"""
Test script to validate day vs night action handling.
"""

from src.mafia_transformer.token_game_interface import TokenGameInterface
from src.mafia_transformer.token_vocab import TokenID

def test_day_action_acceptance():
    """Test that day multi-actions are accepted."""
    interface = TokenGameInterface()
    
    # Initialize game
    token_state = interface.initialize_game(seed=42)
    
    print("🎮 Testing Day Action Validation")
    print(f"Current phase: DAY_1")
    print(f"Active player: {token_state.active_player}")
    
    # Test multi-action day sequence
    day_multi_action = [
        TokenID.SAY.value, TokenID.PLAYER_1.value, TokenID.RED.value,
        TokenID.NOMINATE.value, TokenID.PLAYER_2.value, 
        TokenID.END_TURN.value
    ]
    
    print(f"🔄 Attempting day multi-action: SAY PLAYER_1 RED + NOMINATE PLAYER_2 + END_TURN")
    
    try:
        new_state = interface.apply_action(token_state, day_multi_action, token_state.active_player)
        print("✅ Day multi-action ACCEPTED")
        print(f"New active player: {new_state.active_player}")
        return True
    except ValueError as e:
        print(f"❌ Day multi-action REJECTED: {e}")
        return False

def test_night_action_rejection():
    """Test that night multi-actions are rejected."""
    interface = TokenGameInterface()
    
    # Create a game state in night phase
    token_state = interface.initialize_game(seed=42)
    
    # Fast-forward to night phase by simulating day completion
    # Apply actions to get all players through day phase
    current_state = token_state
    
    # Have all players end their turns to get to night
    for player in range(10):
        if current_state.active_player != player:
            continue
        try:
            current_state = interface.apply_action(
                current_state, 
                [TokenID.END_TURN.value], 
                current_state.active_player
            )
        except:
            break
        
        # Check if we're in night phase
        phase_name = current_state._internal_state.current_phase.__class__.__name__
        if "Night" in phase_name:
            break
    
    phase_name = current_state._internal_state.current_phase.__class__.__name__
    print(f"\n🌙 Testing Night Action Validation")
    print(f"Current phase: {phase_name}")
    print(f"Active player: {current_state.active_player}")
    
    # Test multi-action night sequence (should be rejected)
    night_multi_action = [
        TokenID.DON_CHECK.value, TokenID.PLAYER_1.value,
        TokenID.DON_CHECK.value, TokenID.PLAYER_2.value,
        TokenID.END_TURN.value
    ]
    
    print(f"🔄 Attempting night multi-action: DON_CHECK PLAYER_1 + DON_CHECK PLAYER_2 + END_TURN")
    
    try:
        interface.apply_action(current_state, night_multi_action, current_state.active_player)
        print("❌ Night multi-action ACCEPTED (should be rejected)")
        return False
    except ValueError as e:
        print(f"✅ Night multi-action REJECTED: {e}")
        return True

def main():
    """Run validation tests."""
    print("="*60)
    print("Day vs Night Action Validation Test")
    print("="*60)
    
    day_ok = test_day_action_acceptance()
    night_ok = test_night_action_rejection()
    
    print("\n" + "="*60)
    print("Summary:")
    print(f"✅ Day multi-actions work: {day_ok}")
    print(f"✅ Night multi-actions rejected: {night_ok}")
    
    if day_ok and night_ok:
        print("🎉 All validation tests PASSED")
        return True
    else:
        print("❌ Some validation tests FAILED")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
