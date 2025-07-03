"""
Tests for vote revelation fix (Task 1.2)

This test suite verifies that vote revelation works correctly after voting rounds
complete with ties, ensuring proper implementation of:
1. Vote privacy during voting
2. Vote revelation after round completion  
3. REVOTE_PHASE token emission
4. Proper vote extraction from game engine
"""

import pytest
from src.mafia_transformer.token_game_interface import TokenGameInterface, create_token_game
from src.mafia_transformer.token_vocab import TokenID, TOKEN_ID_TO_NAME


class TestVoteRevelationFix:
    """Test vote revelation after voting round completion with ties."""
    
    def setup_method(self):
        """Set up test environment."""
        self.game = create_token_game()
        
    def test_vote_privacy_during_voting(self):
        """
        Test that votes remain private during voting phase.
        
        Verifies that while players are voting, other players cannot see their votes.
        This ensures simultaneous voting mechanics work correctly.
        """
        try:
            # Initialize game with seed 42 to get deterministic behavior
            token_state = self.game.initialize_game(seed=42)
            
            # Fast-forward to voting phase by ending all day turns
            voting_state = self._advance_to_voting_phase(token_state)
            
            # Have P0 vote for P1
            vote_action = [TokenID.VOTE.value, TokenID.PLAYER_1.value, TokenID.END_TURN.value]
            voting_state = self.game.apply_action(voting_state, vote_action, 0)
            
            # Check that other players (P1, P2, etc.) cannot see P0's vote
            for player_idx in range(1, 10):
                if voting_state._internal_state.game_states[player_idx].alive:
                    player_tokens = self.game.get_observation_tokens(voting_state, player_idx)
                    
                    # Should not contain P0's vote information
                    vote_sequence = [TokenID.PLAYER_0.value, TokenID.VOTE.value, TokenID.PLAYER_1.value]
                    contains_vote = self._contains_sequence(player_tokens, vote_sequence)
                    assert not contains_vote, f"P{player_idx} saw P0's vote (privacy violation)"
        except Exception as e:
            pytest.fail(f"Vote privacy test failed: {str(e)}")
    
    def test_vote_revelation_after_tie(self):
        """
        Test that votes are revealed to all players after a voting round completes with a tie.
        
        This tests the core fix where vote revelation should happen when:
        1. All players have voted
        2. There's a tie requiring revote
        3. Active player resets to 0 indicating new round
        """
        try:
            # Initialize game with seed 42 to get deterministic tie scenario
            token_state = self.game.initialize_game(seed=42)
            
            # Advance to voting phase
            voting_state = self._advance_to_voting_phase(token_state)
            
            # Simulate votes that will create a tie (based on seed 42 pattern)
            tie_state = self._simulate_tie_voting_round(voting_state)
            
            # Verify vote revelation is shown to all players
            failed_players = []
            for player_idx in range(10):
                if tie_state._internal_state.game_states[player_idx].alive:
                    player_tokens = self.game.get_observation_tokens(tie_state, player_idx)
                    has_vote_revelation = self._has_vote_revelation(player_tokens)
                    if not has_vote_revelation:
                        failed_players.append(player_idx)
            
            assert len(failed_players) == 0, f"Players {failed_players} missing vote revelation"
        except Exception as e:
            pytest.fail(f"Vote revelation after tie test failed: {str(e)}")
    
    def test_revote_phase_token_emission(self):
        """
        Test that REVOTE_PHASE token is properly emitted when transitioning to revote.
        
        Verifies that the system correctly identifies when a revote is needed
        and emits the appropriate phase token.
        """
        try:
            # Initialize game and advance to tie scenario
            token_state = self.game.initialize_game(seed=42)
            voting_state = self._advance_to_voting_phase(token_state)
            tie_state = self._simulate_tie_voting_round(voting_state)
            
            # Check that REVOTE_PHASE token appears in player sequences
            missing_revote = []
            for player_idx in range(10):
                if tie_state._internal_state.game_states[player_idx].alive:
                    player_tokens = self.game.get_observation_tokens(tie_state, player_idx)
                    has_revote_phase = TokenID.REVOTE_PHASE.value in player_tokens
                    if not has_revote_phase:
                        missing_revote.append(player_idx)
            
            assert len(missing_revote) == 0, f"Players {missing_revote} missing REVOTE_PHASE token"
        except Exception as e:
            pytest.fail(f"REVOTE_PHASE emission test failed: {str(e)}")
    
    def test_vote_revelation_not_duplicated(self):
        """
        Test that vote revelation is not shown multiple times to the same player.
        
        Ensures that the revelation logic doesn't repeatedly show the same votes.
        """
        # Initialize game and create tie scenario
        token_state = self.game.initialize_game(seed=42)
        voting_state = self._advance_to_voting_phase(token_state)
        tie_state = self._simulate_tie_voting_round(voting_state)
        
        # Get initial observation
        initial_tokens = self.game.get_observation_tokens(tie_state, 0)
        vote_revelation_count_1 = self._count_vote_revelations(initial_tokens)
        
        # Get observation again - should not add more revelations
        second_tokens = self.game.get_observation_tokens(tie_state, 0)
        vote_revelation_count_2 = self._count_vote_revelations(second_tokens)
        
        assert vote_revelation_count_1 == vote_revelation_count_2, \
            "Vote revelation should not be duplicated on subsequent observations"
    
    def test_vote_revelation_extraction_methods(self):
        """
        Test that vote revelation tokens are properly extracted using different methods.
        
        Verifies that the _get_vote_revelation_tokens method can extract votes
        from the game engine or fall back to hardcoded reconstruction.
        """
        token_state = self.game.initialize_game(seed=42)
        voting_state = self._advance_to_voting_phase(token_state)
        
        # Test the vote revelation extraction directly
        revelation_tokens = self.game._get_vote_revelation_tokens(voting_state)
        
        # Should return a non-empty list of tokens
        assert len(revelation_tokens) > 0, "Vote revelation should extract tokens"
        
        # Should contain proper vote format: PLAYER_X, VOTE, PLAYER_Y, END_TURN
        assert self._is_valid_vote_revelation_format(revelation_tokens), \
            "Vote revelation should follow proper token format"
    
    def test_should_show_vote_revelation_logic(self):
        """
        Test the logic for determining when to show vote revelation.
        
        Verifies that _should_show_vote_revelation_now correctly identifies
        when vote revelation should be shown to a player.
        """
        token_state = self.game.initialize_game(seed=42)
        voting_state = self._advance_to_voting_phase(token_state)
        
        # Before any votes are cast - should not show revelation
        for player_idx in range(10):
            if voting_state._internal_state.game_states[player_idx].alive:
                should_show = self.game._should_show_vote_revelation_now(voting_state, player_idx)
                assert not should_show, \
                    f"Should not show vote revelation to P{player_idx} before tie"
        
        # After tie scenario - should show revelation
        tie_state = self._simulate_tie_voting_round(voting_state)
        for player_idx in range(10):
            if tie_state._internal_state.game_states[player_idx].alive:
                should_show = self.game._should_show_vote_revelation_now(tie_state, player_idx)
                assert should_show, \
                    f"Should show vote revelation to P{player_idx} after tie"
    
    # Helper methods
    
    def _advance_to_voting_phase(self, token_state):
        """Advance the game to voting phase by having all players end their day turns."""
        current_state = token_state
        
        # Count alive players to know how many END_TURN actions we need
        alive_players = [i for i in range(10) if current_state._internal_state.game_states[i].alive]
        
        # Have each alive player end their turn
        for _ in alive_players:
            active_player = current_state.active_player
            if current_state._internal_state.game_states[active_player].alive:
                end_turn_action = [TokenID.END_TURN.value]
                current_state = self.game.apply_action(current_state, end_turn_action, active_player)
        
        # Verify we're in voting phase
        assert self.game._is_voting_phase(current_state._internal_state), \
            "Should be in voting phase after all day turns complete"
        
        return current_state
    
    def _simulate_tie_voting_round(self, voting_state):
        """Simulate a complete voting round that results in a tie."""
        current_state = voting_state
        
        # Get alive players
        alive_players = [i for i in range(10) if current_state._internal_state.game_states[i].alive]
        
        # Cast votes in a pattern that creates a tie (based on seed 42 pattern)
        vote_pattern = [
            (9, 8), (0, 8), (1, 2), (2, 2), (3, 6),
            (4, 1), (5, 6), (6, 1), (7, 8), (8, 1)
        ]
        
        for voter, target in vote_pattern:
            if (voter < len(alive_players) and 
                current_state._internal_state.game_states[voter].alive and
                current_state.active_player == voter):
                
                vote_action = [TokenID.VOTE.value, TokenID.PLAYER_0.value + target, TokenID.END_TURN.value]
                current_state = self.game.apply_action(current_state, vote_action, voter)
        
        return current_state
    
    def _contains_sequence(self, tokens, sequence):
        """Check if a token sequence contains a specific subsequence."""
        if len(sequence) > len(tokens):
            return False
        
        for i in range(len(tokens) - len(sequence) + 1):
            if tokens[i:i+len(sequence)] == sequence:
                return True
        return False
    
    def _has_vote_revelation(self, tokens):
        """Check if tokens contain vote revelation (multiple VOTE tokens from different players)."""
        vote_count = 0
        different_voters = set()
        
        i = 0
        while i < len(tokens) - 2:
            if (tokens[i] >= TokenID.PLAYER_0.value and tokens[i] <= TokenID.PLAYER_9.value and
                tokens[i + 1] == TokenID.VOTE.value):
                vote_count += 1
                different_voters.add(tokens[i])
                i += 3  # Skip PLAYER, VOTE, TARGET
            else:
                i += 1
        
        # Vote revelation should have multiple votes from different players
        return vote_count >= 3 and len(different_voters) >= 3
    
    def _count_vote_revelations(self, tokens):
        """Count the number of vote revelation sequences in tokens."""
        count = 0
        i = 0
        while i < len(tokens) - 2:
            if (tokens[i] >= TokenID.PLAYER_0.value and tokens[i] <= TokenID.PLAYER_9.value and
                tokens[i + 1] == TokenID.VOTE.value):
                count += 1
                i += 3  # Skip PLAYER, VOTE, TARGET
            else:
                i += 1
        return count
    
    def _is_valid_vote_revelation_format(self, tokens):
        """Check if tokens follow valid vote revelation format."""
        if len(tokens) % 4 != 0:  # Should be groups of 4: PLAYER, VOTE, PLAYER, END_TURN
            return False
        
        for i in range(0, len(tokens), 4):
            if i + 3 >= len(tokens):
                break
            
            # Check format: PLAYER_X, VOTE, PLAYER_Y, END_TURN
            if not (tokens[i] >= TokenID.PLAYER_0.value and tokens[i] <= TokenID.PLAYER_9.value):
                return False
            if tokens[i + 1] != TokenID.VOTE.value:
                return False
            if not (tokens[i + 2] >= TokenID.PLAYER_0.value and tokens[i + 2] <= TokenID.PLAYER_9.value):
                return False
            if tokens[i + 3] != TokenID.END_TURN.value:
                return False
        
        return True


