"""
Token-based Mafia Game Server for UAT testing.
Manages game state and communicates entirely through tokens.
"""

import json
import os
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from mafia_transformer.token_game_interface import TokenGameInterface, TokenGameState, create_token_game
from mafia_transformer.token_vocab import TokenID


def format_tokens(tokens: List[int]) -> str:
    """Format a list of token IDs in a readable way: <TOKEN_NAME> <TOKEN_NAME>"""
    formatted = []
    for token in tokens:
        if isinstance(token, TokenID):
            formatted.append(f"<{token.name}>")
        elif isinstance(token, int):
            # Check if it's a seed token (range 1000+)
            if token >= 1000 and token < 2000:
                # Format seed as 4-digit number
                seed_value = token - 1000
                formatted.append(f"<{seed_value:04d}>")
            else:
                # Try to find the TokenID enum value
                try:
                    token_id = TokenID(token)
                    formatted.append(f"<{token_id.name}>")
                except ValueError:
                    # If it's not a valid TokenID, just show the number
                    formatted.append(f"<{token}>")
        else:
            formatted.append(f"<{token}>")
    
    return " ".join(formatted)


def format_tokens_readable(tokens: List[int]) -> str:
    """
    Format tokens with human-readable structure:
    - Handle game setup sequences (GAME_START, role assignments, etc.)
    - Handle standalone action sequences (client requests)
    - Group by phases (DAY_1, NIGHT_1, etc.)
    - Group by players within each phase
    - Add line breaks for better readability
    """
    if not tokens:
        return ""
    
    # Check if this is a setup sequence or standalone action sequence
    has_setup_tokens = any(tokens[i] in [TokenID.GAME_START.value, TokenID.YOUR_ROLE.value, TokenID.MAFIA_TEAM.value] for i in range(len(tokens)))
    
    # If no setup tokens, treat as standalone action sequence
    if not has_setup_tokens:
        return format_standalone_action_sequence(tokens)
    
    # Otherwise, use the full game state formatting
    formatted = []
    current_phase = None
    current_player = None
    current_action = []
    
    def flush_current_action():
        if current_player is not None and current_action:
            action_line = f"  Player {current_player}: " + " ".join(current_action)
            formatted.append(action_line)
            current_action.clear()
    
    def flush_phase():
        flush_current_action()
        if current_phase:
            formatted.append("")  # Empty line between phases
    
    # Action tokens that start new commands
    ACTION_STARTERS = {
        'SAY', 'CLAIM_SHERIFF_CHECK', 'CLAIM_SHERIFF', 'DENY_SHERIFF', 
        'NOMINATE', 'VOTE', 'NIGHT_ACTION', 'END_TURN'
    }
    
    # Special setup tokens that should be handled differently
    SETUP_TOKENS = {'GAME_START', 'YOUR_ROLE', 'MAFIA_TEAM'}
    ROLE_TOKENS = {'DON', 'MAFIA', 'SHERIFF', 'CITIZEN'}
    
    i = 0
    in_setup_phase = True  # Start assuming we're in setup phase
    
    while i < len(tokens):
        token = tokens[i]
        
        try:
            token_id = TokenID(token)
        except ValueError:
            # Handle non-enum tokens (like seeds)
            if token >= 1000 and token < 2000:
                seed_value = token - 1000
                token_name = f"SEED_{seed_value:04d}"
                if in_setup_phase:
                    formatted.append(f"Game Setup - Seed: {seed_value}")
                else:
                    current_action.append(f"<{seed_value:04d}>")
            else:
                token_name = f"<{token}>"
                current_action.append(token_name)
            i += 1
            continue
        
        token_name = token_id.name
        
        # Handle setup phase tokens
        if in_setup_phase and token_id.name in SETUP_TOKENS:
            if token_id.name == 'GAME_START':
                formatted.append("=== GAME SETUP ===")
                i += 1
                continue
            elif token_id.name == 'YOUR_ROLE':
                # Look ahead for the role
                if i + 1 < len(tokens):
                    try:
                        role_token = TokenID(tokens[i + 1])
                        if role_token.name in ROLE_TOKENS:
                            formatted.append(f"Player Role: {role_token.name}")
                            i += 2  # Skip both YOUR_ROLE and the role token
                            continue
                    except ValueError:
                        pass
                formatted.append(f"Player Role: (unknown)")
                i += 1
                continue
            elif token_id.name == 'MAFIA_TEAM':
                # Collect team members
                team_members = []
                j = i + 1
                while j < len(tokens):
                    try:
                        next_token = TokenID(tokens[j])
                        if next_token.name.startswith('PLAYER_'):
                            player_num = next_token.name.split('_')[1]
                            team_members.append(f"Player {player_num}")
                            j += 1
                        else:
                            break
                    except ValueError:
                        break
                
                if team_members:
                    formatted.append(f"Mafia Team: {', '.join(team_members)}")
                else:
                    formatted.append("Mafia Team: (empty)")
                
                i = j  # Move past all team member tokens
                continue
        
        # Handle PLAYER_X in setup phase (player identity)
        if in_setup_phase and token_id.name.startswith('PLAYER_'):
            player_num = token_id.name.split('_')[1]
            formatted.append(f"Playing as: Player {player_num}")
            i += 1
            continue
        
        # Check for phase tokens - this ends setup phase
        if token_id.name.startswith(('DAY_', 'NIGHT_')):
            in_setup_phase = False
            flush_phase()
            current_phase = token_id.name
            formatted.append(f"\n=== {current_phase} ===")
            current_player = None
            i += 1
            continue
        
        # Handle NEXT_TURN token
        if token_id.name == 'NEXT_TURN':
            if in_setup_phase:
                formatted.append("Ready for first turn")
            else:
                formatted.append("  → Your turn to act")
            i += 1
            continue
        
        # Handle phase transition tokens
        if token_id.name == 'VOTING_PHASE_START':
            formatted.append("🗳️  VOTING PHASE START")
            i += 1
            continue
        elif token_id.name == 'NIGHT_PHASE_START':
            formatted.append("🌙 NIGHT PHASE START")
            i += 1
            continue
        elif token_id.name == 'DAY_PHASE_START':
            formatted.append("☀️  DAY PHASE START")
            i += 1
            continue
        elif token_id.name == 'YOUR_TURN':
            formatted.append("  → Your turn")
            i += 1
            continue
        
        # End setup phase when we hit the first non-setup token
        if in_setup_phase:
            in_setup_phase = False
        
        # Check for player tokens that might be action starters
        if token_id.name.startswith('PLAYER_'):
            player_num = int(token_id.name.split('_')[1])
            
            # Look ahead to see if this is followed by an action starter
            is_action_starter = False
            if i + 1 < len(tokens):
                try:
                    next_token_id = TokenID(tokens[i + 1])
                    if next_token_id.name in ACTION_STARTERS:
                        is_action_starter = True
                except ValueError:
                    pass
            
            # If this PLAYER_X is followed by an action, it's a new action by that player
            if is_action_starter:
                flush_current_action()
                current_player = player_num
                i += 1  # Skip the PLAYER_X token since it's just marking the actor
                continue
            else:
                # This PLAYER_X is a parameter (like target of an action)
                current_action.append(f"<{token_name}>")
                i += 1
                continue
        
        # Check for action starter tokens
        if token_id.name in ACTION_STARTERS:
            # If we have a current action in progress, finish it first
            if current_action:
                flush_current_action()
            
            # Parse action with proper arguments for better readability
            if token_id.name == 'NOMINATE' and i + 1 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    if target_token.name.startswith('PLAYER_'):
                        target_player = target_token.name.replace('PLAYER_', '')
                        current_action.append(f"<NOMINATE> Player {target_player}")
                        i += 1  # Skip the target token since we consumed it
                        i += 1  # Move to next token
                        continue
                except ValueError:
                    pass
            elif token_id.name == 'SAY' and i + 2 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    color_token = TokenID(tokens[i + 2])
                    if target_token.name.startswith('PLAYER_') and color_token.name in ['RED', 'BLACK']:
                        target_player = target_token.name.replace('PLAYER_', '')
                        color = color_token.name.lower()
                        current_action.append(f"<SAY> Player {target_player} is {color}")
                        i += 2  # Skip both target and color tokens
                        i += 1  # Move to next token
                        continue
                except ValueError:
                    pass
            elif token_id.name == 'CLAIM_SHERIFF_CHECK' and i + 2 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    color_token = TokenID(tokens[i + 2])
                    if target_token.name.startswith('PLAYER_') and color_token.name in ['RED', 'BLACK']:
                        target_player = target_token.name.replace('PLAYER_', '')
                        color = color_token.name.lower()
                        current_action.append(f"<CLAIM_SHERIFF_CHECK> Player {target_player} is {color}")
                        i += 2  # Skip both target and color tokens
                        i += 1  # Move to next token
                        continue
                except ValueError:
                    pass
            elif token_id.name == 'VOTE' and i + 1 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    if target_token.name.startswith('PLAYER_'):
                        target_player = target_token.name.replace('PLAYER_', '')
                        current_action.append(f"<VOTE> Player {target_player}")
                        i += 1  # Skip the target token
                        i += 1  # Move to next token
                        continue
                except ValueError:
                    pass
            
            # Fallback for other action tokens or if parsing failed
            current_action.append(f"<{token_name}>")
        else:
            # Regular parameter tokens
            current_action.append(f"<{token_name}>")
        
        i += 1
    
    # Flush any remaining action
    flush_current_action()
    
    return "\n".join(formatted)


