"""
Simple test to validate the basic token encoding functionality.
"""
import sys
from pathlib import Path

from mafia_transformer.token_vocab import TokenID
from mafia_transformer.token_encoder import TokenEncoder
from mafia_game.actions import NullAction, NominationAction
from mafia_game.common import Team

def test_basic_encoding():
    """Test basic token encoding and decoding."""
    encoder = TokenEncoder()
    
    # Test NullAction
    action = NullAction(0)
    tokens = encoder.encode_action(action)
    assert tokens == [TokenID.END_TURN]
    decoded = encoder.decode_action(tokens, 0)
    assert isinstance(decoded, NullAction)
    assert decoded.player_index == 0
    
    # Test NominationAction  
    action = NominationAction(2, 5)
    tokens = encoder.encode_action(action)
    assert tokens == [TokenID.NOMINATE, TokenID.PLAYER_5]
    decoded = encoder.decode_action(tokens, 2)
    assert isinstance(decoded, NominationAction)
    assert decoded.player_index == 2
    assert decoded.target_player == 5
    
    print("All basic encoding tests passed!")

if __name__ == "__main__":
    test_basic_encoding()
