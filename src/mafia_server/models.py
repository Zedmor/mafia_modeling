from enum import Enum, auto
import random
import json
import numpy as np
from typing import Dict, List, Any, Optional, Set, Tuple, Union


class Team(Enum):
    """Team enumeration representing the two teams in the game"""
    RED = "RED"
    BLACK = "BLACK"
    UNKNOWN = "UNKNOWN"


class Role(Enum):
    """Role enumeration representing the different roles in the game"""
    CITIZEN = "CITIZEN"
    SHERIFF = "SHERIFF"
    MAFIA = "MAFIA"
    DON = "DON"
    UNKNOWN = "UNKNOWN"
    
    @property
    def team(self) -> Team:
        """Get the team associated with this role"""
        if self in [Role.CITIZEN, Role.SHERIFF]:
            return Team.RED
        elif self in [Role.MAFIA, Role.DON]:
            return Team.BLACK
        return Team.UNKNOWN


class Phase(Enum):
    """Phase enumeration representing the different phases of the game"""
    DECLARATION = "DECLARATION"
    VOTING = "VOTING"
    NIGHT_KILL = "NIGHT_KILL"
    NIGHT_DON = "NIGHT_DON"
    NIGHT_SHERIFF = "NIGHT_SHERIFF"
    GAME_OVER = "GAME_OVER"


