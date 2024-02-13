from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, Type

import numpy as np

from mafia_game.actions import (
    BeliefAction,
    DonCheckAction,
    KillAction,
    NominationAction,
    PublicSheriffDeclarationAction,
    SheriffCheckAction,
    SheriffDeclarationAction,
    VoteAction,
)
from mafia_game.common import (
    ARRAY_SIZE,
    Beliefs,
    Booleans,
    Checks,
    DeserializeMixin, Kills,
    MAX_PLAYERS,
    MAX_TURNS,
    Nominations,
    Role,
    SerializeMixin, T, Team,
    Votes,
    )
from mafia_game.logger import logger


@dataclass
class OtherMafias(SerializeMixin, DeserializeMixin):

    other_mafias: np.array = field(default_factory=lambda: np.array([-1, -1, -1]))

    @classmethod
    def expected_size(cls):
        return 3

    def serialize(self):
        return self.other_mafias

    @classmethod
    def deserialize(cls: Type[T], serialized_data: np.ndarray) -> T:
        return OtherMafias(other_mafias=serialized_data)

@dataclass
class PrivateData(SerializeMixin, DeserializeMixin):
    role: Role
    sheriff_checks: Checks = field(default_factory=Checks)
    don_checks: Checks = field(default_factory=Checks)
    other_mafias: OtherMafias = field(default_factory=OtherMafias)

    @property
    def team(self):
        if self.role == Role.DON or self.role == Role.MAFIA:
            return Team.BLACK_TEAM
        return Team.RED_TEAM


@dataclass
class PublicData(SerializeMixin, DeserializeMixin):
    beliefs: Beliefs = field(default_factory=Beliefs)
    nominations: Nominations = field(default_factory=Nominations)
    votes: Votes = field(default_factory=Votes)
    sheriff_declaration: Booleans = field(default_factory=Booleans)
    public_sheriff_checks: Checks = field(default_factory=Checks)
    kills: Kills = field(default_factory=Kills)


@dataclass
class GameState(SerializeMixin, DeserializeMixin):
    private_data: PrivateData
    public_data: PublicData
    alive: int = field(default=1)

    def set_winner(self, team: Team):
        # Set the winning team
        if not isinstance(team, Team):
            raise ValueError("Invalid team type")
        self.team_won = team


class Phase:
    allowed_actions = []

    @staticmethod
    def from_value(value):
        for subclass in Phase.__subclasses__():
            if subclass.value == value:
                return subclass()

    def execute_action(self, game_state: "CompleteGameState", action):
        # Accept only VoteAction during the voting phase
        if any(isinstance(action, clazz) for clazz in self.allowed_actions):
            action.apply(game_state)
        else:
            raise ValueError(
                f"Action {action.__class__} is not allowed during {self.__class__} phase"
            )

    @abstractmethod
    def next_phase(self, game_state: "CompleteGameState"):
        pass


class DayPhase(Phase):
    value = 0

    allowed_actions = [
        BeliefAction,
        NominationAction,
        SheriffDeclarationAction,
        PublicSheriffDeclarationAction,
    ]

    def next_phase(self, game_state: "CompleteGameState"):
        # Transition to the voting phase after all players have taken their actions
        return VotingPhase()

    def __repr__(self):
        return f"DayPhase"


class VotingPhase(Phase):
    allowed_actions = [VoteAction]
    value = 1

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        if game_state.nominated_players:
            game_state.resolve_votes()
            game_state.nominated_players = []
        else:
            logger.info("Nobody had been nominated. Skipping vote.")
        return NightKillPhase()

    def __repr__(self):
        return f"VotingPhase"


class NightKillPhase(Phase):
    allowed_actions = [KillAction]
    value = 2

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        return NightDonPhase()

    def __repr__(self):
        return f"NightKillPhase"


class NightDonPhase(Phase):
    allowed_actions = [DonCheckAction]
    value = 3

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        return NightSheriffPhase()

    def __repr__(self):
        return f"NightDonPhase"

class NightSheriffPhase(Phase):
    allowed_actions = [SheriffCheckAction]
    value = 4

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        return EndPhase()

    def __repr__(self):
        return f"NightSheriffPhase"


class EndPhase(Phase):
    allowed_actions = []
    value = 5

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        game_state.check_end_conditions()
        game_state.turn += 1
        while True:
            game_state.active_player += 1
            if game_state.active_player > 9:
                game_state.active_player = 0
            if game_state.game_states[game_state.active_player].alive:
                break
        return DayPhase()

    def __repr__(self):
        return f"EndPhase"


