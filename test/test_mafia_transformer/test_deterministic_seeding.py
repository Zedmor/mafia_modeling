"""
Test deterministic seeding functionality.
"""

import pytest
from mafia_transformer.token_game_interface import TokenGameInterface, create_token_game
from mafia_transformer.token_vocab import TokenID
from mafia_game.common import Role


class TestDeterministicSeeding:
    """Test deterministic seed generation."""
    
    def test_total_arrangements_count(self):
        """Test that we have exactly 2,520 arrangements."""
        interface = create_token_game()
        total = interface.get_total_arrangements()
        
        # Mathematical calculation: C(10,1) * C(9,2) * C(7,1) * C(6,6) = 10 * 36 * 7 * 1 = 2,520
        expected = 10 * 36 * 7 * 1
        assert total == expected == 2520
    
    def test_seed_0_specific_arrangement(self):
        """Test that seed 0 produces the expected arrangement."""
        interface = create_token_game()
        state = interface.initialize_game(seed=0)
        
        # Get roles from internal state
        roles = [player.private_data.role for player in state._internal_state.game_states]
        
        # First arrangement should be: Don=0, Mafia=1,2, Sheriff=3, Citizens=4-9
        expected_roles = [
            Role.DON,      # Player 0
            Role.MAFIA,    # Player 1
            Role.MAFIA,    # Player 2
            Role.SHERIFF,  # Player 3
            Role.CITIZEN,  # Player 4
            Role.CITIZEN,  # Player 5
            Role.CITIZEN,  # Player 6
            Role.CITIZEN,  # Player 7
            Role.CITIZEN,  # Player 8
            Role.CITIZEN   # Player 9
        ]
        
        assert roles == expected_roles
    
    def test_deterministic_reproducibility(self):
        """Test that same seed produces identical arrangements."""
        seed = 42
        
        interface1 = create_token_game()
        state1 = interface1.initialize_game(seed=seed)
        roles1 = [player.private_data.role for player in state1._internal_state.game_states]
        
        interface2 = create_token_game()
        state2 = interface2.initialize_game(seed=seed)
        roles2 = [player.private_data.role for player in state2._internal_state.game_states]
        
        assert roles1 == roles2
        assert state1.seed_tokens == state2.seed_tokens
        assert state1.private_states == state2.private_states
    
    def test_different_seeds_different_arrangements(self):
        """Test that different seeds produce different arrangements."""
        interface = create_token_game()
        
        state1 = interface.initialize_game(seed=0)
        roles1 = [player.private_data.role for player in state1._internal_state.game_states]
        
        state2 = interface.initialize_game(seed=1)
        roles2 = [player.private_data.role for player in state2._internal_state.game_states]
        
        # Should be different arrangements
        assert roles1 != roles2
    
    def test_role_distribution_invariants(self):
        """Test that all arrangements have correct role distribution."""
        interface = create_token_game()
        
        # Test several random seeds
        for seed in [0, 1, 100, 500, 1000, 2000, 2519]:
            state = interface.initialize_game(seed=seed)
            roles = [player.private_data.role for player in state._internal_state.game_states]
            
            # Count roles
            role_counts = {
                Role.DON: roles.count(Role.DON),
                Role.MAFIA: roles.count(Role.MAFIA),
                Role.SHERIFF: roles.count(Role.SHERIFF),
                Role.CITIZEN: roles.count(Role.CITIZEN)
            }
            
            # Should always have correct distribution
            assert role_counts[Role.DON] == 1
            assert role_counts[Role.MAFIA] == 2
            assert role_counts[Role.SHERIFF] == 1
            assert role_counts[Role.CITIZEN] == 6
    
    def test_mafia_team_information(self):
        """Test that mafia members know about each other."""
        interface = create_token_game()
        state = interface.initialize_game(seed=123)
        
        # Find mafia players
        mafia_players = []
        for i, player in enumerate(state._internal_state.game_states):
            if player.private_data.role in [Role.MAFIA, Role.DON]:
                mafia_players.append(i)
        
        assert len(mafia_players) == 3  # 1 Don + 2 Mafia
        
        # Check that each mafia member knows about the others
        for mafia_idx in mafia_players:
            other_mafias = state._internal_state.game_states[mafia_idx].private_data.other_mafias.other_mafias
            # Should contain all mafia player indexes
            mafia_set = set(mafia_players)
            other_mafia_set = set([x for x in other_mafias if x != -1])
            assert mafia_set == other_mafia_set
    
    def test_private_states_contain_mafia_team_info(self):
        """Test that private token states contain mafia team information."""
        interface = create_token_game()
        state = interface.initialize_game(seed=456)
        
        # Find mafia players
        mafia_players = []
        for i, player in enumerate(state._internal_state.game_states):
            if player.private_data.role in [Role.MAFIA, Role.DON]:
                mafia_players.append(i)
        
        # Check private states for mafia players
        from mafia_transformer.token_vocab import TokenID
        
        for mafia_idx in mafia_players:
            private_tokens = state.private_states[mafia_idx]
            
            # Should contain MAFIA_TEAM token
            assert TokenID.MAFIA_TEAM in private_tokens
            
            # Should contain player tokens for other mafia members
            other_mafia_players = [p for p in mafia_players if p != mafia_idx]
            for other_mafia in other_mafia_players:
                expected_token = TokenID.PLAYER_0 + other_mafia
                assert expected_token in private_tokens
    
    def test_seed_wrapping(self):
        """Test that seeds wrap around correctly."""
        interface = create_token_game()
        total_arrangements = interface.get_total_arrangements()
        
        # Test that seed 0 and seed 2520 produce the same arrangement
        state1 = interface.initialize_game(seed=0)
        state2 = interface.initialize_game(seed=total_arrangements)  # Should wrap to 0
        
        roles1 = [player.private_data.role for player in state1._internal_state.game_states]
        roles2 = [player.private_data.role for player in state2._internal_state.game_states]
        
        assert roles1 == roles2
    
    def test_specific_arrangements_samples(self):
        """Test a few specific arrangements to verify correctness."""
        interface = create_token_game()
        
        # Test arrangement at index 1 (second arrangement)
        state = interface.initialize_game(seed=1)
        roles = [player.private_data.role for player in state._internal_state.game_states]
        
        # Should have exactly 1 Don, 2 Mafia, 1 Sheriff, 6 Citizens
        assert roles.count(Role.DON) == 1
        assert roles.count(Role.MAFIA) == 2
        assert roles.count(Role.SHERIFF) == 1
        assert roles.count(Role.CITIZEN) == 6
        
        # All positions should be filled
        assert len(roles) == 10
        assert all(role in [Role.DON, Role.MAFIA, Role.SHERIFF, Role.CITIZEN] for role in roles)
    
    def test_interface_state_updates(self):
        """Test that interface state is properly updated."""
        interface = create_token_game()
        
        # Initially no current state
        assert interface.current_state is None
        
        # After initialization, should have current state
        state = interface.initialize_game(seed=789)
        assert interface.current_state is not None
        assert interface.current_state == state
        
        # State should have proper structure
        assert len(state.seed_tokens) == 3
        assert state.seed_tokens[1] == TokenID.GAME_START
        assert len(state.private_states) == 10
        assert state.active_player == 0
        assert len(state.player_chronological_sequences) == 10
        
        # Check that each player has initial chronological sequence with DAY_1 phase
        for player_seq in state.player_chronological_sequences:
            assert TokenID.DAY_1 in player_seq
