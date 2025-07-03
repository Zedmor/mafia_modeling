"""
Token encoding and decoding utilities for converting between Action classes and tokens.
"""
from typing import List, Optional, Union, Dict, Any

from mafia_game.actions import (
    Action, NullAction, KillAction, NominationAction, 
    DonCheckAction, SheriffCheckAction, SheriffDeclarationAction,
    PublicSheriffDeclarationAction, VoteAction, EliminateAllNominatedVoteAction,
    SayAction
)
from mafia_game.common import Team, Role
from mafia_transformer.token_vocab import (
    TokenID, VERB_TOKENS, PLAYER_TOKENS, COLOR_TOKENS,
    player_index_to_token, token_to_player_index,
    verb_requires_target, verb_requires_player_target,
    verb_requires_player_color_targets, NO_TARGET_VERBS,
    PLAYER_TARGET_VERBS, PLAYER_COLOR_TARGET_VERBS
)


class TokenEncoder:
    """Handles encoding/decoding between Action classes and token sequences."""
    
    def encode_action(self, action: Action) -> List[int]:
        """
        Convert an Action instance to a list of token IDs.
        
        Args:
            action: Action instance to encode
            
        Returns:
            List of token IDs representing the action
        """
        if isinstance(action, NullAction):
            return [TokenID.END_TURN]
            
        elif isinstance(action, NominationAction):
            return [TokenID.NOMINATE, player_index_to_token(action.target_player)]
            
        elif isinstance(action, VoteAction):
            return [TokenID.VOTE, player_index_to_token(action.target_player)]
            
        elif isinstance(action, KillAction):
            return [TokenID.KILL, player_index_to_token(action.target_player)]
            
        elif isinstance(action, SheriffCheckAction):
            return [TokenID.SHERIFF_CHECK, player_index_to_token(action.target_player)]
            
        elif isinstance(action, DonCheckAction):
            return [TokenID.DON_CHECK, player_index_to_token(action.target_player)]
            
        elif isinstance(action, SheriffDeclarationAction):
            if action.i_am_sheriff:
                return [TokenID.CLAIM_SHERIFF]
            else:
                return [TokenID.DENY_SHERIFF]
                
        elif isinstance(action, PublicSheriffDeclarationAction):
            color_token = TokenID.RED if action.role == Team.RED_TEAM else TokenID.BLACK
            return [
                TokenID.CLAIM_SHERIFF_CHECK,
                player_index_to_token(action.target_player),
                color_token
            ]
            
        elif isinstance(action, EliminateAllNominatedVoteAction):
            if action.eliminate_all:
                return [TokenID.VOTE_ELIMINATE_ALL]
            else:
                return [TokenID.VOTE_KEEP_ALL]
                
        elif isinstance(action, SayAction):
            color_token = TokenID.RED if action.team == Team.RED_TEAM else TokenID.BLACK
            return [
                TokenID.SAY,
                player_index_to_token(action.target_player),
                color_token
            ]
                
        else:
            raise ValueError(f"Unknown action type: {type(action)}")
    
    def decode_action(self, token_ids: List[int], player_index: int) -> Action:
        """
        Convert a list of token IDs back to an Action instance.
        Handles both day phase actions (without END_TURN) and other phase actions (with END_TURN).
        
        Args:
            token_ids: List of token IDs representing the action
            player_index: Index of the player performing the action
            
        Returns:
            Action instance
        """
        if not token_ids:
            raise ValueError("Empty token sequence")
        
        # Check if it's just END_TURN (NullAction)
        if len(token_ids) == 1 and token_ids[0] == TokenID.END_TURN.value:
            return NullAction(player_index)
        
        # Handle actions that may or may not end with END_TURN
        action_tokens = token_ids[:]
        
        # If the sequence ends with END_TURN, remove it for processing
        if token_ids[-1] == TokenID.END_TURN.value:
            action_tokens = token_ids[:-1]
            
            if not action_tokens:
                raise ValueError("Action sequence cannot be empty after removing END_TURN")
        
        # If no action tokens remain, this is invalid
        if not action_tokens:
            raise ValueError("Empty action sequence")
            
        verb_token = TokenID(action_tokens[0])
            
        if verb_token == TokenID.NOMINATE:
            if len(action_tokens) < 2:
                raise ValueError("NOMINATE requires target player")
            target_player = token_to_player_index(TokenID(action_tokens[1]))
            return NominationAction(player_index, target_player)
            
        elif verb_token == TokenID.VOTE:
            if len(action_tokens) < 2:
                raise ValueError("VOTE requires target player")
            target_player = token_to_player_index(TokenID(action_tokens[1]))
            return VoteAction(player_index, target_player)
            
        elif verb_token == TokenID.KILL:
            if len(action_tokens) < 2:
                raise ValueError("KILL requires target player")
            target_player = token_to_player_index(TokenID(action_tokens[1]))
            return KillAction(player_index, target_player)
            
        elif verb_token == TokenID.SHERIFF_CHECK:
            if len(action_tokens) < 2:
                raise ValueError("SHERIFF_CHECK requires target player")
            target_player = token_to_player_index(TokenID(action_tokens[1]))
            return SheriffCheckAction(player_index, target_player)
            
        elif verb_token == TokenID.DON_CHECK:
            if len(action_tokens) < 2:
                raise ValueError("DON_CHECK requires target player")
            target_player = token_to_player_index(TokenID(action_tokens[1]))
            return DonCheckAction(player_index, target_player)
            
        elif verb_token == TokenID.CLAIM_SHERIFF:
            return SheriffDeclarationAction(player_index, True)
            
        elif verb_token == TokenID.DENY_SHERIFF:
            return SheriffDeclarationAction(player_index, False)
            
        elif verb_token == TokenID.CLAIM_SHERIFF_CHECK:
            if len(action_tokens) < 3:
                raise ValueError("CLAIM_SHERIFF_CHECK requires target player and color")
            target_player = token_to_player_index(TokenID(action_tokens[1]))
            color_token = TokenID(action_tokens[2])
            if color_token == TokenID.RED:
                team = Team.RED_TEAM
            elif color_token == TokenID.BLACK:
                team = Team.BLACK_TEAM
            else:
                raise ValueError(f"Invalid color token for CLAIM_SHERIFF_CHECK: {color_token}")
            return PublicSheriffDeclarationAction(player_index, target_player, team)
            
        elif verb_token == TokenID.VOTE_ELIMINATE_ALL:
            return EliminateAllNominatedVoteAction(player_index, True)
            
        elif verb_token == TokenID.VOTE_KEEP_ALL:
            return EliminateAllNominatedVoteAction(player_index, False)
            
        elif verb_token == TokenID.SAY:
            if len(action_tokens) < 3:
                raise ValueError("SAY requires target player and color")
            target_player = token_to_player_index(TokenID(action_tokens[1]))
            color_token = TokenID(action_tokens[2])
            if color_token == TokenID.RED:
                team = Team.RED_TEAM
            elif color_token == TokenID.BLACK:
                team = Team.BLACK_TEAM
            else:
                raise ValueError(f"Invalid color token for SAY: {color_token}")
            return SayAction(player_index, target_player, team)
            
        else:
            raise ValueError(f"Unknown verb token: {verb_token}")
    
    def encode_sequence(self, actions: List[Action]) -> List[int]:
        """
        Encode a sequence of actions into token IDs.
        
        Args:
            actions: List of Action instances
            
        Returns:
            List of token IDs with END_TURN tokens separating actions
        """
        token_sequence = []
        for action in actions:
            action_tokens = self.encode_action(action)
            token_sequence.extend(action_tokens)
            # Add END_TURN if not already present
            if not action_tokens or action_tokens[-1] != TokenID.END_TURN:
                token_sequence.append(TokenID.END_TURN)
        return token_sequence
    
    def decode_sequence(self, token_ids: List[int], player_indices: List[int]) -> List[Action]:
        """
        Decode a sequence of token IDs back to actions.
        
        Args:
            token_ids: List of token IDs
            player_indices: List of player indices (one per action)
            
        Returns:
            List of Action instances
        """
        actions = []
        i = 0
        player_idx = 0
        
        while i < len(token_ids) and player_idx < len(player_indices):
            if token_ids[i] == TokenID.END_TURN:
                # Skip lone END_TURN tokens
                i += 1
                continue
                
            # Find the next END_TURN or end of sequence
            action_start = i
            while i < len(token_ids) and token_ids[i] != TokenID.END_TURN:
                i += 1
            
            # Decode the action tokens
            action_tokens = token_ids[action_start:i]
            if action_tokens:
                try:
                    action = self.decode_action(action_tokens, player_indices[player_idx])
                    actions.append(action)
                    player_idx += 1
                except ValueError as e:
                    # Skip invalid action sequences
                    print(f"Warning: Failed to decode action {action_tokens}: {e}")
                    
            # Skip the END_TURN token
            if i < len(token_ids):
                i += 1
                
        return actions
    
    def validate_action_tokens(self, token_ids: List[int]) -> bool:
        """
        Validate that a token sequence represents a valid action.
        Handles both day phase actions (without END_TURN) and other phase actions (with END_TURN).
        
        Args:
            token_ids: List of token IDs to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not token_ids:
            return False
        
        # Check if it's just END_TURN (valid NullAction)
        if len(token_ids) == 1 and token_ids[0] == TokenID.END_TURN.value:
            return True
        
        # Handle actions that may or may not end with END_TURN
        action_tokens = token_ids[:]
        
        # If the sequence ends with END_TURN, remove it for validation
        if token_ids[-1] == TokenID.END_TURN.value:
            action_tokens = token_ids[:-1]
            
            if not action_tokens:
                return False  # Empty action part is invalid
        
        # If no action tokens remain, this is invalid
        if not action_tokens:
            return False
            
        try:
            verb_token = TokenID(action_tokens[0])
        except ValueError:
            return False
            
        if verb_token not in VERB_TOKENS:
            return False
            
        # Check argument count for the action part (without END_TURN)
        if verb_token in NO_TARGET_VERBS:
            return len(action_tokens) == 1
        elif verb_token in PLAYER_TARGET_VERBS:
            if len(action_tokens) != 2:
                return False
            try:
                target_token = TokenID(action_tokens[1])
                return target_token in PLAYER_TOKENS
            except ValueError:
                return False
        elif verb_token in PLAYER_COLOR_TARGET_VERBS:
            if len(action_tokens) != 3:
                return False
            try:
                target_token = TokenID(action_tokens[1])
                color_token = TokenID(action_tokens[2])
                return target_token in PLAYER_TOKENS and color_token in COLOR_TOKENS
            except ValueError:
                return False
        
        return False


# Global encoder instance
encoder = TokenEncoder()

# Convenience functions
def encode_action(action: Action) -> List[int]:
    """Encode a single action to token IDs."""
    return encoder.encode_action(action)

def decode_action(token_ids: List[int], player_index: int) -> Action:
    """Decode token IDs to a single action."""
    return encoder.decode_action(token_ids, player_index)

def encode_sequence(actions: List[Action]) -> List[int]:
    """Encode a sequence of actions to token IDs."""
    return encoder.encode_sequence(actions)

def decode_sequence(token_ids: List[int], player_indices: List[int]) -> List[Action]:
    """Decode token IDs to a sequence of actions."""
    return encoder.decode_sequence(token_ids, player_indices)

def validate_action_tokens(token_ids: List[int]) -> bool:
    """Validate that token IDs represent a valid action."""
    return encoder.validate_action_tokens(token_ids)
