import sys
import pytest
import random
import json
from pathlib import Path

from mafia_transformer.token_game_server import TokenGameServer, format_tokens
from mafia_transformer.token_vocab import TokenID, TOKEN_ID_TO_NAME


def test_end_turn_token_consistency_validation():
    """
    Test that all actions properly end with END_TURN tokens after the bugfix.
    
    This test validates the fix for missing END_TURN tokens after actions,
    specifically focusing on night phase moves and vote moves that were
    previously missing END_TURN tokens.
    
    Uses the same pattern as test_seed_42_random_557_scenario.py but with
    specific END_TURN validation to prevent regressions.
    """
    seed = 42
    random_seed = 557
    log_dir = Path(__file__).parent / 'logs' / 'end_turn_validation'
    log_dir.mkdir(parents=True, exist_ok=True)

    # Initialize server with the specific seed for reproducibility
    server = TokenGameServer(
        seed=seed, 
        console_quiet=True, 
        traffic_log_dir=str(log_dir)
    )
    server.start_game()

    # Import and use random agent for realistic game simulation
    from mafia_transformer.token_random_agent import TokenRandomAgent
    
    # Set the random seed to match the scenario
    random.seed(random_seed)
    
    max_rounds = 50  # Enough rounds to see night and voting phases
    end_turn_violations = []  # Track any END_TURN violations found
    action_sequences = []  # Track all action sequences for analysis
    
    for round_num in range(max_rounds):
        stats = server.get_game_stats()
        
        # Check if game finished
        if stats['game_finished']:
            print(f"Game finished successfully after {round_num} rounds")
            break
            
        active_player = stats['active_player']
        if active_player is not None:
            try:
                # Get player state and create random agent
                player_state_response = server.get_player_state(active_player)
                if player_state_response.success and player_state_response.player_state.is_active:
                    # Create a random agent for this turn - use the internal state
                    game_state = server.token_interface.current_state._internal_state
                    agent = TokenRandomAgent(game_state)
                    action = agent.get_action(active_player)
                    
                    # CRITICAL: Validate the action sequence before applying
                    if isinstance(action, list) and action:
                        action_sequences.append({
                            'round': round_num,
                            'player': active_player,
                            'action': action.copy(),
                            'phase': _get_current_phase_name(game_state)
                        })
                        
                        # Check for END_TURN consistency based on action type
                        violation = _validate_end_turn_consistency(action, active_player, game_state)
                        if violation:
                            end_turn_violations.append({
                                'round': round_num,
                                'player': active_player,
                                'action': action.copy(),
                                'violation': violation,
                                'phase': _get_current_phase_name(game_state)
                            })
                    
                    # Apply the action
                    if isinstance(action, list):
                        server.apply_player_action(active_player, action)
                    else:
                        # If not a token sequence, just end turn
                        server.apply_player_action(active_player, [TokenID.END_TURN.value])
                        
                else:
                    # Player not active, skip
                    continue
            except Exception as e:
                print(f"Error in player {active_player} turn: {e}")
                # Force end turn on error
                server.apply_player_action(active_player, [TokenID.END_TURN.value])
        else:
            print(f"No active player at round {round_num}, game may have ended")
            break
    else:
        # Loop exhausted without finishing - acceptable for this test
        print(f"Game did not finish within {max_rounds} rounds, but test completed")
    
    # CRITICAL VALIDATION: Check for END_TURN violations
    print(f"\n=== END_TURN VALIDATION RESULTS ===")
    print(f"Total action sequences analyzed: {len(action_sequences)}")
    print(f"END_TURN violations found: {len(end_turn_violations)}")
    
    if end_turn_violations:
        print("\n🚨 END_TURN VIOLATIONS DETECTED:")
        for violation in end_turn_violations[:10]:  # Show first 10 violations
            action_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in violation['action']]
            print(f"  Round {violation['round']}, Player {violation['player']}, "
                  f"Phase: {violation['phase']}")
            print(f"    Action: {' '.join(action_names)}")
            print(f"    Violation: {violation['violation']}")
    
    # Generate summary report
    phase_stats = _analyze_action_sequences_by_phase(action_sequences)
    print(f"\n=== PHASE-WISE ACTION ANALYSIS ===")
    for phase_name, stats in phase_stats.items():
        print(f"{phase_name}: {stats['total']} actions, "
              f"{stats['with_end_turn']} with END_TURN ({stats['percentage']:.1f}%)")
    
    # ASSERT: No END_TURN violations should be found after the bugfix
    assert len(end_turn_violations) == 0, (
        f"Found {len(end_turn_violations)} END_TURN violations after bugfix. "
        f"First violation: {end_turn_violations[0] if end_turn_violations else 'None'}"
    )
    
    final_stats = server.get_game_stats()
    print(f"Final game stats: {final_stats}")
    
    # Ensure the test completed successfully
    assert final_stats is not None, "Should be able to get game stats"
    print("✅ END_TURN validation test completed successfully - no violations found!")


