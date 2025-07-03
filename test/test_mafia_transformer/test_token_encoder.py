"""
Unit tests for token encoding and decoding functionality.
"""
import sys
from pathlib import Path

import pytest

from mafia_game.actions import (
    Action, NullAction, KillAction, NominationAction, 
    DonCheckAction, SheriffCheckAction, SheriffDeclarationAction,
    PublicSheriffDeclarationAction, VoteAction, EliminateAllNominatedVoteAction
)
from mafia_game.common import Team, Role
from mafia_transformer.token_vocab import TokenID, player_index_to_token, token_to_player_index
from mafia_transformer.token_encoder import (
    TokenEncoder, encode_action, decode_action, 
    encode_sequence, decode_sequence, validate_action_tokens
)


class TestTokenEncoder:
    """Test cases for the TokenEncoder class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.encoder = TokenEncoder()
    
    def test_encode_null_action(self):
        """Test encoding of NullAction."""
        action = NullAction(0)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.END_TURN]
    
    def test_decode_null_action(self):
        """Test decoding of NullAction."""
        tokens = [TokenID.END_TURN]
        action = self.encoder.decode_action(tokens, 0)
        assert isinstance(action, NullAction)
        assert action.player_index == 0
    
    def test_encode_nomination_action(self):
        """Test encoding of NominationAction."""
        action = NominationAction(2, 5)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.NOMINATE, TokenID.PLAYER_5]
    
    def test_decode_nomination_action(self):
        """Test decoding of NominationAction."""
        tokens = [TokenID.NOMINATE, TokenID.PLAYER_5]
        action = self.encoder.decode_action(tokens, 2)
        assert isinstance(action, NominationAction)
        assert action.player_index == 2
        assert action.target_player == 5
    
    def test_encode_vote_action(self):
        """Test encoding of VoteAction."""
        action = VoteAction(1, 3)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.VOTE, TokenID.PLAYER_3]
    
    def test_decode_vote_action(self):
        """Test decoding of VoteAction."""
        tokens = [TokenID.VOTE, TokenID.PLAYER_3]
        action = self.encoder.decode_action(tokens, 1)
        assert isinstance(action, VoteAction)
        assert action.player_index == 1
        assert action.target_player == 3
    
    def test_encode_kill_action(self):
        """Test encoding of KillAction."""
        action = KillAction(4, 7)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.KILL, TokenID.PLAYER_7]
    
    def test_decode_kill_action(self):
        """Test decoding of KillAction."""
        tokens = [TokenID.KILL, TokenID.PLAYER_7]
        action = self.encoder.decode_action(tokens, 4)
        assert isinstance(action, KillAction)
        assert action.player_index == 4
        assert action.target_player == 7
    
    def test_encode_sheriff_check_action(self):
        """Test encoding of SheriffCheckAction."""
        action = SheriffCheckAction(3, 6)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.SHERIFF_CHECK, TokenID.PLAYER_6]
    
    def test_decode_sheriff_check_action(self):
        """Test decoding of SheriffCheckAction."""
        tokens = [TokenID.SHERIFF_CHECK, TokenID.PLAYER_6]
        action = self.encoder.decode_action(tokens, 3)
        assert isinstance(action, SheriffCheckAction)
        assert action.player_index == 3
        assert action.target_player == 6
    
    def test_encode_don_check_action(self):
        """Test encoding of DonCheckAction."""
        action = DonCheckAction(0, 2)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.DON_CHECK, TokenID.PLAYER_2]
    
    def test_decode_don_check_action(self):
        """Test decoding of DonCheckAction."""
        tokens = [TokenID.DON_CHECK, TokenID.PLAYER_2]
        action = self.encoder.decode_action(tokens, 0)
        assert isinstance(action, DonCheckAction)
        assert action.player_index == 0
        assert action.target_player == 2
    
    def test_encode_sheriff_declaration_claim(self):
        """Test encoding of SheriffDeclarationAction (claiming sheriff)."""
        action = SheriffDeclarationAction(1, True)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.CLAIM_SHERIFF]
    
    def test_decode_sheriff_declaration_claim(self):
        """Test decoding of SheriffDeclarationAction (claiming sheriff)."""
        tokens = [TokenID.CLAIM_SHERIFF]
        action = self.encoder.decode_action(tokens, 1)
        assert isinstance(action, SheriffDeclarationAction)
        assert action.player_index == 1
        assert action.i_am_sheriff == True
    
    def test_encode_sheriff_declaration_deny(self):
        """Test encoding of SheriffDeclarationAction (denying sheriff)."""
        action = SheriffDeclarationAction(2, False)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.DENY_SHERIFF]
    
    def test_decode_sheriff_declaration_deny(self):
        """Test decoding of SheriffDeclarationAction (denying sheriff)."""
        tokens = [TokenID.DENY_SHERIFF]
        action = self.encoder.decode_action(tokens, 2)
        assert isinstance(action, SheriffDeclarationAction)
        assert action.player_index == 2
        assert action.i_am_sheriff == False
    
    def test_encode_public_sheriff_declaration_red(self):
        """Test encoding of PublicSheriffDeclarationAction (red team)."""
        action = PublicSheriffDeclarationAction(3, 5, Team.RED_TEAM)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.CLAIM_SHERIFF_CHECK, TokenID.PLAYER_5, TokenID.RED]
    
    def test_decode_public_sheriff_declaration_red(self):
        """Test decoding of PublicSheriffDeclarationAction (red team)."""
        tokens = [TokenID.CLAIM_SHERIFF_CHECK, TokenID.PLAYER_5, TokenID.RED]
        action = self.encoder.decode_action(tokens, 3)
        assert isinstance(action, PublicSheriffDeclarationAction)
        assert action.player_index == 3
        assert action.target_player == 5
        assert action.role == Team.RED_TEAM
    
    def test_encode_public_sheriff_declaration_black(self):
        """Test encoding of PublicSheriffDeclarationAction (black team)."""
        action = PublicSheriffDeclarationAction(4, 1, Team.BLACK_TEAM)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.CLAIM_SHERIFF_CHECK, TokenID.PLAYER_1, TokenID.BLACK]
    
    def test_decode_public_sheriff_declaration_black(self):
        """Test decoding of PublicSheriffDeclarationAction (black team)."""
        tokens = [TokenID.CLAIM_SHERIFF_CHECK, TokenID.PLAYER_1, TokenID.BLACK]
        action = self.encoder.decode_action(tokens, 4)
        assert isinstance(action, PublicSheriffDeclarationAction)
        assert action.player_index == 4
        assert action.target_player == 1
        assert action.role == Team.BLACK_TEAM
    
    def test_encode_eliminate_all_vote_yes(self):
        """Test encoding of EliminateAllNominatedVoteAction (yes)."""
        action = EliminateAllNominatedVoteAction(2, True)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.VOTE_ELIMINATE_ALL]
    
    def test_decode_eliminate_all_vote_yes(self):
        """Test decoding of EliminateAllNominatedVoteAction (yes)."""
        tokens = [TokenID.VOTE_ELIMINATE_ALL]
        action = self.encoder.decode_action(tokens, 2)
        assert isinstance(action, EliminateAllNominatedVoteAction)
        assert action.player_index == 2
        assert action.eliminate_all == True
    
    def test_encode_eliminate_all_vote_no(self):
        """Test encoding of EliminateAllNominatedVoteAction (no)."""
        action = EliminateAllNominatedVoteAction(6, False)
        tokens = self.encoder.encode_action(action)
        assert tokens == [TokenID.VOTE_KEEP_ALL]
    
    def test_decode_eliminate_all_vote_no(self):
        """Test decoding of EliminateAllNominatedVoteAction (no)."""
        tokens = [TokenID.VOTE_KEEP_ALL]
        action = self.encoder.decode_action(tokens, 6)
        assert isinstance(action, EliminateAllNominatedVoteAction)
        assert action.player_index == 6
        assert action.eliminate_all == False
    
    def test_round_trip_encoding_all_actions(self):
        """Test that all action types can be encoded and decoded correctly (round-trip test)."""
        test_actions = [
            NullAction(0),
            NominationAction(1, 5),
            VoteAction(2, 3),
            KillAction(3, 7),
            SheriffCheckAction(4, 2),
            DonCheckAction(5, 8),
            SheriffDeclarationAction(6, True),
            SheriffDeclarationAction(7, False),
            PublicSheriffDeclarationAction(8, 4, Team.RED_TEAM),
            PublicSheriffDeclarationAction(9, 1, Team.BLACK_TEAM),
            EliminateAllNominatedVoteAction(0, True),
            EliminateAllNominatedVoteAction(1, False),
        ]
        
        for original_action in test_actions:
            # Encode then decode
            tokens = self.encoder.encode_action(original_action)
            decoded_action = self.encoder.decode_action(tokens, original_action.player_index)
            
            # Check that the decoded action matches the original
            assert type(decoded_action) == type(original_action)
            assert decoded_action.player_index == original_action.player_index
            
            # Check action-specific attributes
            if hasattr(original_action, 'target_player'):
                assert decoded_action.target_player == original_action.target_player
            if hasattr(original_action, 'i_am_sheriff'):
                assert decoded_action.i_am_sheriff == original_action.i_am_sheriff
            if hasattr(original_action, 'role'):
                assert decoded_action.role == original_action.role
            if hasattr(original_action, 'eliminate_all'):
                assert decoded_action.eliminate_all == original_action.eliminate_all
    
    def test_encode_sequence(self):
        """Test encoding of action sequences."""
        actions = [
            NominationAction(1, 5),
            VoteAction(2, 5),
            KillAction(3, 2)
        ]
        tokens = self.encoder.encode_sequence(actions)
        expected = [
            TokenID.NOMINATE, TokenID.PLAYER_5, TokenID.END_TURN,
            TokenID.VOTE, TokenID.PLAYER_5, TokenID.END_TURN,
            TokenID.KILL, TokenID.PLAYER_2, TokenID.END_TURN
        ]
        assert tokens == expected
    
    def test_decode_sequence(self):
        """Test decoding of action sequences."""
        tokens = [
            TokenID.NOMINATE, TokenID.PLAYER_5, TokenID.END_TURN,
            TokenID.VOTE, TokenID.PLAYER_5, TokenID.END_TURN,
            TokenID.KILL, TokenID.PLAYER_2, TokenID.END_TURN
        ]
        player_indices = [1, 2, 3]
        actions = self.encoder.decode_sequence(tokens, player_indices)
        
        assert len(actions) == 3
        assert isinstance(actions[0], NominationAction)
        assert actions[0].player_index == 1 and actions[0].target_player == 5
        assert isinstance(actions[1], VoteAction)
        assert actions[1].player_index == 2 and actions[1].target_player == 5
        assert isinstance(actions[2], KillAction)
        assert actions[2].player_index == 3 and actions[2].target_player == 2
    
    def test_validate_action_tokens(self):
        """Test token validation functionality."""
        # Valid tokens
        assert self.encoder.validate_action_tokens([TokenID.END_TURN])
        assert self.encoder.validate_action_tokens([TokenID.NOMINATE, TokenID.PLAYER_3])
        assert self.encoder.validate_action_tokens([TokenID.CLAIM_SHERIFF_CHECK, TokenID.PLAYER_2, TokenID.RED])
        
        # Invalid tokens
        assert not self.encoder.validate_action_tokens([])  # Empty
        assert not self.encoder.validate_action_tokens([TokenID.NOMINATE])  # Missing target
        assert not self.encoder.validate_action_tokens([TokenID.CLAIM_SHERIFF_CHECK, TokenID.PLAYER_2])  # Missing color
        assert not self.encoder.validate_action_tokens([TokenID.END_TURN, TokenID.PLAYER_1])  # Extra token
    
    def test_invalid_action_decoding(self):
        """Test that invalid token sequences raise appropriate errors."""
        with pytest.raises(ValueError, match="Empty token sequence"):
            self.encoder.decode_action([], 0)
        
        with pytest.raises(ValueError, match="NOMINATE requires target player"):
            self.encoder.decode_action([TokenID.NOMINATE], 0)
        
        with pytest.raises(ValueError, match="CLAIM_SHERIFF_CHECK requires target player and color"):
            self.encoder.decode_action([TokenID.CLAIM_SHERIFF_CHECK, TokenID.PLAYER_2], 0)
    
    def test_unknown_action_encoding(self):
        """Test that unknown action types raise errors."""
        class UnknownAction(Action):
            def apply(self, game_state):
                pass
        
        with pytest.raises(ValueError, match="Unknown action type"):
            self.encoder.encode_action(UnknownAction(0))


class TestConvenienceFunctions:
    """Test cases for the convenience functions."""
    
    def test_encode_action_function(self):
        """Test the standalone encode_action function."""
        action = NominationAction(2, 4)
        tokens = encode_action(action)
        assert tokens == [TokenID.NOMINATE, TokenID.PLAYER_4]
    
    def test_decode_action_function(self):
        """Test the standalone decode_action function."""
        tokens = [TokenID.VOTE, TokenID.PLAYER_7]
        action = decode_action(tokens, 3)
        assert isinstance(action, VoteAction)
        assert action.player_index == 3
        assert action.target_player == 7
    
    def test_validate_action_tokens_function(self):
        """Test the standalone validate_action_tokens function."""
        assert validate_action_tokens([TokenID.KILL, TokenID.PLAYER_1])
        assert not validate_action_tokens([TokenID.KILL])  # Missing target


if __name__ == "__main__":
    pytest.main([__file__])
