"""
Token vocabulary definitions for the Mafia game transformer system.
"""
from enum import IntEnum
from typing import Dict, List, Optional

class TokenID(IntEnum):
    """Token ID constants matching the token grammar specification."""
    
    # Verb Tokens (Action Types)
    END_TURN = 0
    NOMINATE = 1
    CLAIM_SHERIFF = 2
    CLAIM_SHERIFF_CHECK = 3
    DENY_SHERIFF = 4
    SAY = 5
    VOTE = 6
    VOTE_ELIMINATE_ALL = 7
    VOTE_KEEP_ALL = 8
    KILL = 9
    SHERIFF_CHECK = 10
    DON_CHECK = 11
    YOUR_POSITION = 12
    
    # Argument Tokens (Player References)
    PLAYER_0 = 13
    PLAYER_1 = 14
    PLAYER_2 = 15
    PLAYER_3 = 16
    PLAYER_4 = 17
    PLAYER_5 = 18
    PLAYER_6 = 19
    PLAYER_7 = 20
    PLAYER_8 = 21
    PLAYER_9 = 22
    
    # Color Tokens
    RED = 23
    BLACK = 24
    
    # Role Tokens
    CITIZEN = 25
    SHERIFF = 26
    MAFIA = 27
    DON = 28
    
    # System/Environment Tokens (Read-Only)
    CHECK_RESULT = 29
    NOT_SHERIFF = 30
    MAFIA_TEAM = 31
    YOUR_ROLE = 32
    NOMINATED_LIST = 33
    VOTE_REVEALED = 34
    ELIMINATED = 35
    KILLED = 36
    TIE_RESULT = 37
    STARTING_PLAYER = 38
    GAME_START = 39
    RED_TEAM_WON = 40
    BLACK_TEAM_WON = 41
    
    # Phase Tokens (Game State)
    DAY_1 = 42
    DAY_2 = 43
    DAY_3 = 44
    DAY_4 = 45
    DAY_5 = 46
    NIGHT_1 = 47
    NIGHT_2 = 48
    NIGHT_3 = 49
    NIGHT_4 = 50
    
    # Phase transition tokens
    VOTING_PHASE_START = 51
    NIGHT_PHASE_START = 52
    DAY_PHASE_START = 53
    REVOTE_PHASE = 56
    ELIMINATE_ALL_VOTE = 57
    
    # Turn signaling tokens
    YOUR_TURN = 54
    
    # Ephemeral tokens (not stored in history) 
    NEXT_TURN = 55


