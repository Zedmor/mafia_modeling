"""
Unit tests for the night phase detection bug in TokenGameClient.

The bug: TokenGameClient incorrectly builds multi-action sequences for night phases
because it only checks if END_TURN is available, but night phases also have END_TURN.
"""

import pytest
from unittest.mock import Mock, MagicMock
from mafia_transformer.token_game_server import TokenGameClient, TokenGameServer, PlayerStateTokens
from mafia_transformer.token_vocab import TokenID


class TestNightPhaseDetectionBug:
    """Test cases for the night phase detection bug in TokenGameClient."""
    
    def test_night_phase_should_not_build_multi_action_sequences(self):
        """Test that night phases correctly send single actions, not multi-action sequences."""
        # Create a mock server
        mock_server = Mock(spec=TokenGameServer)
        client = TokenGameClient(player_id=1, server=mock_server)
        
        # Mock night phase legal actions (includes END_TURN but should be single actions only)
        night_legal_actions = [
            [TokenID.KILL.value, TokenID.PLAYER_2.value],
            [TokenID.KILL.value, TokenID.PLAYER_3.value], 
            [TokenID.KILL.value, TokenID.PLAYER_4.value],
            [TokenID.END_TURN.value]  # END_TURN is available but this is NIGHT phase
        ]
        
        # Test multiple times to ensure consistent behavior
        for i in range(10):
            chosen_action = client.choose_action(night_legal_actions)
            
            # Should choose one of the legal actions, not build a sequence
            assert chosen_action in night_legal_actions, f"Iteration {i}: {chosen_action} not in legal actions"
            
            # Should NOT be a multi-action sequence with multiple kills
            if TokenID.KILL.value in chosen_action:
                # Count KILL tokens - should be at most 1
                kill_count = chosen_action.count(TokenID.KILL.value)
                assert kill_count <= 1, f"Iteration {i}: Night phase should not have multiple KILL actions: {chosen_action}"
    
    def test_day_phase_should_build_multi_action_sequences(self):
        """Test that day phases correctly build multi-action sequences."""
        mock_server = Mock(spec=TokenGameServer)
        client = TokenGameClient(player_id=1, server=mock_server)
        
        # Mock day phase legal actions (many actions available)
        day_legal_actions = [
            [TokenID.SAY.value, TokenID.PLAYER_2.value, TokenID.BLACK.value],
            [TokenID.SAY.value, TokenID.PLAYER_3.value, TokenID.RED.value],
            [TokenID.NOMINATE.value, TokenID.PLAYER_4.value],
            [TokenID.CLAIM_SHERIFF.value],
            [TokenID.END_TURN.value]  # END_TURN available in day phase too
        ]
        
        # Test multiple times
        for i in range(10):
            chosen_action = client.choose_action(day_legal_actions)
            
            # Should end with exactly one END_TURN token
            end_turn_count = chosen_action.count(TokenID.END_TURN.value)
            assert end_turn_count == 1, f"Iteration {i}: Should have exactly 1 END_TURN: {chosen_action}"
            assert chosen_action[-1] == TokenID.END_TURN.value, f"Iteration {i}: Should end with END_TURN: {chosen_action}"
    
    def test_voting_phase_should_send_single_actions(self):
        """Test that voting phases send single actions, not sequences."""
        mock_server = Mock(spec=TokenGameServer)
        client = TokenGameClient(player_id=1, server=mock_server)
        
        # Mock voting phase legal actions (limited voting options)
        voting_legal_actions = [
            [TokenID.VOTE.value, TokenID.PLAYER_2.value],
            [TokenID.VOTE.value, TokenID.PLAYER_3.value],
            [TokenID.VOTE.value, TokenID.PLAYER_4.value]
        ]
        
        # Test multiple times
        for i in range(10):
            chosen_action = client.choose_action(voting_legal_actions)
            
            # Should choose exactly one of the legal actions
            assert chosen_action in voting_legal_actions, f"Iteration {i}: {chosen_action} not in legal actions"
            
            # Should not contain multiple VOTE tokens
            vote_count = chosen_action.count(TokenID.VOTE.value)
            assert vote_count == 1, f"Iteration {i}: Should have exactly 1 VOTE: {chosen_action}"
    
    def test_phase_detection_with_mock_player_state(self):
        """Test that phase detection works correctly with player state information."""
        mock_server = Mock(spec=TokenGameServer)
        client = TokenGameClient(player_id=1, server=mock_server)
        
        # Test with night phase state
        night_state = PlayerStateTokens(
            player_id=1,
            seed_tokens=[1042, TokenID.GAME_START.value, TokenID.PLAYER_1.value],
            chronological_history=[TokenID.NIGHT_1.value],  # This is a night phase
            private_state=[TokenID.YOUR_ROLE.value, TokenID.MAFIA.value],
            active_player=1,
            is_active=True
        )
        
        # Mock the request_game_state to return night phase
        original_request = client.request_game_state
        client.request_game_state = Mock(return_value=(
            night_state,
            [[TokenID.KILL.value, TokenID.PLAYER_2.value], [TokenID.END_TURN.value]]
        ))
        
        # Play turn should result in single action
        mock_server.apply_player_action = Mock(return_value=Mock(success=True, game_finished=False))
        
        success = client.play_turn()
        assert success
        
        # Check that the action sent was a single action, not a sequence
        call_args = mock_server.apply_player_action.call_args
        if call_args:
            action_sent = call_args[0][1]  # Second argument is action_tokens
            
            # Should be a single action, not a multi-action sequence
            if TokenID.KILL.value in action_sent:
                kill_count = action_sent.count(TokenID.KILL.value)
                assert kill_count == 1, f"Night phase should send single KILL action: {action_sent}"
    
    def test_client_does_not_add_extra_end_turn_to_single_actions(self):
        """Test that client doesn't add extra END_TURN tokens to actions that don't need them."""
        mock_server = Mock(spec=TokenGameServer)
        client = TokenGameClient(player_id=1, server=mock_server)
        
        # Legal actions that are complete single actions (no END_TURN needed)
        single_actions = [
            [TokenID.KILL.value, TokenID.PLAYER_2.value],
            [TokenID.SHERIFF_CHECK.value, TokenID.PLAYER_3.value],
            [TokenID.VOTE.value, TokenID.PLAYER_4.value]
        ]
        
        for action in single_actions:
            chosen = client.choose_action([action])
            
            # Should be exactly the same action, no extra END_TURN added
            assert chosen == action, f"Should not modify single action {action}, got {chosen}"
            
            # Should not have any END_TURN tokens in single night/voting actions
            end_turn_count = chosen.count(TokenID.END_TURN.value)
            assert end_turn_count == 0, f"Single action should not have END_TURN: {chosen}"


