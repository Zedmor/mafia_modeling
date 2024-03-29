from abc import ABC, abstractmethod
from enum import Enum

import numpy as np
import torch

from mafia_game.common import Check, Role, Team


# TODO: Add serialization to vector

class InputTypes(Enum):
    VECTOR = 0
    INDEX = 1


class FromIndexTargetPlayerMixin:
    @classmethod
    def from_index(cls, action_index, game_state, player_index):
        # Create an instance of NominationAction using the action_index
        return cls(player_index, action_index)


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
        return mask



class BeliefAction(Action):
    action_size = 30

    input_type = InputTypes.VECTOR

    def __init__(self, player_index, beliefs):
        self.player_index = player_index
        self.beliefs = beliefs

    def apply(self, game_state: "CompleteGameState"):
        game_state.game_states[self.player_index].public_data.beliefs.checks[
            game_state.turn
        ] = self.beliefs

    @staticmethod
    def normalize_vector(output_vector):
        # The output_vector is expected to be a tensor of shape (10, 3)
        # where each row is the probability distribution over the teams for each player.
        reshaped_output_vector = output_vector.view(10, 3)

        # Convert the output probabilities to scalar beliefs by taking the argmax over the second dimension
        beliefs = reshaped_output_vector.argmax(dim=1).tolist()  # Convert to a list of scalar beliefs
        return beliefs


    @classmethod
    def from_output_vector(cls, output_vector, game_state, player_index):
        beliefs = cls.normalize_vector(output_vector)
        return cls(player_index, Check.deserialize(np.array(beliefs)))


    def __repr__(self):
        return f"Player {self.player_index}. Beliefs: {[self.beliefs]}"


class KillAction(Action, FromIndexTargetPlayerMixin):
    red_team = False

    def __init__(self, player_index, target_player):
        self.player_index = player_index
        self.target_player = target_player

    def apply(self, game_state: "CompleteGameState"):
        # Apply the kill action to the game state
        # target_player is the index of the player to be killed
        game_state.game_states[self.player_index].public_data.kills.checks[
            game_state.turn
        ][self.target_player] = 1
        # Mark the player as dead in the game state
        game_state.game_states[self.target_player].alive = 0

    def __repr__(self):
        return f"Player {self.player_index}. Kills: {self.target_player}"

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        mask = torch.ones(cls.action_size, dtype=torch.float32)
        for i, player_state in enumerate(game_state.game_states):
            if not player_state.alive or i == player_index:
                mask[i] = 0

        return mask


class NominationAction(Action, FromIndexTargetPlayerMixin):
    def __init__(self, player_index, target_player):
        self.player_index = player_index
        self.target_player = target_player

    def apply(self, game_state: "CompleteGameState"):
        # Apply the nomination action to the game state
        # target_player is the index of the player to be nominated
        game_state.nominated_players.append(self.target_player)
        game_state.game_states[self.player_index].public_data.nominations.checks[
            game_state.turn
        ][self.target_player] = 1

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        mask = torch.ones(cls.action_size, dtype=torch.float32)
        for i, player_state in enumerate(game_state.game_states):
            if not player_state.alive or i == player_index:
                mask[i] = 0

        return mask

    def __repr__(self):
        return f"Player {self.player_index}. Nominates: {self.target_player}"


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

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        mask = torch.ones(cls.action_size, dtype=torch.float32)
        return mask

    def __repr__(self):
        return f"Player {self.player_index} (Don). Checks: {self.target_player}"


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

    def __repr__(self):
        return f"Player {self.player_index} (Sheriff). Checks: {self.target_player}"


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

    @classmethod
    def generate_action_mask(cls, game_state: "CompleteGameState", player_index):
        # This mask is different, votes are disabled by default
        # and only voting for nominated players is allowed
        mask = torch.zeros(cls.action_size, dtype=torch.float32)
        for index in game_state.nominated_players:
            mask[index] = 1
        return mask

    def __repr__(self):
        return f"Player {self.player_index}. Votes: {self.target_player}"