def format_standalone_action_sequence(tokens: List[int]) -> str:
    """
    Format a standalone action sequence (like client requests) in readable form.
    
    Args:
        tokens: List of token IDs representing an action sequence
        
    Returns:
        Human-readable string describing the actions
    """
    if not tokens:
        return ""
    
    formatted = []
    i = 0
    
    while i < len(tokens):
        token = tokens[i]
        
        try:
            token_id = TokenID(token)
        except ValueError:
            # Handle unknown tokens
            formatted.append(f"Unknown token: {token}")
            i += 1
            continue
        
        token_name = token_id.name
        
        # Handle different action types
        if token_name == 'SAY':
            if i + 2 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    color_token = TokenID(tokens[i + 2])
                    target_player = target_token.name.replace('PLAYER_', '')
                    color = color_token.name.lower()
                    formatted.append(f"Say Player {target_player} is {color}")
                    i += 3
                    continue
                except ValueError:
                    pass
        
        elif token_name == 'NOMINATE':
            if i + 1 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    target_player = target_token.name.replace('PLAYER_', '')
                    formatted.append(f"Nominate Player {target_player}")
                    i += 2
                    continue
                except ValueError:
                    pass
        
        elif token_name == 'CLAIM_SHERIFF_CHECK':
            if i + 2 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    color_token = TokenID(tokens[i + 2])
                    target_player = target_token.name.replace('PLAYER_', '')
                    color = color_token.name.lower()
                    formatted.append(f"Claim sheriff check: Player {target_player} is {color}")
                    i += 3
                    continue
                except ValueError:
                    pass
        
        elif token_name == 'VOTE':
            if i + 1 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    target_player = target_token.name.replace('PLAYER_', '')
                    formatted.append(f"Vote against Player {target_player}")
                    i += 2
                    continue
                except ValueError:
                    pass
        
        elif token_name == 'KILL':
            if i + 1 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    target_player = target_token.name.replace('PLAYER_', '')
                    formatted.append(f"Kill Player {target_player}")
                    i += 2
                    continue
                except ValueError:
                    pass
        
        elif token_name == 'SHERIFF_CHECK':
            if i + 1 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    target_player = target_token.name.replace('PLAYER_', '')
                    formatted.append(f"Sheriff check Player {target_player}")
                    i += 2
                    continue
                except ValueError:
                    pass
        
        elif token_name == 'DON_CHECK':
            if i + 1 < len(tokens):
                try:
                    target_token = TokenID(tokens[i + 1])
                    target_player = target_token.name.replace('PLAYER_', '')
                    formatted.append(f"Don check Player {target_player}")
                    i += 2
                    continue
                except ValueError:
                    pass
        
        elif token_name == 'CLAIM_SHERIFF':
            formatted.append("Claim to be sheriff")
            i += 1
            continue
        
        elif token_name == 'DENY_SHERIFF':
            formatted.append("Deny being sheriff")
            i += 1
            continue
        
        elif token_name == 'END_TURN':
            formatted.append("End turn")
            i += 1
            continue
        
        elif token_name == 'VOTE_ELIMINATE_ALL':
            formatted.append("Vote to eliminate all tied players")
            i += 1
            continue
        
        elif token_name == 'VOTE_KEEP_ALL':
            formatted.append("Vote to keep all tied players")
            i += 1
            continue
        
        else:
            # Fallback for other tokens
            formatted.append(f"<{token_name}>")
            i += 1
    
    if formatted:
        return " → ".join(formatted)
    else:
        return "(Empty action sequence)"


