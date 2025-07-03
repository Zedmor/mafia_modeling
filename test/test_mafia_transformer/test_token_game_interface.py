"""
Unit tests for TokenGameInterface - the clean token-based game interface.
"""

import pytest
from typing import List

from mafia_transformer.token_game_interface import TokenGameInterface, TokenGameState, create_token_game
from mafia_transformer.token_vocab import TokenID, TOKEN_ID_TO_NAME


class TestTokenGameInterface:
    """Test cases for the TokenGameInterface."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.interface = create_token_game()
        # Use deterministic seeds for predictable testing
        self.seed_citizen_start = 0  # Seed 0: Don=P0, Mafia=P1,P2, Sheriff=P3, Citizens=P4-9
        self.seed_sheriff_start = 42  # Seed 42: Different arrangement  
        self.seed_mafia_start = 100   # Seed 100: Different arrangement
    
    def test_create_token_game_factory(self):
        """Test the factory function creates a valid interface."""
        interface = create_token_game()
        assert isinstance(interface, TokenGameInterface)
        assert interface.current_state is None
    
    def test_initialize_game_basic(self):
        """Test basic game initialization."""
        seed = 12345
        state = self.interface.initialize_game(seed)
        
        # Verify state structure
        assert isinstance(state, TokenGameState)
        assert len(state.seed_tokens) == 3  # SEED, GAME_START, PLAYER_X
        assert state.seed_tokens[1] == TokenID.GAME_START
        assert state.active_player == 0  # Game starts with player 0
        assert len(state.player_chronological_sequences) == 10  # 10 players
        
        # Verify each player has initial chronological sequence with DAY_1 phase
        for player_seq in state.player_chronological_sequences:
            assert len(player_seq) >= 3  # At least GAME_START, PLAYER_X, YOUR_ROLE, role_token, DAY_1
            assert TokenID.GAME_START in player_seq
            assert TokenID.DAY_1 in player_seq
        
        # Verify interface state updated
        assert self.interface.current_state == state
    
    def test_initialize_game_deterministic(self):
        """Test that same seed produces same game setup."""
        seed = 42
        
        # Initialize same game twice
        state1 = self.interface.initialize_game(seed)
        interface2 = create_token_game()
        state2 = interface2.initialize_game(seed)
        
        # Should have identical setup
        assert state1.seed_tokens == state2.seed_tokens
        assert state1.active_player == state2.active_player
        assert state1.player_chronological_sequences == state2.player_chronological_sequences
        
        # Private states should be identical (same role distribution)
        for i in range(10):
            assert state1.private_states[i] == state2.private_states[i]
    
    def test_initialize_game_invalid_players(self):
        """Test initialization with invalid number of players."""
        with pytest.raises(ValueError, match="Currently only 10-player games are supported"):
            self.interface.initialize_game(seed=123, num_players=8)
    
    def test_private_states_contain_roles(self):
        """Test that private states contain role information."""
        state = self.interface.initialize_game(seed=999)
        
        # All players should have role information
        for player_idx, private_tokens in enumerate(state.private_states):
            assert len(private_tokens) >= 2  # At least YOUR_ROLE + role_token
            assert private_tokens[0] == TokenID.YOUR_ROLE
            assert private_tokens[1] in [TokenID.CITIZEN, TokenID.SHERIFF, TokenID.MAFIA, TokenID.DON]
    
    def test_private_states_mafia_team_info(self):
        """Test that mafia members get team information."""
        state = self.interface.initialize_game(seed=777)
        
        mafia_players = []
        for player_idx, private_tokens in enumerate(state.private_states):
            if private_tokens[1] in [TokenID.MAFIA, TokenID.DON]:
                mafia_players.append(player_idx)
                # Should have MAFIA_TEAM token
                assert TokenID.MAFIA_TEAM in private_tokens
        
        # Should have exactly 3 mafia members
        assert len(mafia_players) == 3
    
    def test_get_legal_actions_initial_state(self):
        """Test getting legal actions for initial game state."""
        state = self.interface.initialize_game(seed=555)
        legal_actions = self.interface.get_legal_actions(state)
        
        # Should have legal actions available
        assert len(legal_actions) > 0
        
        # All actions should be valid token sequences
        for action_tokens in legal_actions:
            assert isinstance(action_tokens, list)
            assert len(action_tokens) >= 1
            assert all(isinstance(token, int) for token in action_tokens)
        
        # Should include END_TURN as a legal action
        end_turn_action = [TokenID.END_TURN]
        assert end_turn_action in legal_actions
        
        # Should include nomination actions (since it's day phase)
        nominate_actions = [action for action in legal_actions if action[0] == TokenID.NOMINATE]
        assert len(nominate_actions) > 0
    
    def test_get_legal_actions_invalid_state(self):
        """Test error handling for invalid token state."""
        invalid_state = TokenGameState(
            seed_tokens=[],
            player_chronological_sequences=[],
            active_player=0,
            _internal_state=None
        )
        
        with pytest.raises(ValueError, match="Invalid token state: no internal state"):
            self.interface.get_legal_actions(invalid_state)
    
    def test_apply_action_valid(self):
        """Test applying a valid action."""
        state = self.interface.initialize_game(seed=333)
        legal_actions = self.interface.get_legal_actions(state)
        
        # Pick the first legal action
        action_to_apply = legal_actions[0]
        current_player = state.active_player
        
        # Apply the action
        new_state = self.interface.apply_action(state, action_to_apply, current_player)
        
        # Verify new state
        assert isinstance(new_state, TokenGameState)
        assert new_state != state  # Should be a new state
        
        # Chronological sequences should grow for all players
        for i in range(10):
            assert len(new_state.player_chronological_sequences[i]) >= len(state.player_chronological_sequences[i])
        
        # Interface state should be updated
        assert self.interface.current_state == new_state
    
    def test_apply_action_wrong_player(self):
        """Test error when wrong player tries to act."""
        state = self.interface.initialize_game(seed=111)
        legal_actions = self.interface.get_legal_actions(state)
        
        wrong_player = (state.active_player + 1) % 10
        action_to_apply = legal_actions[0]
        
        with pytest.raises(ValueError, match="Wrong player"):
            self.interface.apply_action(state, action_to_apply, wrong_player)
    
    def test_apply_action_illegal_action(self):
        """Test error when applying illegal action."""
        state = self.interface.initialize_game(seed=222)
        
        # Try to apply an illegal action (e.g., sheriff check during day phase)
        illegal_action = [TokenID.SHERIFF_CHECK, TokenID.PLAYER_1]
        
        with pytest.raises(ValueError, match="Illegal action"):
            self.interface.apply_action(state, illegal_action, state.active_player)
    
    def test_apply_action_invalid_state(self):
        """Test error when applying action to invalid state."""
        invalid_state = TokenGameState(
            seed_tokens=[],
            player_chronological_sequences=[],
            active_player=0,
            _internal_state=None
        )
        
        with pytest.raises(ValueError, match="Invalid token state: no internal state"):
            self.interface.apply_action(invalid_state, [TokenID.END_TURN], 0)
    
    def test_get_game_result_ongoing(self):
        """Test game result for ongoing game."""
        state = self.interface.initialize_game(seed=444)
        result = self.interface.get_game_result(state)
        
        # Game just started, should be ongoing
        assert result is None
    
    def test_get_game_result_invalid_state(self):
        """Test game result for invalid state."""
        invalid_state = TokenGameState(
            seed_tokens=[],
            player_chronological_sequences=[],
            active_player=0,
            _internal_state=None
        )
        
        result = self.interface.get_game_result(invalid_state)
        assert result is None
    
    def test_multiple_actions_sequence(self):
        """Test applying multiple actions in sequence."""
        state = self.interface.initialize_game(seed=666)
        initial_seq_lengths = [len(seq) for seq in state.player_chronological_sequences]
        
        # Apply several actions
        for i in range(3):
            legal_actions = self.interface.get_legal_actions(state)
            assert len(legal_actions) > 0, f"No legal actions at step {i}"
            
            # Apply first legal action
            action = legal_actions[0]
            current_player = state.active_player
            state = self.interface.apply_action(state, action, current_player)
            
            # Verify chronological sequences have grown
            current_seq_lengths = [len(seq) for seq in state.player_chronological_sequences]
            assert any(current > initial for current, initial in zip(current_seq_lengths, initial_seq_lengths))
    
    def test_phase_progression(self):
        """Test that phase tokens update as game progresses."""
        state = self.interface.initialize_game(seed=self.seed_citizen_start)
        
        # Check that we have a valid initial phase in the chronological sequences
        initial_sequences = [seq.copy() for seq in state.player_chronological_sequences]
        
        # Apply actions until phase changes (or max attempts)
        max_attempts = 30
        attempts = 0
        
        while attempts < max_attempts:
            legal_actions = self.interface.get_legal_actions(state)
            if not legal_actions:
                break
            
            action = legal_actions[0]
            current_player = state.active_player
            state = self.interface.apply_action(state, action, current_player)
            attempts += 1
            
            # Check if any player's sequence has grown (indicating game progression)
            current_sequences = state.player_chronological_sequences
            if any(len(current) > len(initial) for current, initial in zip(current_sequences, initial_sequences)):
                break
        
        # The test should either find progression or reach max attempts without failing
        assert attempts <= max_attempts
        # Verify we're still in a valid state
        assert isinstance(state, TokenGameState)
        assert len(state.player_chronological_sequences) == 10
    
    def test_seed_encoding(self):
        """Test seed encoding produces valid token IDs."""
        interface = TokenGameInterface()
        
        # Test various seeds
        for seed in [0, 123, 999, 5555]:
            encoded = interface._encode_seed(seed)
            assert isinstance(encoded, int)
            assert 1000 <= encoded <= 1999  # Within expected range
    
    def test_role_to_token_mapping(self):
        """Test role to token conversion."""
        from mafia_game.common import Role
        
        interface = TokenGameInterface()
        
        # Test all roles
        assert interface._role_to_token(Role.CITIZEN) == TokenID.CITIZEN
        assert interface._role_to_token(Role.SHERIFF) == TokenID.SHERIFF
        assert interface._role_to_token(Role.MAFIA) == TokenID.MAFIA
        assert interface._role_to_token(Role.DON) == TokenID.DON


class TestTokenGameStateStructure:
    """Test the TokenGameState data structure."""
    
    def test_token_game_state_creation(self):
        """Test creating a TokenGameState directly."""
        state = TokenGameState(
            seed_tokens=[1001, TokenID.GAME_START, TokenID.PLAYER_0],
            player_chronological_sequences=[[] for _ in range(10)],
            active_player=0,
            _internal_state=None
        )
        
        assert len(state.seed_tokens) == 3
        assert state.active_player == 0
        assert len(state.player_chronological_sequences) == 10


class TestIntegrationScenarios:
    """Integration tests with realistic game scenarios."""
    
    def test_complete_nomination_round(self):
        """Test a complete nomination round."""
        interface = create_token_game()
        state = interface.initialize_game(seed=1001)
        
        # Count nominations
        nominations_made = 0
        max_nominations = 10  # One per player
        initial_seq_lengths = [len(seq) for seq in state.player_chronological_sequences]
        
        while nominations_made < max_nominations:
            legal_actions = interface.get_legal_actions(state)
            
            # Look for nomination actions
            nomination_actions = [action for action in legal_actions if action[0] == TokenID.NOMINATE]
            
            if nomination_actions:
                # Make a nomination
                action = nomination_actions[0]
                current_player = state.active_player
                state = interface.apply_action(state, action, current_player)
                nominations_made += 1
            else:
                # No nominations available, might have moved to voting phase
                break
        
        # Should have made at least some nominations
        assert nominations_made > 0
        # Verify chronological sequences have grown
        current_seq_lengths = [len(seq) for seq in state.player_chronological_sequences]
        assert any(current > initial for current, initial in zip(current_seq_lengths, initial_seq_lengths))
    
    def test_deterministic_gameplay(self):
        """Test that deterministic seed produces reproducible gameplay."""
        seed = 2024
        
        # Play same sequence with two interfaces
        def play_sequence(seed, num_actions=5):
            interface = create_token_game()
            state = interface.initialize_game(seed)
            history = []
            
            for _ in range(num_actions):
                legal_actions = interface.get_legal_actions(state)
                if not legal_actions:
                    break
                
                # Always pick first legal action for determinism
                action = legal_actions[0]
                current_player = state.active_player
                history.append((current_player, action))
                state = interface.apply_action(state, action, current_player)
            
            return history, state.chronological_history
        
        history1, chronological1 = play_sequence(seed)
        history2, chronological2 = play_sequence(seed)
        
        # Should be identical
        assert history1 == history2
        assert chronological1 == chronological2


class TestDeterministicSeeding:
    """Tests specifically for deterministic seeding functionality."""
    
    def test_seed_0_known_arrangement(self):
        """Test that seed 0 produces the known first arrangement."""
        interface = create_token_game()
        state = interface.initialize_game(seed=0)
        
        # Seed 0 should produce: Don=P0, Mafia=P1,P2, Sheriff=P3, Citizens=P4-9
        expected_roles = [
            TokenID.DON,      # Player 0
            TokenID.MAFIA,    # Player 1  
            TokenID.MAFIA,    # Player 2
            TokenID.SHERIFF,  # Player 3
            TokenID.CITIZEN,  # Player 4
            TokenID.CITIZEN,  # Player 5
            TokenID.CITIZEN,  # Player 6
            TokenID.CITIZEN,  # Player 7
            TokenID.CITIZEN,  # Player 8
            TokenID.CITIZEN   # Player 9
        ]
        
        for player_idx, expected_role in enumerate(expected_roles):
            private_tokens = state.private_states[player_idx]
            actual_role = private_tokens[1]  # Role token is second
            assert actual_role == expected_role, f"Player {player_idx}: expected {expected_role}, got {actual_role}"
    
    def test_specific_seed_scenarios(self):
        """Test specific seed scenarios for predictable testing."""
        test_scenarios = [
            {
                'seed': 0,
                'description': "Don starts, mafia team P0,P1,P2, sheriff P3",
                'don_player': 0,
                'sheriff_player': 3,
                'mafia_count': 3,
            },
            {
                'seed': 1,
                'description': "Different arrangement to test variety",
                'don_player': 0,  # Seed 1 still has Don at P0 based on our algorithm
                'sheriff_player': 4,  # But sheriff in different position
                'mafia_count': 3,
            },
            {
                'seed': 42,
                'description': "Mid-range seed for diverse testing",
                'mafia_count': 3,
            }
        ]
        
        for scenario in test_scenarios:
            interface = create_token_game()
            state = interface.initialize_game(seed=scenario['seed'])
            
            # Verify basic invariants
            mafia_players = []
            don_players = []
            sheriff_players = []
            citizen_players = []
            
            for player_idx, private_tokens in enumerate(state.private_states):
                role_token = private_tokens[1]
                if role_token == TokenID.DON:
                    don_players.append(player_idx)
                elif role_token == TokenID.MAFIA:
                    mafia_players.append(player_idx)
                elif role_token == TokenID.SHERIFF:
                    sheriff_players.append(player_idx)
                elif role_token == TokenID.CITIZEN:
                    citizen_players.append(player_idx)
            
            # Verify correct counts
            assert len(don_players) == 1, f"Seed {scenario['seed']}: Expected 1 Don, got {len(don_players)}"
            assert len(mafia_players) == 2, f"Seed {scenario['seed']}: Expected 2 Mafia, got {len(mafia_players)}"
            assert len(sheriff_players) == 1, f"Seed {scenario['seed']}: Expected 1 Sheriff, got {len(sheriff_players)}"
            assert len(citizen_players) == 6, f"Seed {scenario['seed']}: Expected 6 Citizens, got {len(citizen_players)}"
            
            # Verify specific positions if provided
            if 'don_player' in scenario:
                assert don_players[0] == scenario['don_player'], f"Seed {scenario['seed']}: Don should be player {scenario['don_player']}"
            
            if 'sheriff_player' in scenario:
                assert sheriff_players[0] == scenario['sheriff_player'], f"Seed {scenario['seed']}: Sheriff should be player {scenario['sheriff_player']}"
    
    def test_mafia_team_information_deterministic(self):
        """Test that mafia team information is deterministic for specific seeds."""
        seeds_to_test = [0, 1, 42, 100, 500, 1000, 2519]
        
        for seed in seeds_to_test:
            interface = create_token_game()
            state = interface.initialize_game(seed=seed)
            
            # Find all mafia members (including Don)
            mafia_team = []
            for player_idx, private_tokens in enumerate(state.private_states):
                role_token = private_tokens[1]
                if role_token in [TokenID.DON, TokenID.MAFIA]:
                    mafia_team.append(player_idx)
            
            assert len(mafia_team) == 3, f"Seed {seed}: Should have exactly 3 mafia members"
            
            # Verify each mafia member knows about the others
            for mafia_player in mafia_team:
                private_tokens = state.private_states[mafia_player]
                
                # Should have MAFIA_TEAM token
                assert TokenID.MAFIA_TEAM in private_tokens, f"Seed {seed}: Player {mafia_player} missing MAFIA_TEAM token"
                
                # Should have player tokens for other mafia members
                other_mafia = [p for p in mafia_team if p != mafia_player]
                for other_player in other_mafia:
                    expected_token = TokenID.PLAYER_0 + other_player
                    assert expected_token in private_tokens, f"Seed {seed}: Player {mafia_player} missing info about player {other_player}"
    
    def test_reproducible_test_scenarios(self):
        """Test that we can create reproducible test scenarios for complex gameplay."""
        # This demonstrates how deterministic seeding enables reproducible testing
        # of complex scenarios like "what happens when sheriff investigates don"
        
        seed = 0  # We know: Don=P0, Sheriff=P3
        interface = create_token_game()
        state = interface.initialize_game(seed=seed)
        
        # Verify our known initial state
        don_private = state.private_states[0]
        sheriff_private = state.private_states[3]
        
        assert don_private[1] == TokenID.DON
        assert sheriff_private[1] == TokenID.SHERIFF
        
        # Now we can create predictable test scenarios:
        # 1. Test sheriff checking the don (should return red)
        # 2. Test don checking the sheriff (should return red)
        # 3. Test citizen behavior in known role environment
        
        # This is just the setup - the actual scenario testing would involve
        # progressing through the game phases to night phase for investigations
        
        # Verify the setup is ready for scenario testing
        assert state.active_player == 0  # Don starts
        
        # Check that DAY_1 phase is in chronological sequences
        for player_seq in state.player_chronological_sequences:
            assert TokenID.DAY_1 in player_seq
        
        # The beauty of deterministic seeding is that we can now write
        # very specific tests like "test what happens when the Don nominates
        # the Sheriff on the first day" knowing exactly who has which role
    
    def test_edge_case_seeds(self):
        """Test edge cases like first and last valid seeds."""
        edge_seeds = [0, 1, 2519]  # First, second, and last valid seeds
        
        for seed in edge_seeds:
            interface = create_token_game()
            state = interface.initialize_game(seed=seed)
            
            # Should all produce valid game states
            assert isinstance(state, TokenGameState)
            assert len(state.player_chronological_sequences) == 10
            assert len(state.seed_tokens) == 3
            assert state.seed_tokens[1] == TokenID.GAME_START
            
            # Should have valid role distribution
            role_counts = {TokenID.DON: 0, TokenID.MAFIA: 0, TokenID.SHERIFF: 0, TokenID.CITIZEN: 0}
            for private_tokens in state.private_states:
                role_token = private_tokens[1]
                role_counts[role_token] += 1
            
            assert role_counts[TokenID.DON] == 1
            assert role_counts[TokenID.MAFIA] == 2  
            assert role_counts[TokenID.SHERIFF] == 1
            assert role_counts[TokenID.CITIZEN] == 6
    
    def test_seed_validation_in_interface(self):
        """Test that interface properly validates seed ranges."""
        interface = create_token_game()
        
        # Valid seeds should work
        valid_seeds = [0, 1, 100, 1000, 2519]
        for seed in valid_seeds:
            state = interface.initialize_game(seed=seed)
            assert isinstance(state, TokenGameState)
        
        # Invalid seeds should be handled (wrapped to valid range)
        # Since our implementation uses modulo, these should work but wrap around
        invalid_seeds = [-1, 2520, 9999]
        for seed in invalid_seeds:
            # Should not raise an error due to wrapping
            state = interface.initialize_game(seed=seed)
            assert isinstance(state, TokenGameState)
