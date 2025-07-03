"""
Random agent that uses the token system for action selection.
This agent demonstrates the complete token pipeline in action with multi-action sequences.
"""
import random
import numpy as np
from typing import List
from datetime import datetime

from mafia_game.agent import Agent
from mafia_transformer.token_vocab import TokenID, TOKEN_ID_TO_NAME
from mafia_transformer.token_encoder import encode_action, decode_action
from mafia_transformer.legal_mask import generate_legal_mask
from mafia_transformer.token_game_interface import TokenGameInterface, TokenGameState


class TokenRandomAgent(Agent):
    """Random agent that selects actions using the token system."""
    
    def __init__(self, game_state, log_file_path: str = None):
        super().__init__(game_state)
        self.log_file_path = log_file_path
        self.action_count = 0
        
    def log_to_file(self, message: str):
        """Log a message to the agent's log file."""
        if self.log_file_path:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
    
    def get_action(self, player_index: int):
        """Get action using token-based random selection with multi-action sequences for day phases."""
        self.action_count += 1
        
        # Log what the agent observes
        self.log_to_file("=" * 60)
        self.log_to_file(f"ACTION REQUEST #{self.action_count} for Player {player_index}")
        self.log_to_file("=" * 60)
        
        # Log current game state information
        current_phase = self.game_state.current_phase.__class__.__name__
        turn = self.game_state.turn
        is_day_phase = "Day" in current_phase and "Voting" not in current_phase
        
        self.log_to_file(f"🎮 GAME STATE:")
        self.log_to_file(f"   Phase: {current_phase}")
        self.log_to_file(f"   Turn: {turn}")
        self.log_to_file(f"   Is Day Phase: {is_day_phase}")
        
        # FOR DAY PHASES: Build multi-action sequences using TokenGameInterface
        if is_day_phase:
            self.log_to_file(f"🎯 DAY PHASE - Building multi-action token sequence")
            
            try:
                # Create a TokenGameInterface to get proper legal actions for day phases
                interface = TokenGameInterface()
                
                # Create a mock token state (simplified - the actual implementation would need proper state)
                # For now, get available actions and convert to tokens
                available_actions = self.game_state.get_available_actions()
                
                # Convert to token actions and filter day actions (remove ALL END_TURN tokens)
                day_action_tokens = []
                for action in available_actions:
                    action_tokens = encode_action(action)
                    # Remove ALL END_TURN tokens from the sequence to get pure action tokens
                    pure_action = [t for t in action_tokens if t != TokenID.END_TURN.value]
                    
                    if pure_action:  # Only add non-empty actions
                        day_action_tokens.append(pure_action)
                
                self.log_to_file(f"   Available day action tokens: {len(day_action_tokens)}")
                for i, action_tokens in enumerate(day_action_tokens):
                    token_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in action_tokens]
                    self.log_to_file(f"   {i+1}. {' '.join(token_names)}")
                
                # Separate nominations from other actions to enforce nomination limit
                nomination_actions = []
                other_actions = []
                
                for action_tokens in day_action_tokens:
                    if action_tokens and action_tokens[0] == TokenID.NOMINATE.value:
                        nomination_actions.append(action_tokens)
                    else:
                        other_actions.append(action_tokens)
                
                self.log_to_file(f"   Available nominations: {len(nomination_actions)}")
                self.log_to_file(f"   Available other actions: {len(other_actions)}")
                
                # Generate random multi-action sequence (0-7 actions)
                max_actions = min(7, len(day_action_tokens))
                num_actions = random.randint(0, max_actions)
                self.log_to_file(f"   Choosing {num_actions} actions for sequence")
                
                if num_actions == 0:
                    # Just END_TURN
                    token_sequence = [TokenID.END_TURN.value]
                    self.log_to_file(f"   Generated sequence: <END_TURN>")
                else:
                    # Build action sequence with nomination limit enforcement
                    chosen_actions = []
                    nominations_used = 0
                    
                    # Decide how many of each type to include
                    remaining_actions = num_actions
                    
                    # Maybe include 1 nomination (30% chance if nominations available)
                    if (nomination_actions and remaining_actions > 0 and 
                        random.random() < 0.3):
                        chosen_nomination = random.choice(nomination_actions)
                        chosen_actions.append(chosen_nomination)
                        nominations_used = 1
                        remaining_actions -= 1
                        self.log_to_file(f"   Added nomination: {[TOKEN_ID_TO_NAME.get(t, f'UNK_{t}') for t in chosen_nomination]}")
                    
                    # Fill remaining slots with other actions
                    if remaining_actions > 0 and other_actions:
                        num_other = min(remaining_actions, len(other_actions))
                        if num_other > 0:
                            chosen_other = random.sample(other_actions, num_other)
                            chosen_actions.extend(chosen_other)
                            self.log_to_file(f"   Added {len(chosen_other)} other actions")
                    
                    # Build the token sequence - ensure no internal END_TURN tokens
                    token_sequence = []
                    for action_tokens in chosen_actions:
                        # Double-check: remove any END_TURN tokens from individual actions
                        clean_tokens = [t for t in action_tokens if t != TokenID.END_TURN.value]
                        token_sequence.extend(clean_tokens)
                    
                    # Add single END_TURN at the end
                    token_sequence.append(TokenID.END_TURN.value)
                    
                    # Log the sequence
                    sequence_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in token_sequence]
                    self.log_to_file(f"   Generated sequence: {' '.join(sequence_names)}")
                    
                    # Verify nomination limit (safety check)
                    nomination_count = sum(1 for action in chosen_actions 
                                         if action and action[0] == TokenID.NOMINATE.value)
                    self.log_to_file(f"   Nomination count in sequence: {nomination_count}")
                    
                    if nomination_count > 1:
                        self.log_to_file(f"   ⚠️  WARNING: Multiple nominations detected, using fallback")
                        # Fallback: just pick one non-nomination action + END_TURN
                        if other_actions:
                            fallback_action = random.choice(other_actions)
                            # Ensure no END_TURN in the fallback action
                            clean_fallback = [t for t in fallback_action if t != TokenID.END_TURN.value]
                            token_sequence = clean_fallback + [TokenID.END_TURN.value]
                        else:
                            token_sequence = [TokenID.END_TURN.value]
                
                # Return the token sequence for day phases
                self.log_to_file(f"📤 SENDING TOKEN SEQUENCE: {token_sequence}")
                return token_sequence
                
            except Exception as e:
                self.log_to_file(f"❌ ERROR building multi-action sequence: {e}")
                # Fallback to single action
                available_actions = self.game_state.get_available_actions()
                if available_actions:
                    chosen_action = random.choice(available_actions)
                    self.log_to_file(f"🔄 FALLBACK: Chose single action: {chosen_action}")
                    return chosen_action
                else:
                    return None
        
        # FOR NON-DAY PHASES: Use original single-action approach
        else:
            self.log_to_file(f"🎯 NON-DAY PHASE - Using single action")
            
            # Get available actions through the game engine
            available_actions = self.game_state.get_available_actions()
            self.log_to_file(f"🎲 AVAILABLE ACTIONS ({len(available_actions)}):")
            for i, action in enumerate(available_actions):
                action_tokens = encode_action(action)
                token_names = [TOKEN_ID_TO_NAME.get(t, f"UNK_{t}") for t in action_tokens]
                verb_display = " ".join(token_names)
                self.log_to_file(f"   {i+1}. {verb_display} → {action_tokens}")
            
            if not available_actions:
                self.log_to_file("❌ No available actions!")
                return None
            
            # Choose random action
            chosen_action = random.choice(available_actions)
            
            # Encode to tokens for logging
            action_tokens = encode_action(chosen_action)
            token_names = [TOKEN_ID_TO_NAME.get(t, f"UNKNOWN_{t}") for t in action_tokens]
            
            self.log_to_file(f"🎯 SELECTED ACTION:")
            self.log_to_file(f"   Action Object: {chosen_action}")
            self.log_to_file(f"   Token Sequence: {action_tokens}")
            self.log_to_file(f"   Token Names: {token_names}")
            
            self.log_to_file(f"📤 SENDING ACTION: {chosen_action}")
            self.log_to_file("")  # Empty line for readability
            
            return chosen_action
    
    def utterance(self, player_index: int):
        """Handle final utterance when player is eliminated."""
        self.log_to_file("=" * 60)
        self.log_to_file(f"💀 PLAYER {player_index} ELIMINATED - FINAL UTTERANCE")
        self.log_to_file("=" * 60)
        player_role = self.game_state.game_states[player_index].private_data.role
        self.log_to_file(f"Player {player_index} ({player_role.name}) has been eliminated from the game.")
        self.log_to_file("No further actions will be taken by this player.")
        self.log_to_file("")