@dataclass
class PlayerStateTokens:
    """Token representation of game state for a specific player."""
    player_id: int
    seed_tokens: List[int]
    chronological_history: List[int]  # Complete game history with phase markers
    private_state: List[int]
    active_player: int
    is_active: bool  # True if this player should act now
    
    # Backward compatibility properties
    @property
    def public_history(self) -> List[int]:
        """Extract public history from chronological history (everything except phase markers)."""
        from mafia_transformer.token_vocab import PHASE_TOKENS
        return [token for token in self.chronological_history if token not in PHASE_TOKENS]
    
    @property
    def phase_tokens(self) -> List[int]:
        """Extract current phase from chronological history."""
        from mafia_transformer.token_vocab import PHASE_TOKENS
        # Get the last phase token in the chronological history
        for token in reversed(self.chronological_history):
            if token in PHASE_TOKENS:
                return [token]
        return []  # No phase found


@dataclass 
class ServerResponse:
    """Server response to client request."""
    success: bool
    player_state: Optional[PlayerStateTokens]
    legal_actions: List[List[int]]
    game_finished: bool
    winner: Optional[str]
    error_message: Optional[str]


class TokenGameServer:
    """
    Token-based game server that manages game state and communicates 
    entirely through tokens with test clients.
    """
    
    def __init__(self, seed: int = 42, log_file: Optional[str] = None, console_quiet: bool = False, traffic_log_dir: Optional[str] = None, show_legal_actions: bool = False):
        self.interface = create_token_game()
        self.current_state: Optional[TokenGameState] = None
        self.seed = seed
        self.log_file = log_file
        self.console_quiet = console_quiet
        self.turn_count = 0
        self.action_count = 0
        self.traffic_log_dir = traffic_log_dir
        self.traffic_sequence = 0
        self.show_legal_actions = show_legal_actions  # Control whether to show legal actions in incremental logs
        
        # Track player state history for incremental logging
        self.player_last_seen_history: Dict[int, List[int]] = {}  # player_id -> last seen chronological history
        self.player_complete_history_files: Dict[int, str] = {}  # player_id -> complete history file path
        
        # Initialize logging
        if log_file:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"MAFIA TOKEN GAME SERVER LOG\n")
                f.write(f"Started: {datetime.now()}\n")
                f.write(f"Seed: {seed}\n")
                f.write("="*60 + "\n\n")
        
        # Initialize traffic logging with per-player files
        if traffic_log_dir:
            import os
            os.makedirs(traffic_log_dir, exist_ok=True)
            self.traffic_log_dir = traffic_log_dir
            self.traffic_log_files = {}  # Will store file paths per player
            
            # Create master traffic log for reference
            self.master_traffic_log = os.path.join(traffic_log_dir, "token_traffic_master.log")
            with open(self.master_traffic_log, 'w', encoding='utf-8') as f:
                f.write(f"MASTER TOKEN TRAFFIC LOG - Seed {seed}\n")
                f.write(f"Started: {datetime.now()}\n")
                f.write("="*80 + "\n")
                f.write("This is a master index. Individual player traffic is in separate files:\n")
                f.write("- token_traffic_player_0.log through token_traffic_player_9.log\n")
                f.write("Each file contains only that player's LLM interactions.\n")
                f.write("="*80 + "\n\n")
        else:
            self.traffic_log_dir = None
            self.traffic_log_files = {}
            self.master_traffic_log = None
    
    def _log(self, message: str, console_only: bool = False):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        
        # Always log to file (unless console_only=True)
        if self.log_file and not console_only:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + "\n")
        
        # Only print to console if not in quiet mode, or if it's a high-level message
        if not self.console_quiet:
            print(f"🖥️  SERVER: {log_entry}")
    
    def _log_game_flow(self, message: str):
        """Log high-level game flow message (always shown in console)."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        
        # Log to file
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + "\n")
        
        # Always show game flow in console
        print(f"🎮 GAME: {log_entry}")
    
    def _log_traffic(self, direction: str, player_id: int, message: str, raw_tokens: List[int] = None, legal_actions: List[List[int]] = None):
        """Log raw token traffic with incremental updates and complete game history files."""
        if not self.traffic_log_dir:
            return
            
        # Create player-specific log file if it doesn't exist
        if player_id not in self.traffic_log_files:
            player_log_path = os.path.join(self.traffic_log_dir, f"token_traffic_player_{player_id}.log")
            self.traffic_log_files[player_id] = player_log_path
            
            # Initialize the player's traffic log file
            with open(player_log_path, 'w', encoding='utf-8') as f:
                f.write(f"INCREMENTAL TOKEN TRAFFIC LOG - Player {player_id} - Seed {self.seed}\n")
                f.write(f"Started: {datetime.now()}\n")
                f.write("="*80 + "\n")
                f.write(f"This log shows ONLY incremental changes since Player {player_id}'s last turn.\n")
                f.write("Complete game history is in complete_game_history_player_X.log files.\n")
                f.write("="*80 + "\n\n")
            
            # Initialize complete game history file
            complete_history_path = os.path.join(self.traffic_log_dir, f"complete_game_history_player_{player_id}.log")
            self.player_complete_history_files[player_id] = complete_history_path
            with open(complete_history_path, 'w', encoding='utf-8') as f:
                f.write(f"COMPLETE GAME HISTORY - Player {player_id} - Seed {self.seed}\n")
                f.write(f"Started: {datetime.now()}\n")
                f.write("="*80 + "\n")
                f.write(f"This log contains the complete token sequence for Player {player_id}.\n")
                f.write("For incremental updates, see token_traffic_player_X.log files.\n")
                f.write("="*80 + "\n\n")
            
            # Initialize player's last seen history
            self.player_last_seen_history[player_id] = []
        
        self.traffic_sequence += 1
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        if direction == "SERVER_TO_CLIENT" and raw_tokens:
            # For server responses, calculate incremental changes
            last_seen = self.player_last_seen_history.get(player_id, [])
            
            # Extract the game state portion (everything before <NEXT_TURN> token)
            game_state_tokens = []
            for token in raw_tokens:
                if token == TokenID.NEXT_TURN.value:
                    break
                game_state_tokens.append(token)
            
            # Calculate incremental changes
            incremental_tokens = []
            if len(game_state_tokens) > len(last_seen):
                # New tokens added since last turn
                incremental_tokens = game_state_tokens[len(last_seen):]
            elif game_state_tokens != last_seen:
                # State has changed in some way - show the difference
                incremental_tokens = game_state_tokens
            
            # Update complete game history file - SIMPLE FORMAT: just final game state
            complete_history_path = self.player_complete_history_files[player_id]
            
            # Only write the final complete state, overwriting previous content
            with open(complete_history_path, 'w', encoding='utf-8') as f:
                f.write("FULL TOKEN SEQUENCE:\n")
                f.write(format_tokens(raw_tokens) + "\n\n")
                f.write("READABLE FORMAT:\n")
                readable_format = format_tokens_readable(raw_tokens)
                if readable_format.strip():
                    f.write(readable_format + "\n")
                else:
                    f.write("(No readable format available)\n")
            
            # Write incremental log (simplified format)
            player_log_path = self.traffic_log_files[player_id]
            with open(player_log_path, 'a', encoding='utf-8') as f:
                f.write("🖥️  SERVER RESPONSE (Incremental changes since last turn):\n")
                f.write("-" * 40 + "\n")
                
                if incremental_tokens:
                    f.write("NEW EVENTS SINCE LAST TURN:\n")
                    f.write("TOKENS: " + format_tokens(incremental_tokens) + "\n")
                    
                    # Human-readable format for incremental changes
                    f.write("\nREADABLE FORMAT:\n")
                    readable_incremental = format_tokens_readable(incremental_tokens)
                    if readable_incremental.strip():
                        f.write(readable_incremental + "\n")
                    else:
                        f.write("(No significant changes)\n")
                else:
                    f.write("NO NEW EVENTS - Your turn to act\n")
                
                # Only show legal actions if explicitly enabled
                if legal_actions and self.show_legal_actions:
                    f.write(f"\nVALID OUTPUT SEQUENCES ({len(legal_actions)} options):\n")
                    f.write("(What LLM can respond with)\n")
                    f.write("-" * 40 + "\n")
                    for i, action in enumerate(legal_actions, 1):
                        f.write(f"  {i:2d}. {format_tokens(action)}\n")
                
                f.write(f"\n💡 Complete game state available in: complete_game_history_player_{player_id}.log\n")
                f.write("\n")
            
            # Update player's last seen history
            self.player_last_seen_history[player_id] = game_state_tokens.copy()
            
        elif direction == "CLIENT_TO_SERVER":
            # For client requests, log normally (they're always incremental)
            player_log_path = self.traffic_log_files[player_id]
            with open(player_log_path, 'a', encoding='utf-8') as f:
                f.write("🤖 CLIENT REQUEST (What LLM sent as output):\n")
                f.write("-" * 40 + "\n")
                if raw_tokens:
                    f.write("TOKENS: " + format_tokens(raw_tokens) + "\n")
                    
                    f.write("\nREADABLE FORMAT:\n")
                    readable_format = format_tokens_readable(raw_tokens)
                    if readable_format.strip():
                        f.write(readable_format + "\n")
                    else:
                        f.write("(No readable format available)\n")
                f.write("\n")
        
        # Also log to master traffic log for reference
        if self.master_traffic_log:
            with open(self.master_traffic_log, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] Player {player_id} - {direction} - {message}\n")
    
    def start_game(self) -> bool:
        """Start a new game with the specified seed."""
        try:
            self._log_game_flow(f"🎮 Starting new game with seed {self.seed}")
            self.current_state = self.interface.initialize_game(seed=self.seed)
            self.turn_count = 0
            self.action_count = 0
            
            self._log(f"Game initialized successfully")
            self._log(f"Active player: {self.current_state.active_player}")
            self._log(f"Phase: DAY_1")
            self._log_game_flow(f"🎯 Game ready - Active player: P{self.current_state.active_player}, Phase: <DAY_1>")
            
            return True
            
        except Exception as e:
            self._log_game_flow(f"❌ ERROR starting game: {e}")
            return False
    
    def get_player_state(self, player_id: int) -> ServerResponse:
        """
        Get current game state tokens for a specific player.
        Returns state only if it's the player's turn to act.
        """
        if not self.current_state:
            return ServerResponse(
                success=False,
                player_state=None,
                legal_actions=[],
                game_finished=False,
                winner=None,
                error_message="Game not started"
            )
        
        try:
            # Check if game is finished
            game_result = self.interface.get_game_result(self.current_state)
            if game_result is not None:
                return ServerResponse(
                    success=True,
                    player_state=None,
                    legal_actions=[],
                    game_finished=True,
                    winner=game_result,
                    error_message=None
                )
            
            # Check if it's this player's turn
            is_active = (self.current_state.active_player == player_id)
            
            # Get legal actions if it's their turn
            legal_actions = []
            if is_active:
                legal_actions = self.interface.get_legal_actions(self.current_state)
                self._log(f"Player {player_id} requested state - ACTIVE TURN")
                self._log(f"Legal actions count: {len(legal_actions)}")
            else:
                self._log(f"Player {player_id} requested state - WAITING (active: {self.current_state.active_player})")
            
            # Use the new chronological sequence system if available
            if hasattr(self.current_state, 'player_chronological_sequences') and player_id < len(self.current_state.player_chronological_sequences):
                # Get the complete chronological sequence for this player
                player_chronological_sequence = self.current_state.player_chronological_sequences[player_id].copy()
                
                # Extract private information for backward compatibility
                private_info = []
                i = 0
                while i < len(player_chronological_sequence):
                    token = player_chronological_sequence[i]
                    
                    # Extract role information
                    if token == TokenID.YOUR_ROLE.value and i + 1 < len(player_chronological_sequence):
                        private_info.extend([token, player_chronological_sequence[i + 1]])
                        i += 2
                        continue
                        
                    # Extract team information
                    if token == TokenID.MAFIA_TEAM.value:
                        private_info.append(token)
                        i += 1
                        while i < len(player_chronological_sequence) and player_chronological_sequence[i] >= TokenID.PLAYER_0.value and player_chronological_sequence[i] <= TokenID.PLAYER_9.value:
                            private_info.append(player_chronological_sequence[i])
                            i += 1
                        continue
                        
                    # Extract check results
                    if token in [TokenID.SHERIFF_CHECK.value, TokenID.DON_CHECK.value] and i + 2 < len(player_chronological_sequence):
                        private_info.extend([token, player_chronological_sequence[i + 1], player_chronological_sequence[i + 2]])
                        i += 3
                        continue
                        
                    i += 1
                
                # Create player state tokens using the chronological sequence
                # Note: chronological_history no longer includes seed to prevent cheating
                player_state = PlayerStateTokens(
                    player_id=player_id,
                    seed_tokens=[1000 + self.seed, TokenID.GAME_START.value, TokenID.PLAYER_0.value + player_id],  # Internal seed info (not visible to player)
                    chronological_history=player_chronological_sequence,  # Complete sequence without seed
                    private_state=private_info,  # Extracted private information for backward compatibility
                    active_player=self.current_state.active_player,
                    is_active=is_active
                )
            else:
                # Fallback to old system for backward compatibility
                player_specific_seed_tokens = self.current_state.seed_tokens.copy()
                if len(player_specific_seed_tokens) >= 3:
                    player_specific_seed_tokens[2] = TokenID.PLAYER_0.value + player_id
                
                player_state = PlayerStateTokens(
                    player_id=player_id,
                    seed_tokens=player_specific_seed_tokens,
                    chronological_history=self.current_state.chronological_history.copy(),
                    private_state=self.current_state.private_states[player_id].copy(),
                    active_player=self.current_state.active_player,
                    is_active=is_active
                )
            
            # Log traffic if player is active (receiving game state and legal actions)
            if is_active:
                # Use the interface's get_observation_tokens method to properly include ephemeral <NEXT_TURN> token
                full_state_tokens = self.interface.get_observation_tokens(self.current_state, player_id)
                
                # VOTING PRIVACY FIX: For debugging, log the actual tokens we're sending
                self._log(f"Full state tokens for player {player_id}: {len(full_state_tokens)} tokens")
                
                self._log_traffic(
                    direction="SERVER_TO_CLIENT",
                    player_id=player_id,
                    message=f"Game state response - Active player turn with {len(legal_actions)} legal actions",
                    raw_tokens=full_state_tokens,
                    legal_actions=legal_actions
                )
            
            return ServerResponse(
                success=True,
                player_state=player_state,
                legal_actions=legal_actions,
                game_finished=False,
                winner=None,
                error_message=None
            )
            
        except Exception as e:
            self._log(f"ERROR getting player state for player {player_id}: {e}")
            return ServerResponse(
                success=False,
                player_state=None,
                legal_actions=[],
                game_finished=False,
                winner=None,
                error_message=str(e)
            )
    
    def apply_player_action(self, player_id: int, action_tokens: List[int]) -> ServerResponse:
        """
        Apply a player's action tokens to the game state.
        Returns updated state if action was successful.
        """
        if not self.current_state:
            return ServerResponse(
                success=False,
                player_state=None,
                legal_actions=[],
                game_finished=False,
                winner=None,
                error_message="Game not started"
            )
        
        try:
            # Verify it's the correct player's turn
            if self.current_state.active_player != player_id:
                return ServerResponse(
                    success=False,
                    player_state=None,
                    legal_actions=[],
                    game_finished=False,
                    winner=None,
                    error_message=f"Not player {player_id}'s turn (active: {self.current_state.active_player})"
                )
            
            self._log(f"Player {player_id} attempting action: {action_tokens}")
            
            # Log traffic for client action
            self._log_traffic(
                direction="CLIENT_TO_SERVER",
                player_id=player_id,
                message=f"Action request from player {player_id}",
                raw_tokens=action_tokens
            )
            
            # Apply the action
            new_state = self.interface.apply_action(self.current_state, action_tokens, player_id)
            old_phase = format_tokens(PlayerStateTokens(0, [], self.current_state.chronological_history, [], 0, False).phase_tokens)
            self.current_state = new_state
            self.action_count += 1
            
            self._log(f"Action applied successfully")
            self._log(f"New active player: {self.current_state.active_player}")
            self._log(f"New phase: {format_tokens(PlayerStateTokens(0, [], self.current_state.chronological_history, [], 0, False).phase_tokens)}")
            self._log(f"Action count: {self.action_count}")
            
            # Show high-level game flow
            new_phase = format_tokens(PlayerStateTokens(0, [], self.current_state.chronological_history, [], 0, False).phase_tokens)
            if old_phase != new_phase:
                self._log_game_flow(f"🔄 Phase changed: {old_phase} → {new_phase}")
            
            self._log_game_flow(f"⚡ P{player_id} → {format_tokens(action_tokens)} → P{self.current_state.active_player} (action #{self.action_count})")
            
            # Check if game finished after this action
            game_result = self.interface.get_game_result(self.current_state)
            if game_result is not None:
                self._log_game_flow(f"🏁 GAME FINISHED! Winner: {game_result}")
                
                # IMPORTANT: Log final state with end-of-game tokens for ALL players
                # This ensures all player traffic logs show the complete game including the result
                training_sequences = {}  # Store for dedicated training files
                
                for final_player_id in range(10):
                    if final_player_id < len(self.current_state.player_chronological_sequences):
                        # Get the final observation tokens for each player (includes end-of-game tokens)
                        final_state_tokens = self.interface.get_observation_tokens(self.current_state, final_player_id)
                        
                        # Store for training file generation
                        training_sequences[final_player_id] = final_state_tokens
                        
                        # Log the final state to each player's traffic log
                        self._log_traffic(
                            direction="SERVER_TO_CLIENT",
                            player_id=final_player_id,
                            message=f"COMPLETE GAME HISTORY - Final training sequence with result {game_result}",
                            raw_tokens=final_state_tokens,
                            legal_actions=[]  # No more legal actions - game is over
                        )
                
                # Generate dedicated training files
                self._generate_training_files(training_sequences, game_result)
                
                return ServerResponse(
                    success=True,
                    player_state=None,
                    legal_actions=[],
                    game_finished=True,
                    winner=game_result,
                    error_message=None
                )
            
            # Return success (client should request new state)
            return ServerResponse(
                success=True,
                player_state=None,
                legal_actions=[],
                game_finished=False,
                winner=None,
                error_message=None
            )
            
        except Exception as e:
            self._log(f"ERROR applying action for player {player_id}: {e}")
            return ServerResponse(
                success=False,
                player_state=None,
                legal_actions=[],
                game_finished=False,
                winner=None,
                error_message=str(e)
            )
    
    def _generate_training_files(self, training_sequences: Dict[int, List[int]], game_result: str):
        """Generate dedicated training files for transformer models."""
        if not self.traffic_log_dir:
            return
        
        # Create training data directory
        training_dir = os.path.join(self.traffic_log_dir, "training_data")
        os.makedirs(training_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate individual player training files
        for player_id, token_sequence in training_sequences.items():
            # Raw token file for direct transformer training
            token_file = os.path.join(training_dir, f"player_{player_id}_tokens_seed_{self.seed}.json")
            with open(token_file, 'w', encoding='utf-8') as f:
                training_data = {
                    "metadata": {
                        "player_id": player_id,
                        "seed": self.seed,
                        "game_result": str(game_result),
                        "total_actions": self.action_count,
                        "timestamp": timestamp,
                        "description": f"Complete game token sequence for Player {player_id} from seed {self.seed}"
                    },
                    "token_sequence": token_sequence,
                    "sequence_length": len(token_sequence)
                }
                json.dump(training_data, f, indent=2)
            
            # Human-readable file for analysis
            readable_file = os.path.join(training_dir, f"player_{player_id}_readable_seed_{self.seed}.txt")
            with open(readable_file, 'w', encoding='utf-8') as f:
                f.write(f"MAFIA GAME TRAINING DATA - Player {player_id}\n")
                f.write(f"Seed: {self.seed}\n")
                f.write(f"Game Result: {game_result}\n")
                f.write(f"Total Actions: {self.action_count}\n")
                f.write(f"Generated: {timestamp}\n")
                f.write("="*80 + "\n\n")
                
                f.write("TOKEN SEQUENCE:\n")
                f.write(format_tokens(token_sequence) + "\n\n")
                
                f.write("HUMAN-READABLE GAME FLOW:\n")
                f.write("-"*40 + "\n")
                readable_format = format_tokens_readable(token_sequence)
                if readable_format.strip():
                    f.write(readable_format + "\n")
                else:
                    f.write("(No readable format available)\n")
        
        # Generate combined training dataset
        combined_file = os.path.join(training_dir, f"all_players_seed_{self.seed}.json")
        with open(combined_file, 'w', encoding='utf-8') as f:
            combined_data = {
                "metadata": {
                    "seed": self.seed,
                    "game_result": str(game_result),
                    "total_actions": self.action_count,
                    "timestamp": timestamp,
                    "description": f"Complete game training data for all players from seed {self.seed}",
                    "num_players": len(training_sequences)
                },
                "players": {}
            }
            
            for player_id, token_sequence in training_sequences.items():
                combined_data["players"][str(player_id)] = {
                    "token_sequence": token_sequence,
                    "sequence_length": len(token_sequence)
                }
            
            json.dump(combined_data, f, indent=2)
        
        # Log the generated files
        self._log_game_flow(f"📁 Generated training files in {training_dir}/")
        self._log_game_flow(f"   - Individual player files: player_X_tokens_seed_{self.seed}.json")
        self._log_game_flow(f"   - Human-readable files: player_X_readable_seed_{self.seed}.txt")
        self._log_game_flow(f"   - Combined dataset: all_players_seed_{self.seed}.json")
    
    def get_game_stats(self) -> Dict:
        """Get current game statistics."""
        if not self.current_state:
            return {"error": "Game not started"}
        
        # Create a temporary PlayerStateTokens to extract phase and public history info
        temp_player_state = PlayerStateTokens(0, [], self.current_state.chronological_history, [], 0, False)
        
        return {
            "seed": self.seed,
            "turn_count": self.turn_count,
            "action_count": self.action_count,
            "active_player": self.current_state.active_player,
            "phase_tokens": temp_player_state.phase_tokens,
            "public_history_length": len(temp_player_state.public_history),
            "game_finished": self.interface.get_game_result(self.current_state) is not None
        }


class TokenGameClient:
    """
    Test client that communicates with TokenGameServer using only tokens.
    Simulates how a transformer would interact with the game.
    
    Multi-action day turns: Performs 5-7 random day actions before END_TURN.
    Single-action other phases: Night/voting phases work as before.
    """
    
    def __init__(self, player_id: int, server: TokenGameServer, log_file: Optional[str] = None):
        self.player_id = player_id
        self.server = server
        self.log_file = log_file
        self.action_count = 0
        
        # Multi-action day turn tracking
        self.day_actions_this_turn = 0
        self.target_day_actions = 0
        
        # Initialize logging
        if log_file:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"MAFIA TOKEN GAME CLIENT LOG - Player {player_id}\n")
                f.write(f"Started: {datetime.now()}\n")
                f.write("="*60 + "\n\n")
    
    def _log(self, message: str):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] P{self.player_id}: {message}"
        
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + "\n")
        
        print(f"🤖 CLIENT: {log_entry}")
    
    def request_game_state(self) -> Optional[Tuple[PlayerStateTokens, List[List[int]]]]:
        """
        Request current game state from server.
        Returns (state_tokens, legal_actions) if it's this player's turn, None otherwise.
        """
        self._log("Requesting game state from server...")
        
        response = self.server.get_player_state(self.player_id)
        
        if not response.success:
            self._log(f"Server error: {response.error_message}")
            return None
        
        if response.game_finished:
            self._log(f"Game finished! Winner: {response.winner}")
            return None
        
        if not response.player_state or not response.player_state.is_active:
            self._log("Not my turn, waiting...")
            return None
        
        # Log received state with clean token formatting and decoded seed
        state = response.player_state
        self._log(f"Received state tokens:")
        
        # Show both token encoding and decoded seed for clarity
        seed_tokens_formatted = format_tokens(state.seed_tokens)
        if len(state.seed_tokens) > 0:
            token_seed = state.seed_tokens[0]
            decoded_seed = token_seed - 1000 if token_seed >= 1000 else token_seed
            self._log(f"  Seed: {seed_tokens_formatted} [Game Logic Seed: {decoded_seed}]")
        else:
            self._log(f"  Seed: {seed_tokens_formatted}")
            
        self._log(f"  Phase: {format_tokens(state.phase_tokens)}")
        self._log(f"  Private: {format_tokens(state.private_state)}")
        self._log(f"  Public history length: {len(state.public_history)}")
        self._log(f"  Active player: {state.active_player}")
        self._log(f"  Legal actions count: {len(response.legal_actions)}")
        
        return (state, response.legal_actions)
    
    def choose_action(self, legal_actions: List[List[int]]) -> List[int]:
        """
        Choose an action from legal actions.
        
        The new system provides individual actions that the agent can combine.
        For day phases, we can build sequences by choosing multiple actions and adding END_TURN.
        For other phases, we choose single actions.
        """
        if not legal_actions:
            self._log("No legal actions available!")
            return []
        
        import random
        
        # IMPROVED PHASE DETECTION: Use action types and count to determine phase
        end_turn_available = [TokenID.END_TURN.value] in legal_actions
        individual_actions = [action for action in legal_actions if action != [TokenID.END_TURN.value]]
        
        # Check for night-specific actions (these indicate non-day phases)
        night_action_types = {TokenID.KILL.value, TokenID.SHERIFF_CHECK.value, TokenID.DON_CHECK.value}
        voting_action_types = {TokenID.VOTE.value, TokenID.VOTE_ELIMINATE_ALL.value, TokenID.VOTE_KEEP_ALL.value}
        
        has_night_actions = any(action[0] in night_action_types for action in individual_actions if action)
        has_voting_actions = any(action[0] in voting_action_types for action in individual_actions if action)
        
        # Day phase detection:
        # 1. No night or voting actions present
        # 2. Many legal actions available (day phases typically have 70+ actions)
        # 3. Has day-specific actions like SAY, NOMINATE, CLAIM_SHERIFF
        day_action_types = {TokenID.SAY.value, TokenID.NOMINATE.value, TokenID.CLAIM_SHERIFF.value, 
                           TokenID.CLAIM_SHERIFF_CHECK.value, TokenID.DENY_SHERIFF.value}
        has_day_actions = any(action[0] in day_action_types for action in individual_actions if action)
        
        is_day_phase = (not has_night_actions and not has_voting_actions and 
                       (len(legal_actions) > 20 or has_day_actions))
        
        if is_day_phase and end_turn_available and individual_actions:
            # Day phase: Build a multi-action sequence ending with END_TURN
            self._log(f"Day phase detected - building multi-action sequence (actions: {len(legal_actions)})")
            
            # Pick 0-7 random individual actions
            num_actions = random.randint(0, min(7, len(individual_actions)))
            self._log(f"Building sequence with {num_actions} individual actions")
            
            if num_actions == 0:
                # Just END_TURN
                sequence = [TokenID.END_TURN.value]
                self._log("Generated sequence: <END_TURN>")
            else:
                # Pick random individual actions and build sequence
                chosen_actions = random.sample(individual_actions, min(num_actions, len(individual_actions)))
                sequence = []
                
                # Add each chosen action to the sequence, stripping END_TURN tokens
                for action in chosen_actions:
                    # Strip END_TURN tokens from individual actions to prevent internal END_TURN tokens
                    clean_action = [token for token in action if token != TokenID.END_TURN.value]
                    if clean_action:  # Only add non-empty actions
                        sequence.extend(clean_action)
                
                # Add single END_TURN at the end
                sequence.append(TokenID.END_TURN.value)
                
                # Log the built sequence
                self._log(f"Built sequence from {len(chosen_actions)} actions: {format_tokens(sequence)}")
            
            return sequence
            
        else:
            # Night/voting phase: choose single action
            phase_type = "night" if has_night_actions else "voting" if has_voting_actions else "single-action"
            self._log(f"Single action phase detected ({phase_type}) - choosing single action (actions: {len(legal_actions)})")
            
            chosen_action = random.choice(legal_actions)
            self._log(f"Single action chosen: {format_tokens(chosen_action)}")
            self._log(f"  From {len(legal_actions)} legal actions")
            
            return chosen_action
    
    def send_action(self, action_tokens: List[int]) -> bool:
        """
        Send chosen action tokens to server.
        Returns True if action was accepted.
        """
        self._log(f"Sending action to server: {format_tokens(action_tokens)}")
        
        response = self.server.apply_player_action(self.player_id, action_tokens)
        
        if response.success:
            self.action_count += 1
            self._log(f"Action accepted! (Total actions: {self.action_count})")
            
            if response.game_finished:
                self._log(f"Game finished after my action! Winner: {response.winner}")
            
            return True
        else:
            self._log(f"Action rejected: {response.error_message}")
            return False
    
    def play_turn(self) -> bool:
        """
        Play one complete turn: request state, choose action, send action.
        Returns True if turn was played successfully, False if game finished or error.
        """
        # Request game state
        result = self.request_game_state()
        if result is None:
            return False  # Not my turn or game finished
        
        state_tokens, legal_actions = result
        
        # Choose action
        chosen_action = self.choose_action(legal_actions)
        if not chosen_action:
            self._log("No action chosen!")
            return False
        
        # Send action
        success = self.send_action(chosen_action)
        return success
