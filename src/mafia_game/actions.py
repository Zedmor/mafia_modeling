from abc import ABC, abstractmethod
from enum import Enum

import numpy as np
import torch

from mafia_game.common import Check, Role, Team
from mafia_game.logger import LogType


# TODO: Add serialization to vector

class InputTypes(Enum):
    VECTOR = 0
    INDEX = 1


class FromIndexTargetPlayerMixin:
    @classmethod
    def from_index(cls, target_player, game_state, player_index):
        # Create an instance of NominationAction using the action_index
        return cls(player_index, target_player)


class Action(ABC):
    action_size = 10
    red_team = True
    black_team = True

    input_type = InputTypes.INDEX

    def __init__(self, player_index):
        self.player_index = player_index

    @abstractmethod
    def apply(self, game_state: "CompleteGameState", *args):
        pass

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        mask = torch.ones(cls.action_size, dtype=torch.float32)
        for i, player_state in enumerate(game_state.game_states):
            if not player_state.alive:
                mask[i] = 0

        return mask


class NullAction(Action):

    def __repr__(self):
        return "Player {} makes no action".format(self.player_index)

    def apply(self, game_state: "CompleteGameState", *args):
        pass
        # game_state.log(self.__repr__())


class KillAction(Action, FromIndexTargetPlayerMixin):
    red_team = False

    def __init__(self, player_index, target_player):
        self.player_index = player_index
        self.target_player = target_player

    def apply(self, game_state: "CompleteGameState"):
        if game_state.game_states[self.target_player].alive == 0:
            raise RuntimeError("Killing dead player")
        # Apply the kill action to the game state
        # target_player is the index of the player to be killed
        game_state.game_states[self.player_index].public_data.kills.checks[
            game_state.turn
        ][self.target_player] = 1
        # Mark the player as dead in the game state
        game_state.game_states[self.target_player].alive = -1
        game_state.final_speech()
        game_state.log(self.__repr__(), player_index=self.player_index, log_type=LogType.KILL_ACTION)

    def __repr__(self):
        return f"Игрок {self.player_index}. убивает: {self.target_player}"


class NominationAction(Action, FromIndexTargetPlayerMixin):
    def __init__(self, player_index, target_player):
        self.player_index = player_index
        self.target_player = target_player

    def apply(self, game_state: "CompleteGameState"):
        # Apply the nomination action to the game state
        # target_player is the index of the player to be nominated
        if game_state.game_states[self.target_player].alive == 0:
            raise RuntimeError("Nominating dead player")
        game_state.nominated_players.append(self.target_player)
        game_state.game_states[self.player_index].public_data.nominations.checks[
            game_state.turn
        ][self.target_player] = 1
        game_state.log(self.__repr__(), log_type=LogType.VOTE_ACTION)

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        mask = torch.ones(cls.action_size, dtype=torch.float32)
        for i, player_state in enumerate(game_state.game_states):
            if not player_state.alive or i == player_index or i in game_state.nominated_players:
                mask[i] = 0

        return mask

    def __repr__(self):
        return f"Игрок {self.player_index}. номинирует: {self.target_player}"


class DonCheckAction(Action, FromIndexTargetPlayerMixin):
    red_team = False

    def __init__(self, player_index, target_player):
        self.player_index = player_index
        self.target_player = target_player

    def apply(self, game_state: "CompleteGameState"):
        # The check result is 1 if the target player is the Sheriff, 0 otherwise
        check_result = (
            1
            if game_state.game_states[self.target_player].private_data.role
            == Role.SHERIFF
            else 0
        )
        # Store the check result in the don_checks for the current turn
        game_state.game_states[self.player_index].private_data.don_checks.checks[
            game_state.turn
        ][self.target_player] = check_result

        game_state.log(f"{self.__repr__()}. Этот игрок {'шериф' if check_result else 'не шериф'}", log_type=LogType.DON_CHECK, player_index=self.player_index)


    def __repr__(self):
        return f"Игрок {self.player_index} (Дон). Проверяет: {self.target_player}"


class SheriffCheckAction(Action, FromIndexTargetPlayerMixin):
    black_team = False

    def __init__(self, player_index, target_player):
        self.player_index = player_index
        self.target_player = target_player

    def apply(self, game_state: "CompleteGameState"):
        # The check result is the team of the target player
        check_result = game_state.game_states[self.target_player].private_data.role
        if check_result == Role.MAFIA or check_result == Role.DON:
            check_result = Team.BLACK_TEAM
        else:
            check_result = Team.RED_TEAM
        # Store the check result in the sheriff_checks for the current turn
        game_state.game_states[self.player_index].private_data.sheriff_checks.checks[
            game_state.turn
        ][self.target_player] = check_result.value
        game_state.log(f"{self.__repr__()} это: {'мафия' if check_result == Team.BLACK_TEAM else 'не мафия'}", log_type=LogType.SHERIFF_CHECK, player_index=self.player_index)

    def __repr__(self):
        return f"Игрок {self.player_index} (Шериф). проверяет: {self.target_player}"


