"""
Unit tests to confirm the voting progression and privacy issues.

This test file will verify:
1. That voting progresses correctly from player to player
2. That players only see their own votes during active voting
3. That vote revelation works when rounds complete
4. That the YOUR_TURN token appears for the correct player after voting
"""

import pytest
from src.mafia_transformer.token_game_interface import TokenGameInterface
from src.mafia_transformer.token_vocab import TokenID


def test_voting_progression_first_player():
    """Test that voting progresses correctly from first player to next."""
    
    # Initialize game with seed 42 (known configuration)
    interface = TokenGameInterface()
    token_state = interface.initialize_game(seed=42, num_players=10)
    
    # Fast-forward to voting phase by simulating day phase
    # Player 0 (DON), Player 1 (MAFIA), Player 8 (MAFIA), Player 2 (SHERIFF), others Citizens
    
    # Simulate day phase with some nominations to reach voting phase
    for player_idx in range(10):
        if token_state.active_player != player_idx:
            continue
            
        # Have some players nominate others to trigger voting phase
        if player_idx < 3:  # First 3 players nominate someone
            nomination_target = (player_idx + 1) % 10
            action_tokens = [TokenID.NOMINATE.value, TokenID.PLAYER_0.value + nomination_target, TokenID.END_TURN.value]
        else:
            # Other players just end their turn
            action_tokens = [TokenID.END_TURN.value]
            
        token_state = interface.apply_action(token_state, action_tokens, player_idx)
        
        # Break when we reach voting phase
        if interface._is_voting_phase(token_state._internal_state):
            break
    
    # Verify we're in voting phase
    assert interface._is_voting_phase(token_state._internal_state), "Should be in voting phase"
    
    # Get the active player at start of voting
    first_voting_player = token_state.active_player
    print(f"First voting player: {first_voting_player}")
    
    # First player votes for a nominated player
    vote_action = [TokenID.VOTE.value, TokenID.PLAYER_0.value + 1]  # Vote for Player 1 (nominated)
    token_state_after_vote = interface.apply_action(token_state, vote_action, first_voting_player)
    
    # CRITICAL TEST: Active player should change to next player after voting
    next_expected_player = (first_voting_player + 1) % 10
    
    # Skip dead players if any
    while (next_expected_player != first_voting_player and 
           not token_state_after_vote._internal_state.game_states[next_expected_player].alive):
        next_expected_player = (next_expected_player + 1) % 10
    
    print(f"Expected next player: {next_expected_player}")
    print(f"Actual active player after vote: {token_state_after_vote.active_player}")
    
    # This should PASS if voting progression works correctly
    assert token_state_after_vote.active_player == next_expected_player, \
        f"Voting should progress to next player. Expected {next_expected_player}, got {token_state_after_vote.active_player}"


def test_voting_privacy_during_active_voting():
    """Test that players only see their own votes during active voting."""
    
    interface = TokenGameInterface()
    token_state = interface.initialize_game(seed=42, num_players=10)
    
    # Fast-forward to voting phase with nominations
    for player_idx in range(10):
        if token_state.active_player != player_idx:
            continue
            
        # Have some players nominate others to trigger voting phase
        if player_idx < 3:  # First 3 players nominate someone
            nomination_target = (player_idx + 1) % 10
            action_tokens = [TokenID.NOMINATE.value, TokenID.PLAYER_0.value + nomination_target, TokenID.END_TURN.value]
        else:
            # Other players just end their turn
            action_tokens = [TokenID.END_TURN.value]
            
        token_state = interface.apply_action(token_state, action_tokens, player_idx)
        
        if interface._is_voting_phase(token_state._internal_state):
            break
    
    # Get voting player and another player to check
    voting_player = token_state.active_player
    other_player = (voting_player + 1) % 10
    
    # Get sequences before vote
    voting_player_seq_before = token_state.player_chronological_sequences[voting_player].copy()
    other_player_seq_before = token_state.player_chronological_sequences[other_player].copy()
    
    # Voting player votes for a nominated player
    vote_action = [TokenID.VOTE.value, TokenID.PLAYER_0.value + 1]  # Vote for Player 1 (nominated)
    token_state_after = interface.apply_action(token_state, vote_action, voting_player)
    
    # Get sequences after vote
    voting_player_seq_after = token_state_after.player_chronological_sequences[voting_player]
    other_player_seq_after = token_state_after.player_chronological_sequences[other_player]
    
    # Check that voting player sees their own vote
    new_tokens_voting_player = voting_player_seq_after[len(voting_player_seq_before):]
    print(f"Voting player {voting_player} new tokens: {new_tokens_voting_player}")
    
    # Should contain the vote tokens
    assert TokenID.VOTE.value in new_tokens_voting_player, \
        "Voting player should see their own vote"
    
    # Check that other player does NOT see the vote (privacy during active voting)
    new_tokens_other_player = other_player_seq_after[len(other_player_seq_before):]
    print(f"Other player {other_player} new tokens: {new_tokens_other_player}")
    
    # Should NOT contain vote tokens during active voting
    assert TokenID.VOTE.value not in new_tokens_other_player, \
        "Other players should NOT see votes during active voting (privacy rule)"


