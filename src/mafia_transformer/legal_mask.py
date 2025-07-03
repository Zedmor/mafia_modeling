"""
Legal action masking logic for the Mafia transformer system.
Generates legal action masks from available actions using the token vocabulary.
"""
from typing import List, Dict, Set, Optional
import numpy as np

from mafia_game.game_state import CompleteGameState
from mafia_game.actions import Action, NullAction
from mafia_transformer.token_vocab import (
    TokenID, VOCAB_SIZE, VERB_TOKENS, PLAYER_TOKENS, COLOR_TOKENS,
    player_index_to_token, is_verb_token, is_player_token, is_color_token,
    verb_requires_target, verb_requires_player_target, verb_requires_player_color_targets,
    NO_TARGET_VERBS, PLAYER_TARGET_VERBS, PLAYER_COLOR_TARGET_VERBS
)
from mafia_transformer.token_encoder import TokenEncoder


class LegalActionMasker:
    """Generates legal action masks from available actions."""
    
    def __init__(self):
        self.encoder = TokenEncoder()
    
    def generate_legal_mask(self, game_state: CompleteGameState, player_index: int) -> np.ndarray:
        """
        Generate a legal action mask for the given game state and player.
        
        Args:
            game_state: The current game state
            player_index: Index of the player for whom to generate the mask
            
        Returns:
            Boolean mask of shape (VOCAB_SIZE,) where True indicates legal tokens
        """
        # Initialize mask - all tokens are illegal by default
        legal_mask = np.zeros(VOCAB_SIZE, dtype=bool)
        
        # Get available actions from game state
        # We need to temporarily set the active player to the requested player
        original_active_player = game_state.active_player
        game_state.active_player = player_index
        
        try:
            available_actions = game_state.get_available_actions()
        finally:
            # Restore original active player
            game_state.active_player = original_active_player
        
        # Convert available actions to legal tokens
        legal_verbs = set()
        legal_targets = set()
        
        for action in available_actions:
            # Encode the action to get its token representation
            action_tokens = self.encoder.encode_action(action)
            
            if action_tokens:
                verb_token = TokenID(action_tokens[0])
                legal_verbs.add(verb_token)
                
                # If the action has targets, mark them as legal
                if len(action_tokens) > 1:
                    for target_token_id in action_tokens[1:]:
                        target_token = TokenID(target_token_id)
                        legal_targets.add(target_token)
        
        # Mark legal verb tokens
        for verb_token in legal_verbs:
            legal_mask[verb_token] = True
        
        # For verbs that require targets, mark corresponding legal targets
        for verb_token in legal_verbs:
            if verb_token in PLAYER_TARGET_VERBS or verb_token in PLAYER_COLOR_TARGET_VERBS:
                # Get the specific targets for this verb from available actions
                verb_specific_targets = self._get_targets_for_verb(available_actions, verb_token)
                for target_token in verb_specific_targets:
                    legal_mask[target_token] = True
        
        # Always allow END_TURN as a fallback, except during voting when players must vote
        # In voting phase, players cannot abstain - they must cast a vote
        # Exception: Dead players giving speeches can always end their turn
        from mafia_game.game_state import VotingPhase
        
        player_is_dead = not game_state.game_states[player_index].alive
        if not isinstance(game_state.current_phase, VotingPhase) or player_is_dead:
            legal_mask[TokenID.END_TURN] = True
        elif not np.any(legal_mask):
            # If we're in voting phase and no actions are available, something is wrong
            raise RuntimeError("No legal actions available during voting phase - this should never happen")
        
        # Validate that the mask has at least one legal action
        if not np.any(legal_mask):
            raise RuntimeError("Legal mask is all-zero, which should never happen")
        
        return legal_mask
    
    def _get_targets_for_verb(self, available_actions: List[Action], verb_token: TokenID) -> Set[TokenID]:
        """
        Get the specific targets available for a given verb from the available actions.
        
        Args:
            available_actions: List of available actions
            verb_token: The verb token to find targets for
            
        Returns:
            Set of legal target tokens for this verb
        """
        targets = set()
        
        for action in available_actions:
            if isinstance(action, NullAction):
                continue
                
            # Encode the action and check if it starts with our verb
            action_tokens = self.encoder.encode_action(action)
            if action_tokens and TokenID(action_tokens[0]) == verb_token:
                # Add all target tokens (skip the verb token)
                for target_token_id in action_tokens[1:]:
                    targets.add(TokenID(target_token_id))
        
        return targets
    
    def generate_factorized_masks(self, game_state: CompleteGameState, player_index: int) -> Dict[str, np.ndarray]:
        """
        Generate factorized legal masks for verb and target selection.
        This is useful for transformer architectures with separate heads.
        
        Args:
            game_state: The current game state
            player_index: Index of the player for whom to generate masks
            
        Returns:
            Dictionary with 'verbs', 'players', and 'colors' masks
        """
        # Generate the full legal mask first
        full_mask = self.generate_legal_mask(game_state, player_index)
        
        # Extract factorized masks
        verb_mask = np.zeros(len(VERB_TOKENS), dtype=bool)
        player_mask = np.zeros(len(PLAYER_TOKENS), dtype=bool)
        color_mask = np.zeros(len(COLOR_TOKENS), dtype=bool)
        
        # Map tokens to factorized masks
        for token_id in range(VOCAB_SIZE):
            if full_mask[token_id]:
                token = TokenID(token_id)
                
                if is_verb_token(token):
                    verb_idx = VERB_TOKENS.index(token)
                    verb_mask[verb_idx] = True
                elif is_player_token(token):
                    player_idx = PLAYER_TOKENS.index(token)
                    player_mask[player_idx] = True
                elif is_color_token(token):
                    color_idx = COLOR_TOKENS.index(token)
                    color_mask[color_idx] = True
        
        return {
            'verbs': verb_mask,
            'players': player_mask,
            'colors': color_mask
        }
    
    def is_legal_action_sequence(self, game_state: CompleteGameState, player_index: int, 
                                token_sequence: List[int]) -> bool:
        """
        Check if a token sequence represents a legal action for the given game state.
        
        Args:
            game_state: The current game state
            player_index: Index of the player performing the action
            token_sequence: List of token IDs representing the action
            
        Returns:
            True if the action is legal, False otherwise
        """
        if not token_sequence:
            return False
        
        # First, validate that the token sequence is well-formed
        if not self.encoder.validate_action_tokens(token_sequence):
            return False
        
        try:
            # Try to decode the action
            action = self.encoder.decode_action(token_sequence, player_index)
            
            # Get available actions and check if this action is among them
            original_active_player = game_state.active_player
            game_state.active_player = player_index
            
            try:
                available_actions = game_state.get_available_actions()
            finally:
                game_state.active_player = original_active_player
            
            # Check if the decoded action matches any available action
            for available_action in available_actions:
                if self._actions_equal(action, available_action):
                    return True
            
            return False
            
        except (ValueError, RuntimeError):
            return False
    
    def _actions_equal(self, action1: Action, action2: Action) -> bool:
        """
        Check if two actions are equivalent.
        
        Args:
            action1: First action to compare
            action2: Second action to compare
            
        Returns:
            True if actions are equivalent, False otherwise
        """
        # Compare action types
        if type(action1) != type(action2):
            return False
        
        # Compare player indices
        if action1.player_index != action2.player_index:
            return False
        
        # Compare action-specific attributes
        if hasattr(action1, 'target_player') and hasattr(action2, 'target_player'):
            if action1.target_player != action2.target_player:
                return False
        
        if hasattr(action1, 'i_am_sheriff') and hasattr(action2, 'i_am_sheriff'):
            if action1.i_am_sheriff != action2.i_am_sheriff:
                return False
        
        if hasattr(action1, 'eliminate_all') and hasattr(action2, 'eliminate_all'):
            if action1.eliminate_all != action2.eliminate_all:
                return False
        
        if hasattr(action1, 'role') and hasattr(action2, 'role'):
            if action1.role != action2.role:
                return False
        
        return True


# Global masker instance
masker = LegalActionMasker()

# Convenience functions
def generate_legal_mask(game_state: CompleteGameState, player_index: int) -> np.ndarray:
    """Generate a legal action mask for the given game state and player."""
    return masker.generate_legal_mask(game_state, player_index)

def generate_factorized_masks(game_state: CompleteGameState, player_index: int) -> Dict[str, np.ndarray]:
    """Generate factorized legal masks for verb and target selection."""
    return masker.generate_factorized_masks(game_state, player_index)

def is_legal_action_sequence(game_state: CompleteGameState, player_index: int, 
                           token_sequence: List[int]) -> bool:
    """Check if a token sequence represents a legal action."""
    return masker.is_legal_action_sequence(game_state, player_index, token_sequence)
