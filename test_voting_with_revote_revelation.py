#!/usr/bin/env python3

"""
Comprehensive test for voting privacy with proper revote revelation.

Tests the correct Mafia voting behavior:
1. During active voting: Players vote simultaneously without seeing others' votes
2. Between voting rounds: When rounds complete due to ties, all votes are revealed before next round
"""

import sys
sys.path.append('.')

from src.mafia_transformer.token_game_interface import TokenGameInterface, TokenGameState
from src.mafia_transformer.token_vocab import TokenID

def create_token_game():
    """Create a token game interface for testing."""
    return TokenGameInterface()

def test_voting_privacy_with_revote_revelation():
    """Test that votes are private during voting but revealed between rounds during ties."""
    print("=== Testing Voting Privacy with Revote Revelation ===")
    
    interface = create_token_game()
    state = interface.initialize_game(seed=42)
    
    # Go through day phase to voting
    print("1. Setting up voting phase...")
    # Complete all day turns to reach voting phase
    for player_idx in range(10):
        if player_idx < 3:
            # First 3 players nominate
            state = interface.apply_action(state, [TokenID.NOMINATE.value, TokenID.PLAYER_0.value + (player_idx+1)], player_idx)
            state = interface.apply_action(state, [TokenID.END_TURN.value], player_idx)
        else:
            # Remaining players just end turn
            state = interface.apply_action(state, [TokenID.END_TURN.value], player_idx)
    
    print(f"Current phase: {state._internal_state.current_phase.__class__.__name__}")
    print(f"Active player: {state.active_player}")
    
    # Ensure we're in voting phase
    if "Voting" not in state._internal_state.current_phase.__class__.__name__:
        print("❌ Failed to reach voting phase")
        return False
    
    # Track votes to create a tie scenario - follow voting order
    # The voting order should be from active player onwards
    first_voter = state.active_player
    print(f"First voter will be P{first_voter}")
    
    # Determine who was nominated - from our setup, it should be P1, P2, P3
    nominated_players = [1, 2, 3]  # Based on our nominations
    print(f"Nominated players: {nominated_players}")
    
    # Create a tie scenario using only nominated players
    target_p1 = nominated_players[0]  # P1
    target_p2 = nominated_players[1]  # P2
    
    print("\n2. Testing first round voting privacy...")
    
    # Vote in the proper order following active_player sequence
    votes_cast = 0
    tie_detected = False
    
    for vote_count in range(10):  # Max 10 votes
        current_voter = state.active_player
        
        # Determine vote target to create a tie: alternate between P1 and P2
        if vote_count % 2 == 0:
            target = target_p1
        else:
            target = target_p2
        
        old_p0_tokens = len(state.player_chronological_sequences[0])
        old_p1_tokens = len(state.player_chronological_sequences[1])
        
        print(f"  P{current_voter} votes for P{target}...")
        
        # Cast vote
        state = interface.apply_action(state, [TokenID.VOTE.value, TokenID.PLAYER_0.value + target], current_voter)
        
        new_p0_tokens = len(state.player_chronological_sequences[0])
        new_p1_tokens = len(state.player_chronological_sequences[1])
        
        p0_tokens_added = new_p0_tokens - old_p0_tokens
        p1_tokens_added = new_p1_tokens - old_p1_tokens
        
        # During first round, only the voting player should see vote tokens
        if current_voter == 0:
            print(f"    P0 sees {p0_tokens_added} new tokens (should be 4: PLAYER_X VOTE PLAYER_Y END_TURN)")
            assert p0_tokens_added == 4, f"P0 should see exactly 4 tokens when voting, got {p0_tokens_added}"
        else:
            print(f"    P0 sees {p0_tokens_added} new tokens (should be 0 during privacy)")
            if p0_tokens_added > 0:
                # Check if this is vote revelation (round completion)
                if p0_tokens_added > 10:  # Many tokens indicate revelation
                    print(f"    🔄 Vote revelation detected! P0 sees {p0_tokens_added} tokens")
                    tie_detected = True
                    break
                elif "Voting" not in state._internal_state.current_phase.__class__.__name__:
                    print(f"    (Voting phase ended - final vote)")
                    break
                else:
                    assert p0_tokens_added == 0, f"P0 should see 0 tokens during other players' votes, got {p0_tokens_added}"
        
        votes_cast += 1
        
        # Check if we've completed the voting round
        if state.active_player == first_voter and votes_cast > 0:  # Reset to first voter
            print(f"    🔄 Round reset detected after {votes_cast} votes - checking for vote revelation...")
            tie_detected = True
            break
    
    print("\n3. Checking for tie and vote revelation...")
    
    # After the first round completes with a tie, check if votes were revealed
    # Look at the current state to see if all first round votes are now visible
    p0_sequence = state.player_chronological_sequences[0]
    p1_sequence = state.player_chronological_sequences[1]
    
    # Count vote-related tokens in sequences
    vote_tokens_p0 = [i for i, token in enumerate(p0_sequence) if token == TokenID.VOTE.value]
    vote_tokens_p1 = [i for i, token in enumerate(p1_sequence) if token == TokenID.VOTE.value]
    
    print(f"P0 sequence has {len(vote_tokens_p0)} VOTE tokens")
    print(f"P1 sequence has {len(vote_tokens_p1)} VOTE tokens")
    
    # After a tie, players should see more than just their own vote
    expected_votes_after_revelation = 10  # All 10 players voted in round 1
    
    if len(vote_tokens_p0) >= expected_votes_after_revelation:
        print("✅ Vote revelation detected - players can see all first round votes")
        revelation_working = True
    else:
        print("❌ Vote revelation missing - players should see all first round votes after tie")
        revelation_working = False
    
    print(f"\n4. Current active player: {state.active_player}")
    print(f"   Current phase: {state._internal_state.current_phase.__class__.__name__}")
    
    return revelation_working