def _get_current_phase_name(game_state) -> str:
    """Get the current phase name for logging."""
    try:
        if hasattr(game_state, '_internal_state') and game_state._internal_state:
            phase_name = game_state._internal_state.current_phase.__class__.__name__
        elif hasattr(game_state, 'current_phase'):
            phase_name = game_state.current_phase.__class__.__name__
        else:
            phase_name = "Unknown"
        return phase_name
    except:
        return "Unknown"


def _validate_end_turn_consistency(action: list, player_id: int, game_state) -> str:
    """
    Validate that action sequences have consistent END_TURN handling.
    
    Returns:
        Empty string if valid, violation description if invalid
    """
    if not action:
        return "Empty action sequence"
    
    phase_name = _get_current_phase_name(game_state)
    has_end_turn = action and action[-1] == TokenID.END_TURN.value
    
    # Determine action type
    action_type = action[0] if action else None
    is_night_action = action_type in [TokenID.KILL.value, TokenID.SHERIFF_CHECK.value, TokenID.DON_CHECK.value]
    is_vote_action = action_type == TokenID.VOTE.value
    is_day_action = action_type in [TokenID.SAY.value, TokenID.NOMINATE.value, TokenID.CLAIM_SHERIFF_CHECK.value, 
                                   TokenID.CLAIM_SHERIFF.value, TokenID.DENY_SHERIFF.value]
    is_standalone_end_turn = action == [TokenID.END_TURN.value]
    
    # CRITICAL VALIDATION RULES based on the bugfix requirements:
    
    # 1. Night actions must ALWAYS end with END_TURN
    if is_night_action and not has_end_turn:
        action_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in action]
        return f"Night action missing END_TURN: {' '.join(action_names)}"
    
    # 2. Vote actions must ALWAYS end with END_TURN  
    if is_vote_action and not has_end_turn:
        action_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in action]
        return f"Vote action missing END_TURN: {' '.join(action_names)}"
    
    # 3. Multi-action day sequences must end with END_TURN
    if _is_multi_action_day_sequence(action) and not has_end_turn:
        action_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in action]
        return f"Multi-action day sequence missing END_TURN: {' '.join(action_names)}"
    
    # 4. Single day actions can optionally have END_TURN (both patterns are valid)
    # No validation needed for single day actions
    
    # 5. Standalone END_TURN is always valid
    # No validation needed
    
    return ""  # Valid action sequence


def _is_multi_action_day_sequence(action: list) -> bool:
    """Check if this is a multi-action day sequence (more than one action before potential END_TURN)."""
    if not action:
        return False
    
    # Parse the action to count individual actions
    action_verbs = [TokenID.SAY.value, TokenID.NOMINATE.value, TokenID.CLAIM_SHERIFF_CHECK.value,
                   TokenID.CLAIM_SHERIFF.value, TokenID.DENY_SHERIFF.value, TokenID.KILL.value,
                   TokenID.SHERIFF_CHECK.value, TokenID.DON_CHECK.value, TokenID.VOTE.value,
                   TokenID.VOTE_ELIMINATE_ALL.value, TokenID.VOTE_KEEP_ALL.value, TokenID.END_TURN.value]
    
    verb_count = 0
    for token in action:
        if token in action_verbs:
            verb_count += 1
    
    # If we have more than 2 verbs (excluding potential END_TURN), it's multi-action
    # Or if we have exactly 2 verbs and the last one isn't END_TURN
    if verb_count > 2:
        return True
    elif verb_count == 2 and action[-1] != TokenID.END_TURN.value:
        return True
    
    return False


def _analyze_action_sequences_by_phase(action_sequences: list) -> dict:
    """Analyze action sequences grouped by phase."""
    phase_stats = {}
    
    for seq in action_sequences:
        phase = seq['phase']
        action = seq['action']
        
        if phase not in phase_stats:
            phase_stats[phase] = {'total': 0, 'with_end_turn': 0, 'percentage': 0.0}
        
        phase_stats[phase]['total'] += 1
        
        if action and action[-1] == TokenID.END_TURN.value:
            phase_stats[phase]['with_end_turn'] += 1
    
    # Calculate percentages
    for phase, stats in phase_stats.items():
        if stats['total'] > 0:
            stats['percentage'] = (stats['with_end_turn'] / stats['total']) * 100.0
    
    return phase_stats


if __name__ == '__main__':
    pytest.main([__file__])
