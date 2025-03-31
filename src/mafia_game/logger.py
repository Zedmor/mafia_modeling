import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

# Configure the logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create a logger
logger = logging.getLogger('mafia_game')

# Create a file logger
os.makedirs('logs', exist_ok=True)
file_handler = logging.FileHandler('logs/mafia_game.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_logger = logging.getLogger('mafia_game_file')
file_logger.setLevel(logging.INFO)
file_logger.addHandler(file_handler)
file_logger.propagate = False  # Prevent logs from being sent to the console


class LogType(Enum):
    KILL_ACTION = "KILL_ACTION"
    ACTION = "ACTION"
    PHASE_CHANGE = "PHASE_CHANGE"
    GAME_STATE = "GAME_STATE"
    VOTE_RESULT = "VOTE_RESULT"
    VOTE_ACTION = "VOTE_ACTION"
    ELIMINATION = "ELIMINATION"
    GAME_END = "GAME_END"
    DON_CHECK = "DON_CHECK"
    SHERIFF_CHECK = "SHERIFF_CHECK"
    UTTERANCE = "UTTERANCE"
    OTHER = "OTHER"

@dataclass
class LogMessage:
    message: str
    log_type: LogType = LogType.OTHER
    turn: int = 0
    player_index: Optional[int] = None
    target_player_index: Optional[int] = None
    timestamp: str = field(default_factory=lambda: logging.Formatter().formatTime(logging.LogRecord("", 0, "", 0, "", (), None)))
    
    def __str__(self):
        player_info = f"Игрок {self.player_index}" if self.player_index is not None else ""
        target_info = f" -> игрока {self.target_player_index}" if self.target_player_index is not None else ""
        turn_info = f"[Ход {self.turn}]" if self.turn > 0 else ""
        
        prefix = f"{turn_info} {player_info}{target_info}: " if (player_info or target_info or turn_info) else ""
        return f"{prefix}{self.message}"