def test_voting_without_tie():
    """Test that votes remain private when there's no tie (normal elimination)."""
    print("\n=== Testing Voting WITHOUT Tie (No Revelation) ===")
    
    interface = create_token_game()
    state = interface.initialize_game(seed=100)  # Different seed to avoid tie
    
    # Go through day phase to voting
    for i in range(3):
        player_idx = i % 10
        state = interface.apply_action(state, [TokenID.NOMINATE.value, TokenID.PLAYER_0.value + (i+1)], player_idx)
        state = interface.apply_action(state, [TokenID.END_TURN.value], player_idx)
    
    # Cast votes that will eliminate someone clearly (no tie)
    clear_elimination_votes = [
        (9, 1),  # P9 votes for P1
        (0, 1),  # P0 votes for P1
        (1, 2),  # P1 votes for P2  
        (2, 1),  # P2 votes for P1
        (3, 1),  # P3 votes for P1
        (4, 1),  # P4 votes for P1
        (5, 1),  # P5 votes for P1
        (6, 1),  # P6 votes for P1
        (7, 1),  # P7 votes for P1
        (8, 1),  # P8 votes for P1
    ]
    # This should result in: P1=9 votes, P2=1 vote (clear winner, no tie)
    
    print("Casting votes for clear elimination...")
    for voter, target in clear_elimination_votes:
        old_p0_tokens = len(state.player_chronological_sequences[0])
        
        state = interface.apply_action(state, [TokenID.VOTE.value, TokenID.PLAYER_0.value + target], voter)
        
        new_p0_tokens = len(state.player_chronological_sequences[0])
        tokens_added = new_p0_tokens - old_p0_tokens
        
        if voter == 0:
            print(f"  P{voter} votes for P{target}: P0 sees {tokens_added} tokens (own vote)")
            assert tokens_added == 4, f"P0 should see 4 tokens when voting"
        else:
            print(f"  P{voter} votes for P{target}: P0 sees {tokens_added} tokens (privacy)")
            # During voting privacy, should see 0 tokens from other players' votes
            if tokens_added > 0:
                # Check if this is the final vote that completes the phase
                phase_name = state._internal_state.current_phase.__class__.__name__
                if "Voting" not in phase_name:
                    print(f"    (Voting phase ended - phase transition detected)")
                else:
                    assert tokens_added == 0, f"P0 should see 0 tokens during other players' votes, got {tokens_added}"
    
    # Count final vote tokens - should be minimal (only own votes, no revelation)
    p0_sequence = state.player_chronological_sequences[0]
    vote_tokens_p0 = [i for i, token in enumerate(p0_sequence) if token == TokenID.VOTE.value]
    
    print(f"After clear elimination: P0 sequence has {len(vote_tokens_p0)} VOTE tokens")
    
    # Without tie, should see fewer vote tokens (no revelation)
    if len(vote_tokens_p0) <= 2:  # Only own votes
        print("✅ No vote revelation - correct for clear elimination")
        return True
    else:
        print("❌ Unexpected vote revelation during clear elimination")
        return False

if __name__ == "__main__":
    print("🎯 Testing Voting Privacy with Revote Revelation")
    print("="*60)
    
    # Test 1: Voting with tie should trigger revelation
    revelation_works = test_voting_privacy_with_revote_revelation()
    
    # Test 2: Voting without tie should maintain privacy  
    privacy_works = test_voting_without_tie()
    
    print("\n" + "="*60)
    print("📊 SUMMARY:")
    print(f"✅ Voting privacy during active voting: WORKING")
    print(f"{'✅' if revelation_works else '❌'} Vote revelation between rounds (ties): {'WORKING' if revelation_works else 'NEEDS FIX'}")
    print(f"{'✅' if privacy_works else '❌'} Privacy maintained (no ties): {'WORKING' if privacy_works else 'NEEDS FIX'}")
    
    if revelation_works and privacy_works:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print("\n🚨 TESTS FAILED - Vote revelation needs implementation")
        exit(1)