class SheriffDeclarationAction(Action):
    action_size = 2

    def __init__(self, player_index, i_am_sheriff: bool):
        self.player_index = player_index
        self.i_am_sheriff = i_am_sheriff

    def apply(self, game_state: "CompleteGameState"):
        game_state.game_states[self.player_index].public_data.sheriff_declaration[
            game_state.turn
        ] = self.i_am_sheriff

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        return torch.ones(cls.action_size, dtype=torch.float32)

    @classmethod
    def from_index(cls, action_index, game_state, player_index):
        # 0 - I am sheriff
        # 1 - I am not a sheriff
        return cls(player_index, action_index == 0)

    def __repr__(self):
        return (
            f"Player {self.player_index}. Declares is he a sheriff: {self.i_am_sheriff}"
        )


class PublicSheriffDeclarationAction(Action):
    action_size = 20

    def __init__(self, player_index, target_player: int, team: Team):
        self.player_index = player_index
        self.target_player = target_player
        self.role = team

    def apply(self, game_state: "CompleteGameState"):
        game_state.game_states[
            self.player_index
        ].public_data.public_sheriff_checks.checks[game_state.turn][
            self.target_player
        ] = self.role.value

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        # Can claim sheriff checks about any alive player except self
        mask = torch.zeros(cls.action_size, dtype=torch.float32)
        for i, player_state in enumerate(game_state.game_states):
            if player_state.alive and i != player_index:
                # Allow both RED and BLACK declarations for this player
                mask[i * 2] = 1      # RED declaration  
                mask[i * 2 + 1] = 1  # BLACK declaration
        return mask

    @classmethod
    def from_index(cls, action_index, game_state, player_index):
        # Determine the target player based on the action_index
        target_player = action_index // 2  # Integer division to get the player index

        # Determine the team based on the action_index
        team = Team.BLACK_TEAM if action_index % 2 == 0 else Team.RED_TEAM

        return cls(player_index, target_player, team)

    def __repr__(self):
        return (
            f"Player {self.player_index}. Declares sheriff check: "
            f"{self.target_player}: {self.role}"
        )


class VoteAction(Action, FromIndexTargetPlayerMixin):
    def __init__(self, player_index, target_player):
        self.player_index = player_index
        self.target_player = target_player

    def apply(self, game_state: "CompleteGameState"):
        game_state.game_states[self.player_index].public_data.votes.checks[
            game_state.turn
        ][self.target_player] = 1
        game_state.log(self.__repr__(), log_type=LogType.VOTE_ACTION)

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        # This mask is different, votes are disabled by default
        # and only voting for nominated players is allowed
        mask = torch.zeros(cls.action_size, dtype=torch.float32)
        
        if game_state.voting_round == 0:
            # First round: vote for nominated players
            for index in game_state.nominated_players:
                mask[index] = 1
        elif game_state.voting_round == 1:
            # Second round: vote for tied players
            for index in game_state.tied_players:
                mask[index] = 1
        
        return mask

    def __repr__(self):
        return f"Игрок {self.player_index}. Голосует против: {self.target_player}"


class EliminateAllNominatedVoteAction(Action):
    action_size = 2  # Yes (1) or No (0)

    def __init__(self, player_index, eliminate_all: bool):
        self.player_index = player_index
        self.eliminate_all = eliminate_all

    def apply(self, game_state: "CompleteGameState"):
        # Record the player's vote on eliminating all tied players
        game_state.eliminate_all_votes[self.player_index] = 1 if self.eliminate_all else 0
        game_state.log(self.__repr__(), log_type=LogType.VOTE_RESULT)

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        # Always allow voting yes or no
        return torch.ones(cls.action_size, dtype=torch.float32)

    @classmethod
    def from_index(cls, action_index, game_state, player_index):
        # Create an instance using the action_index (0 = No, 1 = Yes)
        return cls(player_index, eliminate_all=(action_index == 1))

    def __repr__(self):
        return f"Player {self.player_index}. Votes {'to eliminate' if self.eliminate_all else 'not to eliminate'} all tied players"


class SayAction(Action):
    action_size = 20  # 10 players × 2 colors

    def __init__(self, player_index, target_player: int, team: Team):
        self.player_index = player_index
        self.target_player = target_player
        self.team = team

    def apply(self, game_state: "CompleteGameState"):
        # Record the player's declaration about another player's team
        # For now, we'll store this in a similar way to public sheriff checks
        # This represents a public statement about a player's team affiliation
        game_state.log(self.__repr__(), log_type=LogType.OTHER)

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        # Can declare about any alive player except self
        mask = torch.zeros(cls.action_size, dtype=torch.float32)
        for i, player_state in enumerate(game_state.game_states):
            if player_state.alive and i != player_index:
                # Allow both RED and BLACK declarations for this player
                mask[i * 2] = 1      # RED declaration  
                mask[i * 2 + 1] = 1  # BLACK declaration
        return mask

    @classmethod
    def from_index(cls, action_index, game_state, player_index):
        # Determine the target player and team based on the action_index
        target_player = action_index // 2  # Integer division to get the player index
        team = Team.RED_TEAM if action_index % 2 == 0 else Team.BLACK_TEAM
        return cls(player_index, target_player, team)

    def __repr__(self):
        team_name = "innocent" if self.team == Team.RED_TEAM else "mafia"
        return f"Player {self.player_index} declares Player {self.target_player} is {team_name}"