def test_your_turn_token_placement():
    """Test that YOUR_TURN appears for the correct player after voting."""
    
    interface = TokenGameInterface()
    token_state = interface.initialize_game(seed=42, num_players=10)
    
    # Fast-forward to voting phase with nominations
    for player_idx in range(10):
        if token_state.active_player != player_idx:
            continue
            
        # Have some players nominate others to trigger voting phase
        if player_idx < 3:  # First 3 players nominate someone
            nomination_target = (player_idx + 1) % 10
            action_tokens = [TokenID.NOMINATE.value, TokenID.PLAYER_0.value + nomination_target, TokenID.END_TURN.value]
        else:
            # Other players just end their turn
            action_tokens = [TokenID.END_TURN.value]
            
        token_state = interface.apply_action(token_state, action_tokens, player_idx)
        
        if interface._is_voting_phase(token_state._internal_state):
            break
    
    voting_player = token_state.active_player
    vote_action = [TokenID.VOTE.value, TokenID.PLAYER_0.value + 1]  # Vote for Player 1 (nominated)
    token_state_after = interface.apply_action(token_state, vote_action, voting_player)
    
    # Check YOUR_TURN placement in observation tokens
    for player_idx in range(10):
        observation_tokens = interface.get_observation_tokens(token_state_after, player_idx)
        has_your_turn = TokenID.YOUR_TURN.value in observation_tokens
        is_active = (player_idx == token_state_after.active_player)
        
        print(f"Player {player_idx}: active={is_active}, has_YOUR_TURN={has_your_turn}")
        
        if is_active:
            assert has_your_turn, f"Active player {player_idx} should have YOUR_TURN token"
        else:
            assert not has_your_turn, f"Inactive player {player_idx} should NOT have YOUR_TURN token"


def test_vote_revelation_when_round_completes():
    """Test that votes are revealed when a voting round completes (if implemented)."""
    
    interface = TokenGameInterface()
    token_state = interface.initialize_game(seed=42, num_players=10)
    
    # Fast-forward to voting phase with nominations
    for player_idx in range(10):
        if token_state.active_player != player_idx:
            continue
            
        # Have some players nominate others to trigger voting phase
        if player_idx < 3:  # First 3 players nominate someone
            nomination_target = (player_idx + 1) % 10
            action_tokens = [TokenID.NOMINATE.value, TokenID.PLAYER_0.value + nomination_target, TokenID.END_TURN.value]
        else:
            # Other players just end their turn
            action_tokens = [TokenID.END_TURN.value]
            
        token_state = interface.apply_action(token_state, action_tokens, player_idx)
        
        if interface._is_voting_phase(token_state._internal_state):
            break
    
    # Collect initial sequences to track changes
    initial_sequences = [seq.copy() for seq in token_state.player_chronological_sequences]
    
    # Have all players vote to complete a round
    current_state = token_state
    votes_cast = []
    
    for vote_num in range(10):  # Max 10 votes for 10 players
        if not interface._is_voting_phase(current_state._internal_state):
            break
            
        voting_player = current_state.active_player
        # Vote for one of the nominated players (P1, P2, P3)
        nominated_players = [1, 2, 3]
        vote_target = nominated_players[vote_num % len(nominated_players)]
        vote_action = [TokenID.VOTE.value, TokenID.PLAYER_0.value + vote_target]
        
        votes_cast.append((voting_player, vote_target))
        print(f"Vote {vote_num + 1}: Player {voting_player} votes for Player {vote_target}")
        
        current_state = interface.apply_action(current_state, vote_action, voting_player)
        
        # Check if this completed a voting round
        if vote_num >= 9:  # After all players have voted
            # Check if any player sequences now contain vote revelation
            for player_idx in range(10):
                final_seq = current_state.player_chronological_sequences[player_idx]
                initial_seq = initial_sequences[player_idx]
                new_tokens = final_seq[len(initial_seq):]
                
                # Count vote tokens in new tokens (should include other players' votes if revealed)
                vote_token_count = new_tokens.count(TokenID.VOTE.value)
                print(f"Player {player_idx} sees {vote_token_count} vote tokens total")
                
                # If vote revelation is working, players should see more than just their own vote
                # This test will show us the current behavior
    
    print(f"Total votes cast: {len(votes_cast)}")
    print(f"Final voting phase: {interface._is_voting_phase(current_state._internal_state)}")


if __name__ == "__main__":
    print("=== Testing Voting Progression Issue ===")
    
    print("\n1. Testing voting progression...")
    try:
        test_voting_progression_first_player()
        print("✅ Voting progression test PASSED")
    except AssertionError as e:
        print(f"❌ Voting progression test FAILED: {e}")
    except Exception as e:
        print(f"💥 Voting progression test ERROR: {e}")
    
    print("\n2. Testing voting privacy...")
    try:
        test_voting_privacy_during_active_voting()
        print("✅ Voting privacy test PASSED")
    except AssertionError as e:
        print(f"❌ Voting privacy test FAILED: {e}")
    except Exception as e:
        print(f"💥 Voting privacy test ERROR: {e}")
    
    print("\n3. Testing YOUR_TURN token placement...")
    try:
        test_your_turn_token_placement()
        print("✅ YOUR_TURN placement test PASSED")
    except AssertionError as e:
        print(f"❌ YOUR_TURN placement test FAILED: {e}")
    except Exception as e:
        print(f"💥 YOUR_TURN placement test ERROR: {e}")
    
    print("\n4. Testing vote revelation...")
    try:
        test_vote_revelation_when_round_completes()
        print("✅ Vote revelation test COMPLETED (check output)")
    except Exception as e:
        print(f"💥 Vote revelation test ERROR: {e}")