class Player:
    """Represents a player in the game with their role and state"""
    
    def __init__(self, player_id: int, role: Role):
        self.player_id = player_id
        self.role = role
        self.alive = True
        self.vote_for = None  # Who this player voted for in current voting round
        
        # Track player declarations
        self.declarations = [0] * 10  # Belief values from -3 to 3
        self.sheriff_claims = [[0] * 10 for _ in range(10)]  # 10x10 matrix for sheriff check claims (one row per turn)
        
        # Private information
        self._private_info = {}
        
        # Nominated players by this player
        self.nominations = []
    
    @property
    def team(self) -> Team:
        """Get the team of this player based on their role"""
        return self.role.team
    
    def to_dict(self) -> Dict:
        """Convert Player object to dictionary for serialization"""
        return {
            "player_id": self.player_id,
            "role": self.role.name,
            "alive": self.alive,
            "declarations": self.declarations,
            "sheriff_claims": self.sheriff_claims
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Player':
        """Create a Player object from a dictionary"""
        player = cls(
            player_id=data["player_id"],
            role=Role[data["role"]]
        )
        player.alive = data["alive"]
        player.declarations = data["declarations"]
        player.sheriff_claims = data["sheriff_claims"]
        return player
    
    def get_observation(self, is_self: bool = False) -> Dict:
        """
        Get the observation object for this player.
        If is_self is True, include private information.
        """
        obs = {
            "player_id": self.player_id,
            "alive": self.alive,
            "declarations": self.declarations,
            "sheriff_claims": self.sheriff_claims
        }
        
        if is_self:
            obs["role"] = self.role.name
            obs["private_info"] = self._private_info
        
        return obs


class GameState:
    """Represents the complete state of a game"""
    
    def __init__(self):
        self.players = []
        self.current_phase = Phase.DECLARATION
        self.turn = 0
        self.active_player = 0
        self.phase_start_player = 0
        self.next_day_first_player = 0  # Track the player who should start the next day
        self.nominated_players = []
        self.tied_players = []
        self.voting_round = 0
        self.eliminate_all_votes = [0] * 10
        self.night_kills = [False] * 10
        self.winner = None
        self.game_log = []
        
        # Private information tracking
        self.private_checks = {}  # player_id -> {target_id -> check_result}
    
    @classmethod
    def new_game(cls) -> 'GameState':
        """Create a new game with randomized roles"""
        game = cls()
        
        # Create list of roles
        roles = ([Role.CITIZEN] * 6) + [Role.SHERIFF] + ([Role.MAFIA] * 2) + [Role.DON]
        random.shuffle(roles)
        
        # Create players with assigned roles
        game.players = [Player(i, role) for i, role in enumerate(roles)]
        
        # Assign mafia knowledge (mafia players know each other)
        mafia_indices = [i for i, p in enumerate(game.players) 
                         if p.role in [Role.MAFIA, Role.DON]]
        
        for idx in mafia_indices:
            game.players[idx]._private_info["mafia_team"] = mafia_indices
        
        return game
    
    def to_dict(self) -> Dict:
        """Convert GameState to dictionary for serialization"""
        return {
            "players": [p.to_dict() for p in self.players],
            "current_phase": self.current_phase.name,
            "turn": self.turn,
            "active_player": self.active_player,
            "nominated_players": self.nominated_players,
            "tied_players": self.tied_players,
            "voting_round": self.voting_round,
            "winner": self.winner.name if self.winner else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GameState':
        """Create a GameState from a dictionary"""
        game = cls()
        game.players = [Player.from_dict(p) for p in data["players"]]
        game.current_phase = Phase[data["current_phase"]]
        game.turn = data["turn"]
        game.active_player = data["active_player"]
        game.nominated_players = data["nominated_players"]
        game.tied_players = data["tied_players"]
        game.voting_round = data["voting_round"]
        game.winner = Team[data["winner"]] if data["winner"] else None
        return game
    
    def get_valid_actions(self) -> Dict[str, Any]:
        """
        Get the valid actions for the current active player based on phase
        and role
        """
        actions = {}
        player = self.players[self.active_player]
        
        if not player.alive:
            return actions
        
        if self.current_phase == Phase.DECLARATION:
            # All alive players can make declarations
            actions["declaration"] = "vector_10"
            actions["sheriff_claims"] = "matrix_10x10"
            
            # Can nominate any other alive player
            valid_nominations = [-1]  # -1 means "skip nomination"
            for i, p in enumerate(self.players):
                if p.alive and i != self.active_player and i not in self.nominated_players:
                    valid_nominations.append(i)
            
            actions["nomination"] = valid_nominations
        
        elif self.current_phase == Phase.VOTING:
            if self.voting_round == 2:
                # Eliminate all vote
                actions["eliminate_all"] = [True, False]
            else:
                # Regular voting - only include alive players from the target list
                if self.voting_round == 0:
                    valid_targets = [t for t in self.nominated_players if self.players[t].alive]
                    # If no nominations occurred, include all other alive players as targets
                    if not valid_targets:
                        valid_targets = [i for i, p in enumerate(self.players) 
                                         if p.alive and i != self.active_player]
                else:
                    valid_targets = [t for t in self.tied_players if self.players[t].alive]
                    # If tied_players is empty or all tied players are dead, reset to regular voting
                    if not valid_targets:
                        self.voting_round = 0
                        self.tied_players = []
                        valid_targets = [i for i, p in enumerate(self.players) 
                                         if p.alive and i != self.active_player]
                
                actions["vote"] = valid_targets
        
        elif self.current_phase == Phase.NIGHT_KILL:
            # Only Mafia/Don can kill
            if player.role in [Role.MAFIA, Role.DON]:
                # Find if this is the active killer
                killer_idx = self._get_active_killer()
                if killer_idx == self.active_player:
                    valid_targets = [-1]  # -1 means "skip kill"
                    for i, p in enumerate(self.players):
                        if p.alive and i != self.active_player:
                            valid_targets.append(i)
                    
                    actions["kill"] = valid_targets
        
        elif self.current_phase == Phase.NIGHT_DON:
            # Only Don can check
            if player.role == Role.DON:
                valid_targets = []
                for i, p in enumerate(self.players):
                    if p.alive and i != self.active_player:
                        valid_targets.append(i)
                
                actions["don_check"] = valid_targets
        
        elif self.current_phase == Phase.NIGHT_SHERIFF:
            # Only Sheriff can check
            if player.role == Role.SHERIFF:
                valid_targets = []
                for i, p in enumerate(self.players):
                    if p.alive and i != self.active_player:
                        valid_targets.append(i)
                
                actions["sheriff_check"] = valid_targets
        
        return actions
    
    def _get_active_killer(self) -> int:
        """Get the player index of the active killer (Don or first alive Mafia)"""
        # First, check for Don
        for i, player in enumerate(self.players):
            if player.role == Role.DON and player.alive:
                return i
        
        # Then, check for first Mafia
        for i, player in enumerate(self.players):
            if player.role == Role.MAFIA and player.alive:
                return i
        
        return -1  # No killer found (shouldn't happen in normal gameplay)
    
    def get_observation(self, player_id: int) -> Dict[str, Any]:
        """
        Get the observation object for the given player.
        This includes public info and private info specific to the player.
        """
        if player_id < 0 or player_id >= len(self.players):
            raise ValueError(f"Invalid player_id: {player_id}")
        
        # Basic game state info
        observation = {
            "turn": self.turn,
            "phase": self.current_phase.name,
            "alive_players": [i for i, p in enumerate(self.players) if p.alive],
            "nominated_players": self.nominated_players,
            "tied_players": self.tied_players if self.voting_round > 0 else []
        }
        
        # Player's own role and private information
        player = self.players[player_id]
        observation["role"] = player.role.name
        
        # Private information
        private_info = {}
        
        # Mafia team knowledge
        if player.role in [Role.MAFIA, Role.DON]:
            private_info["mafia_team"] = player._private_info.get("mafia_team", [])
        
        # Don check results
        if player.role == Role.DON and player_id in self.private_checks:
            private_info["don_checks"] = {}
            for target_id, result in self.private_checks[player_id].items():
                if isinstance(result, bool):  # Only include don checks
                    private_info["don_checks"][target_id] = result
        
        # Sheriff check results
        if player.role == Role.SHERIFF and player_id in self.private_checks:
            private_info["sheriff_checks"] = {}
            for target_id, result in self.private_checks[player_id].items():
                if isinstance(result, Team):  # Only include sheriff checks
                    private_info["sheriff_checks"][target_id] = result.name
        
        observation["private_info"] = private_info
        
        # Public information about other players
        observation["players"] = []
        for i, p in enumerate(self.players):
            player_info = {
                "player_id": i,
                "alive": p.alive,
                "declarations": p.declarations,
                "sheriff_claims": p.sheriff_claims
            }
            observation["players"].append(player_info)
        
        # Known roles (e.g., eliminated players, but roles should remain hidden)
        observation["known_roles"] = {}
        for i, p in enumerate(self.players):
            if not p.alive:  # Track eliminated players but don't reveal roles
                observation["known_roles"][i] = "UNKNOWN"
        
        return observation
    
    def apply_declaration(self, player_id: int, declarations: List[int], sheriff_claims: List[List[int]] = None) -> None:
        """Apply a declaration action from a player"""
        if not self.players[player_id].alive:
            raise ValueError(f"Player {player_id} is not alive")
        
        if len(declarations) != 10:
            raise ValueError("Declaration vector must have length 10")
        
        # Validate declaration values are between -3 and 3
        for value in declarations:
            if value < -3 or value > 3:
                raise ValueError("Declaration values must be between -3 and 3")
        
        self.players[player_id].declarations = declarations
        
        if sheriff_claims:
            if not isinstance(sheriff_claims, list):
                raise ValueError("Sheriff claims must be a list of lists")
            
            # Validate sheriff claims (must be 10x10 matrix)
            if len(sheriff_claims) != 10:
                raise ValueError("Sheriff claims must be a 10x10 matrix (10 rows)")
                
            for claim in sheriff_claims:
                if len(claim) != 10:
                    raise ValueError("Each sheriff claim vector must have length 10")
                for value in claim:
                    if value not in [-1, 0, 1]:
                        raise ValueError("Sheriff claim values must be -1, 0, or 1")
            
            self.players[player_id].sheriff_claims = sheriff_claims
    
    def apply_nomination(self, player_id: int, target_id: int) -> None:
        """Apply a nomination action from a player"""
        if not self.players[player_id].alive:
            raise ValueError(f"Player {player_id} is not alive")
        
        if target_id != -1:  # -1 means skip nomination
            if target_id < 0 or target_id >= len(self.players):
                raise ValueError(f"Invalid target player: {target_id}")
            
            if not self.players[target_id].alive:
                raise ValueError(f"Cannot nominate dead player {target_id}")
            
            if target_id == player_id:
                raise ValueError("Player cannot nominate themselves")
            
            if target_id in self.nominated_players:
                raise ValueError(f"Player {target_id} is already nominated")
            
            self.nominated_players.append(target_id)
    
    def apply_vote(self, player_id: int, target_id: int) -> None:
        """Apply a vote action from a player"""
        if not self.players[player_id].alive:
            raise ValueError(f"Player {player_id} is not alive")
        
        if target_id < 0 or target_id >= len(self.players):
            raise ValueError(f"Invalid target player: {target_id}")
        
        if not self.players[target_id].alive:
            raise ValueError(f"Cannot vote for dead player {target_id}")
        
        # Validate vote target based on voting round
        if self.voting_round == 0:
            # If no nominations occurred, any alive player other than self is valid
            if not self.nominated_players:
                if player_id == target_id:
                    raise ValueError(f"Player cannot vote for themselves")
            elif target_id not in self.nominated_players:
                raise ValueError(f"Player {target_id} is not nominated")
        elif self.voting_round == 1 and target_id not in self.tied_players:
            raise ValueError(f"Player {target_id} is not in tied players")
        
        self.players[player_id].vote_for = target_id
    
    def apply_eliminate_all_vote(self, player_id: int, vote: bool) -> None:
        """Apply an eliminate-all vote from a player"""
        if not self.players[player_id].alive:
            raise ValueError(f"Player {player_id} is not alive")
        
        if self.voting_round != 2:
            raise ValueError("Eliminate-all vote is only available in the third voting round")
        
        self.eliminate_all_votes[player_id] = 1 if vote else 0
    
    def apply_kill(self, target_id: int) -> None:
        """Apply a night kill action"""
        if target_id == -1:  # Skip kill
            return
        
        if target_id < 0 or target_id >= len(self.players):
            raise ValueError(f"Invalid target player: {target_id}")
        
        if not self.players[target_id].alive:
            raise ValueError(f"Cannot kill dead player {target_id}")
        
        # Mark the player for night kill (not actually killed until night phase end)
        self.night_kills[target_id] = True
    
    def apply_don_check(self, target_id: int) -> bool:
        """
        Apply a don check action
        Returns True if the target is Sheriff, False otherwise
        """
        if target_id < 0 or target_id >= len(self.players):
            raise ValueError(f"Invalid target player: {target_id}")
        
        if not self.players[target_id].alive:
            raise ValueError(f"Cannot check dead player {target_id}")
        
        # Check if target is Sheriff
        is_sheriff = self.players[target_id].role == Role.SHERIFF
        
        # Store result in private checks
        don_id = self.active_player
        if don_id not in self.private_checks:
            self.private_checks[don_id] = {}
        
        self.private_checks[don_id][target_id] = is_sheriff
        
        return is_sheriff
    
    def apply_sheriff_check(self, target_id: int) -> Team:
        """
        Apply a sheriff check action
        Returns Team.BLACK if target is Mafia/Don, Team.RED otherwise
        """
        if target_id < 0 or target_id >= len(self.players):
            raise ValueError(f"Invalid target player: {target_id}")
        
        if not self.players[target_id].alive:
            raise ValueError(f"Cannot check dead player {target_id}")
        
        # Check target's team
        target_team = self.players[target_id].team
        
        # Store result in private checks
        sheriff_id = self.active_player
        if sheriff_id not in self.private_checks:
            self.private_checks[sheriff_id] = {}
        
        self.private_checks[sheriff_id][target_id] = target_team
        
        return target_team
    
    def _advance_player(self) -> bool:
        """
        Advance to the next alive player
        Returns True if we've completed a full cycle of players
        """
        original_player = self.active_player
        while True:
            self.active_player = (self.active_player + 1) % len(self.players)
            
            # If we've gone through all players and returned to the starting player
            if self.active_player == self.phase_start_player:
                return True
            
            # If we found an alive player, stop searching
            if self.players[self.active_player].alive:
                return False
            
            # If we've checked all players and none are alive (shouldn't happen in normal gameplay)
            if self.active_player == original_player:
                return True
    
    def _transition_phase(self) -> None:
        """Transition to the next game phase based on current phase"""
        if self.current_phase == Phase.DECLARATION:
            # Always transition to voting phase, even if there are no nominations
            self.current_phase = Phase.VOTING
            
            # Reset for start of voting
            self.active_player = self._find_first_alive_player()
            self.phase_start_player = self.active_player
            self.voting_round = 0  # Ensure voting round is properly reset
            
        elif self.current_phase == Phase.VOTING:
            # Transition to night kill phase
            self.current_phase = Phase.NIGHT_KILL
            
            # Set active player to the killer (Don or first Mafia)
            killer_idx = self._get_active_killer()
            if killer_idx != -1:
                self.active_player = killer_idx
                self.phase_start_player = self.active_player
            else:
                # No killers alive, skip to next phase
                self.current_phase = Phase.NIGHT_DON
                self._transition_phase()
                
        elif self.current_phase == Phase.NIGHT_KILL:
            # Transition to don check phase
            self.current_phase = Phase.NIGHT_DON
            
            # Find the Don if alive
            don_idx = -1
            for i, player in enumerate(self.players):
                if player.role == Role.DON and player.alive:
                    don_idx = i
                    break
            
            if don_idx != -1:
                self.active_player = don_idx
                self.phase_start_player = self.active_player
            else:
                # No Don alive, skip to next phase
                self.current_phase = Phase.NIGHT_SHERIFF
                self._transition_phase()
                
        elif self.current_phase == Phase.NIGHT_DON:
            # Transition to sheriff check phase
            self.current_phase = Phase.NIGHT_SHERIFF
            
            # Find the Sheriff if alive
            sheriff_idx = -1
            for i, player in enumerate(self.players):
                if player.role == Role.SHERIFF and player.alive:
                    sheriff_idx = i
                    break
            
            if sheriff_idx != -1:
                self.active_player = sheriff_idx
                self.phase_start_player = self.active_player
            else:
                # No Sheriff alive, finish night phase
                self._process_night_end()
                self.current_phase = Phase.DECLARATION
                self.turn += 1
                self._set_next_day_first_player()
                
        elif self.current_phase == Phase.NIGHT_SHERIFF:
            # Finish night phase
            self._process_night_end()
            
            # Check win conditions
            winner = self.check_win_condition()
            if winner:
                self.winner = winner
                self.current_phase = Phase.GAME_OVER
            else:
                # Start next day
                self.current_phase = Phase.DECLARATION
                self.turn += 1
                self._set_next_day_first_player()
    
    def _process_night_end(self) -> None:
        """Process the end of the night phase"""
        # Apply night kills
        for i, killed in enumerate(self.night_kills):
            if killed:
                self.players[i].alive = False
                self.game_log.append(f"Player {i} was killed during the night")
        
        # Reset night kills for next night
        self.night_kills = [False] * len(self.players)
    
    def _find_first_alive_player(self) -> int:
        """Find the index of the first alive player"""
        for i, player in enumerate(self.players):
            if player.alive:
                return i
        return 0  # Shouldn't happen in normal gameplay
        
    def _set_next_day_first_player(self) -> None:
        """Set the first player for the next day, ensuring player rotation"""
        # Start search from the player after the current day's first player
        start_idx = (self.next_day_first_player + 1) % len(self.players)
        current_idx = start_idx
        
        # Search for the first alive player starting from next_day_first_player + 1
        found_alive_player = False
        while not found_alive_player:
            if self.players[current_idx].alive:
                self.active_player = current_idx
                self.phase_start_player = current_idx
                self.next_day_first_player = current_idx  # Update for next day
                found_alive_player = True
            else:
                current_idx = (current_idx + 1) % len(self.players)
            
            # If we've checked all players and made a full circle, use first alive
            if current_idx == start_idx and not found_alive_player:
                # Fall back to finding any alive player
                self.active_player = self._find_first_alive_player()
                self.phase_start_player = self.active_player
                self.next_day_first_player = self.active_player
                break
    
    def _resolve_votes(self) -> Optional[int]:
        """
        Resolve the voting phase
        Returns the player index of the eliminated player, or None if no player was eliminated
        """
        # Count the votes for each player
        vote_counts = [0] * len(self.players)
        
        # Count votes
        for player in self.players:
            if player.alive and player.vote_for is not None:
                vote_counts[player.vote_for] += 1
        
        # Find the player(s) with the most votes
        max_votes = max(vote_counts) if sum(vote_counts) > 0 else 0
        if max_votes == 0:
            # No votes cast
            self.voting_round = 0
            return None
        
        players_with_max_votes = [i for i, count in enumerate(vote_counts) if count == max_votes]
        
        # If only one player has the most votes, eliminate them
        if len(players_with_max_votes) == 1:
            eliminated_player = players_with_max_votes[0]
            self.players[eliminated_player].alive = False
            self.game_log.append(f"Player {eliminated_player} was eliminated by vote")
            
            # Reset voting state
            self.voting_round = 0
            for player in self.players:
                player.vote_for = None
                
            return eliminated_player
        
        # If there's a tie
        if self.voting_round == 0:
            # First round tie - move to second round
            self.tied_players = players_with_max_votes
            self.voting_round = 1
            
            # Reset votes
            for player in self.players:
                player.vote_for = None
                
            return None
            
        elif self.voting_round == 1:
            # Second round tie - move to third round
            self.tied_players = players_with_max_votes
            self.voting_round = 2
            
            # Reset votes and prepare for eliminate-all vote
            for player in self.players:
                player.vote_for = None
                
            self.eliminate_all_votes = [0] * len(self.players)
            
            return None
    
    def _resolve_eliminate_all_vote(self) -> None:
        """Resolve the vote to eliminate all tied players"""
        # Count the number of alive players
        alive_players_count = sum(1 for p in self.players if p.alive)
        
        # Count yes votes
        yes_votes = sum(self.eliminate_all_votes)
        
        # If more than half of alive players voted yes, eliminate all tied players
        if yes_votes > alive_players_count / 2:
            for player_id in self.tied_players:
                self.players[player_id].alive = False
                self.game_log.append(f"Player {player_id} was eliminated by majority vote")
        
        # Reset voting state
        self.voting_round = 0
        self.tied_players = []
        self.eliminate_all_votes = [0] * len(self.players)
    
    def check_win_condition(self) -> Optional[Team]:
        """
        Check if either team has won the game
        Returns the winning team or None if the game continues
        """
        # Count alive players by team
        red_count = sum(1 for p in self.players if p.alive and p.team == Team.RED)
        black_count = sum(1 for p in self.players if p.alive and p.team == Team.BLACK)
        
        # Black team wins if they have equal or greater numbers than Red team
        if black_count >= red_count:
            return Team.BLACK
        
        # Red team wins if all Black team players are eliminated
        if black_count == 0:
            return Team.RED
        
        # Game continues
        return None


class ActionRequest:
    """Request from the server to a client to take an action"""
    
    def __init__(self, type: str, player_id: int, phase: str, valid_actions: Dict, observation: Dict):
        self.type = type
        self.player_id = player_id
        self.phase = phase
        self.valid_actions = valid_actions
        self.observation = observation
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "type": self.type,
            "player_id": self.player_id,
            "phase": self.phase,
            "valid_actions": self.valid_actions,
            "observation": self.observation
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ActionRequest':
        """Create from dictionary"""
        return cls(
            type=data["type"],
            player_id=data["player_id"],
            phase=data["phase"],
            valid_actions=data["valid_actions"],
            observation=data["observation"]
        )


class ActionResponse:
    """Response from a client to the server with their chosen action"""
    
    def __init__(self, type: str, player_id: int, action: Dict):
        self.type = type
        self.player_id = player_id
        self.action = action
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "type": self.type,
            "player_id": self.player_id,
            "action": self.action
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ActionResponse':
        """Create from dictionary"""
        return cls(
            type=data["type"],
            player_id=data["player_id"],
            action=data["action"]
        )


class GameEvent:
    """Event notification from the server to clients"""
    
    def __init__(self, type: str, event: str, **kwargs):
        self.type = type
        self.event = event
        self.__dict__.update(kwargs)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = {
            "type": self.type,
            "event": self.event
        }
        # Add any additional fields
        for key, value in self.__dict__.items():
            if key not in ["type", "event"]:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GameEvent':
        """Create from dictionary"""
        event_data = data.copy()
        event_type = event_data.pop("type")
        event = event_data.pop("event")
        return cls(type=event_type, event=event, **event_data)