@dataclass
class CompleteGameState(SerializeMixin, DeserializeMixin):
    game_states: List[GameState] = field(
        default_factory=lambda: [
            GameState(
                private_data=PrivateData(role=Role.UNKNOWN), public_data=PublicData()
            )
            for _ in range(MAX_PLAYERS)
        ]
    )

    current_phase: Phase = field(default_factory=DayPhase)
    active_player: int = 0
    turn: int = field(default=0)
    team_won: Team = field(default=Team.UNKNOWN)
    nominated_players: list = field(default_factory=list)

    def serialize(self):
        # Serialize each GameState object and concatenate them
        game_states = [game_state.serialize() for game_state in self.game_states]

        serialized_state = np.concatenate(
            [
                np.concatenate(game_states),
                np.array([self.active_player]),
                np.array([self.current_phase.value]),
                np.array([self.turn]),
                np.array([self.team_won.value]),
            ]
        )
        return serialized_state

    def update_turn(self):
        # Update the turn, ensuring it doesn't exceed the maximum number of turns
        if self.turn < MAX_TURNS - 1:
            self.turn += 1
        else:
            raise ValueError("Maximum number of turns reached")

    @staticmethod
    def deserialize(serialized_state: np.ndarray):
        # Deserialize the complete game state into individual GameState objects
        # CompleteGameState is [GameState * MAX_PLAYERS, game_phase, active_player]
        if serialized_state.size != ARRAY_SIZE * MAX_PLAYERS + 4:
            raise ValueError(
                f"Serialized state must have a size of {ARRAY_SIZE * MAX_PLAYERS + 4}"
            )

        game_states = []
        for i in range(MAX_PLAYERS):
            start_idx = i * ARRAY_SIZE
            end_idx = (i + 1) * ARRAY_SIZE
            game_state = GameState.deserialize(serialized_state[start_idx:end_idx])
            game_states.append(game_state)

        active_player = int(serialized_state[-4])
        game_phase = Phase.from_value(serialized_state[-3])
        turn = int(serialized_state[-2])
        team_won = Team(serialized_state[-1])

        return CompleteGameState(
            game_states=game_states,
            current_phase=game_phase,
            active_player=active_player,
            team_won=team_won,
            turn=turn,
        )

    def deserialize_from(self, player_index: int):
        # Deserialize the complete game state from a specific player's perspective
        if player_index < 0 or player_index >= MAX_PLAYERS:
            raise ValueError(f"Player index must be between 0 and {MAX_PLAYERS - 1}")

        complete_state = self.deserialize(self.serialize())
        for i, game_state in enumerate(complete_state.game_states):
            if i != player_index:
                # Replace the private data for all other players with minimal information
                game_state.private_data = PrivateData(role=Role.UNKNOWN)
        return complete_state

    @staticmethod
    def next_state(game_state: "CompleteGameState", action_vector: "ActionVector"):
        new_game_state: CompleteGameState
        """We combine game_state and action_vector to get new game state"""
        return new_game_state

    def index_of_night_killer(self):
        """
        Determines index of killer
        """
        killer = -1
        for i, state in enumerate(self.game_states):
            if state.private_data.role == Role.MAFIA and state.alive and killer == -1:
                killer = i
            if state.private_data.role == Role.DON and state.alive:
                killer = i
        return killer


    def get_available_action_classes(self):
        # Get the GameState for the active player
        active_player_state = self.game_states[self.active_player]
        active_player_role = active_player_state.private_data.role
        available_action_classes = []

        if isinstance(self.current_phase, DayPhase):
            # During the day, all players can make declarations and nominations
            available_action_classes.append(BeliefAction)
            available_action_classes.append(NominationAction)
            available_action_classes.append(SheriffDeclarationAction)
            available_action_classes.append(PublicSheriffDeclarationAction)

        elif isinstance(self.current_phase, VotingPhase):
            # During the voting phase, players vote for nominated players
            available_action_classes.append(VoteAction)

        elif isinstance(self.current_phase, NightKillPhase):
            if self.index_of_night_killer() == self.active_player:
                # Mafia and Don decide who to kill
                available_action_classes.append(KillAction)

        elif isinstance(self.current_phase, NightDonPhase):
            if active_player_role == Role.DON:
                # Don checks if a player is the Sheriff
                available_action_classes.append(DonCheckAction)

        elif isinstance(self.current_phase, NightSheriffPhase):
            if active_player_role == Role.SHERIFF:
                # Sheriff checks a player's allegiance
                available_action_classes.append(SheriffCheckAction)

        return available_action_classes

    def execute_action(self, action):
        self.current_phase.execute_action(self, action)

    def transition_to_next_phase(self):
        self.current_phase = self.current_phase.next_phase(self)

    def resolve_votes(self):
        # Count the votes for each player
        vote_counts = np.zeros(MAX_PLAYERS, dtype=int)
        for player_state in self.game_states:
            if player_state.alive:  # Only alive players can vote
                votes = player_state.public_data.votes.checks[self.turn]
                for target_player, vote in enumerate(votes):
                    if vote:
                        vote_counts[target_player] += 1

        # Determine if a player has been voted out
        max_votes = np.max(vote_counts)
        players_with_max_votes = np.where(vote_counts == max_votes)[0]

        if len(players_with_max_votes) == 1:
            # If there is a clear player with the most votes, eliminate that player
            eliminated_player = players_with_max_votes[0]
            self.game_states[eliminated_player].alive = 0
            logger.info(f'Eliminated player {eliminated_player}')
        else:
            logger.info(f"There's tie, no one is eliminated.")
        # If there is a tie or no one received votes, no one is eliminated

        # Clear the votes for the next round
        for player_state in self.game_states:
            player_state.public_data.votes.checks[self.turn].checks.fill(0)

    def check_end_conditions(self):
        # Count the number of alive players for each team
        red_team_count = 0
        black_team_count = 0
        for state in self.game_states:
            if state.alive:
                if state.private_data.role in [Role.CITIZEN, Role.SHERIFF]:
                    red_team_count += 1
                elif state.private_data.role in [Role.MAFIA, Role.DON]:
                    black_team_count += 1

        # Check winning conditions
        if black_team_count >= red_team_count:
            self.team_won = Team.BLACK_TEAM
        elif black_team_count == 0:
            self.team_won = Team.RED_TEAM
        else:
            self.team_won = Team.UNKNOWN  # Game continues

        # If the game has ended, transition to the EndPhase
        if self.team_won != Team.UNKNOWN:
            self.current_phase = EndPhase()

def create_game_state_with_role(role: Role, alive: bool = True):
    return GameState(
        private_data=PrivateData(role=role), public_data=PublicData(), alive=alive
        )