# Token name to ID mappings
TOKEN_NAME_TO_ID: Dict[str, int] = {
    # Verbs
    "<END_TURN>": TokenID.END_TURN,
    "<NOMINATE>": TokenID.NOMINATE,
    "<CLAIM_SHERIFF>": TokenID.CLAIM_SHERIFF,
    "<CLAIM_SHERIFF_CHECK>": TokenID.CLAIM_SHERIFF_CHECK,
    "<DENY_SHERIFF>": TokenID.DENY_SHERIFF,
    "<SAY>": TokenID.SAY,
    "<VOTE>": TokenID.VOTE,
    "<VOTE_ELIMINATE_ALL>": TokenID.VOTE_ELIMINATE_ALL,
    "<VOTE_KEEP_ALL>": TokenID.VOTE_KEEP_ALL,
    "<KILL>": TokenID.KILL,
    "<SHERIFF_CHECK>": TokenID.SHERIFF_CHECK,
    "<DON_CHECK>": TokenID.DON_CHECK,
    "<YOUR_POSITION>": TokenID.YOUR_POSITION,
    
    # Players
    "<PLAYER_0>": TokenID.PLAYER_0,
    "<PLAYER_1>": TokenID.PLAYER_1,
    "<PLAYER_2>": TokenID.PLAYER_2,
    "<PLAYER_3>": TokenID.PLAYER_3,
    "<PLAYER_4>": TokenID.PLAYER_4,
    "<PLAYER_5>": TokenID.PLAYER_5,
    "<PLAYER_6>": TokenID.PLAYER_6,
    "<PLAYER_7>": TokenID.PLAYER_7,
    "<PLAYER_8>": TokenID.PLAYER_8,
    "<PLAYER_9>": TokenID.PLAYER_9,
    
    # Colors
    "<RED>": TokenID.RED,
    "<BLACK>": TokenID.BLACK,
    
    # Roles
    "<CITIZEN>": TokenID.CITIZEN,
    "<SHERIFF>": TokenID.SHERIFF,
    "<MAFIA>": TokenID.MAFIA,
    "<DON>": TokenID.DON,
    
    # System tokens
    "<CHECK_RESULT>": TokenID.CHECK_RESULT,
    "<NOT_SHERIFF>": TokenID.NOT_SHERIFF,
    "<MAFIA_TEAM>": TokenID.MAFIA_TEAM,
    "<YOUR_ROLE>": TokenID.YOUR_ROLE,
    "<NOMINATED_LIST>": TokenID.NOMINATED_LIST,
    "<VOTE_REVEALED>": TokenID.VOTE_REVEALED,
    "<ELIMINATED>": TokenID.ELIMINATED,
    "<KILLED>": TokenID.KILLED,
    "<TIE_RESULT>": TokenID.TIE_RESULT,
    "<STARTING_PLAYER>": TokenID.STARTING_PLAYER,
    "<GAME_START>": TokenID.GAME_START,
    "<RED_TEAM_WON>": TokenID.RED_TEAM_WON,
    "<BLACK_TEAM_WON>": TokenID.BLACK_TEAM_WON,
    
    # Phases
    "<DAY_1>": TokenID.DAY_1,
    "<DAY_2>": TokenID.DAY_2,
    "<DAY_3>": TokenID.DAY_3,
    "<DAY_4>": TokenID.DAY_4,
    "<DAY_5>": TokenID.DAY_5,
    "<NIGHT_1>": TokenID.NIGHT_1,
    "<NIGHT_2>": TokenID.NIGHT_2,
    "<NIGHT_3>": TokenID.NIGHT_3,
    "<NIGHT_4>": TokenID.NIGHT_4,
    
    # Phase transition tokens
    "<VOTING_PHASE_START>": TokenID.VOTING_PHASE_START,
    "<NIGHT_PHASE_START>": TokenID.NIGHT_PHASE_START,
    "<DAY_PHASE_START>": TokenID.DAY_PHASE_START,
    "<REVOTE_PHASE>": TokenID.REVOTE_PHASE,
    "<ELIMINATE_ALL_VOTE>": TokenID.ELIMINATE_ALL_VOTE,
    
    # Turn signaling tokens
    "<YOUR_TURN>": TokenID.YOUR_TURN,
    
    # Ephemeral tokens (not stored in history)
    "<NEXT_TURN>": TokenID.NEXT_TURN,
}

# ID to token name mappings (inverse)
TOKEN_ID_TO_NAME: Dict[int, str] = {v: k for k, v in TOKEN_NAME_TO_ID.items()}

# Verb tokens (action types that can be performed by players)
VERB_TOKENS = [
    TokenID.END_TURN,
    TokenID.NOMINATE,
    TokenID.CLAIM_SHERIFF,
    TokenID.CLAIM_SHERIFF_CHECK,
    TokenID.DENY_SHERIFF,
    TokenID.SAY,
    TokenID.VOTE,
    TokenID.VOTE_ELIMINATE_ALL,
    TokenID.VOTE_KEEP_ALL,
    TokenID.KILL,
    TokenID.SHERIFF_CHECK,
    TokenID.DON_CHECK,
]

# Player tokens (targets for actions)
PLAYER_TOKENS = [
    TokenID.PLAYER_0,
    TokenID.PLAYER_1,
    TokenID.PLAYER_2,
    TokenID.PLAYER_3,
    TokenID.PLAYER_4,
    TokenID.PLAYER_5,
    TokenID.PLAYER_6,
    TokenID.PLAYER_7,
    TokenID.PLAYER_8,
    TokenID.PLAYER_9,
]

# Color tokens
COLOR_TOKENS = [TokenID.RED, TokenID.BLACK]

# Role tokens
ROLE_TOKENS = [TokenID.CITIZEN, TokenID.SHERIFF, TokenID.MAFIA, TokenID.DON]

# Phase tokens
PHASE_TOKENS = [
    TokenID.DAY_1, TokenID.DAY_2, TokenID.DAY_3, TokenID.DAY_4, TokenID.DAY_5,
    TokenID.NIGHT_1, TokenID.NIGHT_2, TokenID.NIGHT_3, TokenID.NIGHT_4
]