def test_vote_revelation_integration():
    """Integration test for the complete vote revelation fix."""
    game = create_token_game()
    
    # Initialize and advance to voting
    token_state = game.initialize_game(seed=42)
    
    # Fast forward through day phase
    alive_players = [i for i in range(10) if token_state._internal_state.game_states[i].alive]
    current_state = token_state
    
    for _ in alive_players:
        active_player = current_state.active_player
        if current_state._internal_state.game_states[active_player].alive:
            end_turn_action = [TokenID.END_TURN.value]
            current_state = game.apply_action(current_state, end_turn_action, active_player)
    
    # Verify we're in voting phase
    assert game._is_voting_phase(current_state._internal_state)
    
    # Simulate votes to create tie
    vote_pattern = [(9, 8), (0, 8), (1, 2), (2, 2), (3, 6), (4, 1), (5, 6), (6, 1), (7, 8), (8, 1)]
    
    for voter, target in vote_pattern:
        if (current_state._internal_state.game_states[voter].alive and
            current_state.active_player == voter):
            vote_action = [TokenID.VOTE.value, TokenID.PLAYER_0.value + target, TokenID.END_TURN.value]
            current_state = game.apply_action(current_state, vote_action, voter)
    
    # Verify vote revelation is working
    for player_idx in range(10):
        if current_state._internal_state.game_states[player_idx].alive:
            tokens = game.get_observation_tokens(current_state, player_idx)
            
            # Should contain REVOTE_PHASE token
            assert TokenID.REVOTE_PHASE.value in tokens, f"Player {player_idx} should see REVOTE_PHASE"
            
            # Should contain vote revelation
            vote_count = sum(1 for token in tokens if token == TokenID.VOTE.value)
            assert vote_count >= 3, f"Player {player_idx} should see multiple revealed votes"
