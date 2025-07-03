#!/usr/bin/env python3
"""
Test script to validate nomination limit enforcement.
"""

from src.mafia_transformer.token_game_interface import TokenGameInterface
from src.mafia_transformer.token_vocab import TokenID
from src.mafia_transformer.token_random_agent import TokenRandomAgent

def test_server_rejects_multiple_nominations():
    """Test that the server properly rejects sequences with multiple nominations."""
    interface = TokenGameInterface()
    
    # Initialize game
    token_state = interface.initialize_game(seed=42)
    
    print("🛡️  Testing Server Rejection of Multiple Nominations")
    print(f"Current phase: DAY_1")
    print(f"Active player: {token_state.active_player}")
    
    # Test sequence with multiple nominations (should be rejected)
    multi_nomination_sequence = [
        TokenID.NOMINATE.value, TokenID.PLAYER_1.value,
        TokenID.NOMINATE.value, TokenID.PLAYER_2.value, 
        TokenID.END_TURN.value
    ]
    
    print(f"🔄 Attempting multi-nomination sequence: NOMINATE PLAYER_1 + NOMINATE PLAYER_2 + END_TURN")
    
    try:
        interface.apply_action(token_state, multi_nomination_sequence, token_state.active_player)
        print("❌ Multi-nomination sequence ACCEPTED (should be rejected)")
        return False
    except ValueError as e:
        print(f"✅ Multi-nomination sequence REJECTED: {e}")
        return True

def test_agent_doesnt_generate_multiple_nominations():
    """Test that our random agent doesn't generate multiple nominations."""
    interface = TokenGameInterface()
    
    # Initialize game
    token_state = interface.initialize_game(seed=42)
    
    print(f"\n🤖 Testing Random Agent Nomination Generation")
    print(f"Active player: {token_state.active_player}")
    
    # Create a random agent for the active player
    agent = TokenRandomAgent(token_state._internal_state, log_file_path=None)
    
    # Generate 50 sequences and check for multiple nominations
    multi_nomination_found = False
    sequences_tested = 0
    
    for i in range(50):
        try:
            action = agent.get_action(token_state.active_player)
            sequences_tested += 1
            
            # Check if this is a token sequence (day phase)
            if isinstance(action, list):
                # Count nominations in the sequence
                nomination_count = 0
                j = 0
                while j < len(action):
                    if action[j] == TokenID.NOMINATE.value:
                        nomination_count += 1
                    j += 1
                
                if nomination_count > 1:
                    print(f"❌ FOUND MULTI-NOMINATION in sequence {i+1}: {nomination_count} nominations")
                    print(f"   Sequence: {action}")
                    multi_nomination_found = True
                    break
                elif nomination_count == 1:
                    print(f"✅ Sequence {i+1}: 1 nomination (valid)")
                else:
                    print(f"✅ Sequence {i+1}: 0 nominations (valid)")
        except Exception as e:
            print(f"⚠️  Error in sequence {i+1}: {e}")
    
    print(f"\n📊 Agent Test Results:")
    print(f"   Sequences tested: {sequences_tested}")
    print(f"   Multi-nominations found: {'YES' if multi_nomination_found else 'NO'}")
    
    return not multi_nomination_found

def test_legal_actions_dont_include_multiple_nominations():
    """Test that legal actions from the interface don't include multiple nominations."""
    interface = TokenGameInterface()
    
    # Initialize game
    token_state = interface.initialize_game(seed=42)
    
    print(f"\n⚖️  Testing Legal Actions for Nomination Limits")
    
    # Get legal actions from the interface
    legal_actions = interface.get_legal_actions(token_state)
    
    print(f"   Total legal actions: {len(legal_actions)}")
    
    multi_nomination_actions = 0
    for i, action_sequence in enumerate(legal_actions):
        # Count nominations in each sequence
        nomination_count = 0
        j = 0
        while j < len(action_sequence):
            if action_sequence[j] == TokenID.NOMINATE.value:
                nomination_count += 1
            j += 1
        
        if nomination_count > 1:
            multi_nomination_actions += 1
            print(f"❌ Legal action {i+1} has {nomination_count} nominations: {action_sequence}")
    
    print(f"   Legal actions with multiple nominations: {multi_nomination_actions}")
    
    return multi_nomination_actions == 0

def main():
    """Run nomination limit validation tests."""
    print("="*60)
    print("Nomination Limit Validation Test")
    print("="*60)
    
    server_ok = test_server_rejects_multiple_nominations()
    agent_ok = test_agent_doesnt_generate_multiple_nominations()
    legal_ok = test_legal_actions_dont_include_multiple_nominations()
    
    print("\n" + "="*60)
    print("Summary:")
    print(f"✅ Server rejects multi-nominations: {server_ok}")
    print(f"✅ Agent doesn't generate multi-nominations: {agent_ok}")
    print(f"✅ Legal actions don't include multi-nominations: {legal_ok}")
    
    if server_ok and agent_ok and legal_ok:
        print("🎉 All nomination limit tests PASSED")
        return True
    else:
        print("❌ Some nomination limit tests FAILED")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