# System tokens (read-only, generated by environment)
SYSTEM_TOKENS = [
    TokenID.CHECK_RESULT,
    TokenID.NOT_SHERIFF,
    TokenID.MAFIA_TEAM,
    TokenID.YOUR_ROLE,
    TokenID.NOMINATED_LIST,
    TokenID.VOTE_REVEALED,
    TokenID.ELIMINATED,
    TokenID.KILLED,
    TokenID.TIE_RESULT,
    TokenID.STARTING_PLAYER,
    TokenID.GAME_START,
    TokenID.RED_TEAM_WON,
    TokenID.BLACK_TEAM_WON,
    TokenID.YOUR_POSITION,
]

# Verbs that don't require a target
NO_TARGET_VERBS = {
    TokenID.END_TURN,
    TokenID.CLAIM_SHERIFF,
    TokenID.DENY_SHERIFF,
    TokenID.VOTE_ELIMINATE_ALL,
    TokenID.VOTE_KEEP_ALL,
}

# Verbs that require a player target
PLAYER_TARGET_VERBS = {
    TokenID.NOMINATE,
    TokenID.VOTE,
    TokenID.KILL,
    TokenID.SHERIFF_CHECK,
    TokenID.DON_CHECK,
}

# Verbs that require player + color targets
PLAYER_COLOR_TARGET_VERBS = {
    TokenID.CLAIM_SHERIFF_CHECK,
    TokenID.SAY,
}

# Vocabulary size
VOCAB_SIZE = 58  # Updated for phase transition and turn signaling tokens

# Helper functions
def player_index_to_token(player_index: int) -> TokenID:
    """Convert player index to player token."""
    if not 0 <= player_index <= 9:
        raise ValueError(f"Invalid player index: {player_index}")
    return TokenID(TokenID.PLAYER_0 + player_index)

def token_to_player_index(token: TokenID) -> int:
    """Convert player token to player index."""
    if token not in PLAYER_TOKENS:
        raise ValueError(f"Token {token} is not a player token")
    return int(token) - int(TokenID.PLAYER_0)

def is_verb_token(token: TokenID) -> bool:
    """Check if token is a verb (action) token."""
    return token in VERB_TOKENS

def is_player_token(token: TokenID) -> bool:
    """Check if token is a player token."""
    return token in PLAYER_TOKENS

def is_color_token(token: TokenID) -> bool:
    """Check if token is a color token."""
    return token in COLOR_TOKENS

def is_role_token(token: TokenID) -> bool:
    """Check if token is a role token."""
    return token in ROLE_TOKENS

def is_phase_token(token: TokenID) -> bool:
    """Check if token is a phase token."""
    return token in PHASE_TOKENS

def is_system_token(token: TokenID) -> bool:
    """Check if token is a system token."""
    return token in SYSTEM_TOKENS

def verb_requires_target(verb: TokenID) -> bool:
    """Check if a verb token requires a target."""
    return verb not in NO_TARGET_VERBS

def verb_requires_player_target(verb: TokenID) -> bool:
    """Check if a verb token requires a player target."""
    return verb in PLAYER_TARGET_VERBS

def verb_requires_player_color_targets(verb: TokenID) -> bool:
    """Check if a verb token requires both player and color targets."""
    return verb in PLAYER_COLOR_TARGET_VERBS

def phase_to_token(phase_name: str, turn: int) -> TokenID:
    """Convert phase name and turn to phase token."""
    phase_key = f"<{phase_name.upper()}_{turn}>"
    if phase_key not in TOKEN_NAME_TO_ID:
        raise ValueError(f"Invalid phase: {phase_name} turn {turn}")
    return TokenID(TOKEN_NAME_TO_ID[phase_key])

def token_to_phase(token: TokenID) -> tuple[str, int]:
    """Convert phase token to phase name and turn."""
    if not is_phase_token(token):
        raise ValueError(f"Token {token} is not a phase token")
    
    token_name = TOKEN_ID_TO_NAME[token]
    # Parse "<DAY_1>" -> ("DAY", 1)
    phase_part = token_name[1:-1]  # Remove < >
    phase_name, turn_str = phase_part.split('_')
    return phase_name.lower(), int(turn_str)