class TestClientPhaseDetectionIntegration:
    """Integration tests for proper phase detection in real game scenarios."""
    
    def test_night_kill_phase_detection(self):
        """Test that night kill phases are properly detected and handled."""
        mock_server = Mock(spec=TokenGameServer)
        client = TokenGameClient(player_id=1, server=mock_server)
        
        # Simulate night kill phase response from server
        night_response = Mock()
        night_response.success = True
        night_response.game_finished = False
        night_response.player_state = PlayerStateTokens(
            player_id=1,
            seed_tokens=[1042, TokenID.GAME_START.value, TokenID.PLAYER_1.value],
            chronological_history=[TokenID.NIGHT_1.value],
            private_state=[TokenID.YOUR_ROLE.value, TokenID.MAFIA.value],
            active_player=1,
            is_active=True
        )
        night_response.legal_actions = [
            [TokenID.KILL.value, TokenID.PLAYER_2.value],
            [TokenID.KILL.value, TokenID.PLAYER_3.value],
            [TokenID.KILL.value, TokenID.PLAYER_4.value],
            [TokenID.END_TURN.value]
        ]
        
        mock_server.get_player_state.return_value = night_response
        mock_server.apply_player_action.return_value = Mock(success=True, game_finished=False)
        
        # Play turn
        success = client.play_turn()
        assert success
        
        # Verify the action sent was appropriate for night phase
        call_args = mock_server.apply_player_action.call_args
        action_sent = call_args[0][1]
        
        # Should be one of the legal single actions
        assert action_sent in night_response.legal_actions
        
        # If it's a KILL action, should not be a multi-kill sequence
        if TokenID.KILL.value in action_sent:
            kill_count = action_sent.count(TokenID.KILL.value)
            assert kill_count <= 1, f"Night phase should not send multi-kill sequence: {action_sent}"
    
    def test_sheriff_check_phase_detection(self):
        """Test that sheriff check phases are properly detected and handled."""
        mock_server = Mock(spec=TokenGameServer)
        client = TokenGameClient(player_id=2, server=mock_server)
        
        # Simulate sheriff check phase response
        sheriff_response = Mock()
        sheriff_response.success = True
        sheriff_response.game_finished = False
        sheriff_response.player_state = PlayerStateTokens(
            player_id=2,
            seed_tokens=[1042, TokenID.GAME_START.value, TokenID.PLAYER_2.value],
            chronological_history=[TokenID.NIGHT_1.value],
            private_state=[TokenID.YOUR_ROLE.value, TokenID.SHERIFF.value],
            active_player=2,
            is_active=True
        )
        sheriff_response.legal_actions = [
            [TokenID.SHERIFF_CHECK.value, TokenID.PLAYER_0.value],
            [TokenID.SHERIFF_CHECK.value, TokenID.PLAYER_1.value],
            [TokenID.SHERIFF_CHECK.value, TokenID.PLAYER_3.value],
            [TokenID.END_TURN.value]
        ]
        
        mock_server.get_player_state.return_value = sheriff_response
        mock_server.apply_player_action.return_value = Mock(success=True, game_finished=False)
        
        # Play turn
        success = client.play_turn()
        assert success
        
        # Verify single action sent
        call_args = mock_server.apply_player_action.call_args
        action_sent = call_args[0][1]
        
        assert action_sent in sheriff_response.legal_actions
        
        # Should not be a multi-check sequence
        if TokenID.SHERIFF_CHECK.value in action_sent:
            check_count = action_sent.count(TokenID.SHERIFF_CHECK.value)
            assert check_count <= 1, f"Night phase should not send multi-check sequence: {action_sent}"
