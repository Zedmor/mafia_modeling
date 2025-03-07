import random
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, Type, Union
from mafia_game.actions import Action, NullAction, EliminateAllNominatedVoteAction

import numpy as np

from mafia_game.actions import (
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

    def clone(self):
        import copy
        return copy.deepcopy(self)

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
        NominationAction,
        SheriffDeclarationAction,
        PublicSheriffDeclarationAction,
        NullAction
    ]


    def next_phase(self, game_state: "CompleteGameState"):
        # Transition to the voting phase after all players have taken their actions
        return VotingPhase()

    def __repr__(self):
        return f"DayPhase"


class VotingPhase(Phase):
    allowed_actions = [VoteAction, EliminateAllNominatedVoteAction, NullAction]
    value = 1

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        if game_state.voting_round == 0:
            # First voting round
            if game_state.nominated_players:
                game_state.resolve_votes()
                if game_state.voting_round == 1:
                    # If there was a tie, stay in VotingPhase for second round
                    game_state.reset_active_player_for_new_voting_round()
                    return VotingPhase()
                # Otherwise, clear nominations and move to night phase
                game_state.nominated_players = []
            else:
                logger.info("Nobody had been nominated. Skipping vote.")
        elif game_state.voting_round == 1:
            # Second voting round
            game_state.resolve_votes()
            if game_state.voting_round == 2:
                # If there was a tie again, stay in VotingPhase for third round
                game_state.reset_active_player_for_new_voting_round()
                return VotingPhase()
            # Otherwise, clear tied players and move to night phase
            game_state.tied_players = []
        elif game_state.voting_round == 2:
            # Third voting round - eliminate all vote
            game_state.resolve_eliminate_all_vote()
            # Clear tied players and move to night phase
            game_state.tied_players = []
            
        return NightKillPhase()

    def __repr__(self):
        return f"VotingPhase"


class NightKillPhase(Phase):
    allowed_actions = [KillAction, NullAction]
    value = 2

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        return NightDonPhase()

    def __repr__(self):
        return f"NightKillPhase"


class NightDonPhase(Phase):
    allowed_actions = [DonCheckAction, NullAction]
    value = 3

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        return NightSheriffPhase()

    def __repr__(self):
        return f"NightDonPhase"

class NightSheriffPhase(Phase):
    allowed_actions = [SheriffCheckAction, NullAction]
    value = 4

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        return EndPhase()

    def __repr__(self):
        return f"NightSheriffPhase"


class EndPhase(Phase):
    allowed_actions = [NullAction]
    value = 5

    def next_phase(self, game_state: "CompleteGameState"):
        for player in game_state.game_states:
            if player.alive == -1:
                player.alive = 0  # Player killed durint the night dead for good
        # Resolve votes and transition to the night kill phase
        game_state.check_end_conditions()
        game_state.turn += 1
        while True:
            game_state.active_player += 1
            if game_state.active_player > 9:
                game_state.active_player = 0
            if game_state.game_states[game_state.active_player].alive:
                break

        logger.info(f"Alive players: {[i for i, game_state in enumerate(game_state.game_states) if game_state.alive]}")

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
    voting_round: int = 0
    active_player: int = 0
    turn: int = field(default=0)
    team_won: Team = field(default=Team.UNKNOWN)
    nominated_players: list = field(default_factory=list)
    phase_start_player: int = field(default=0)  # Track the player who started the current phase
    voting_round: int = field(default=0)  # Track which voting round we're in (0=first, 1=second, 2=third)
    tied_players: list = field(default_factory=list)  # Track players who tied in voting
    eliminate_all_votes: np.array = field(default_factory=lambda: np.zeros(MAX_PLAYERS, dtype=int))  # Track votes for eliminating all tied players

    @staticmethod
    def build():
        game_states = [
            create_game_state_with_role(r) for r in
            [Role.CITIZEN] * 6 + [Role.SHERIFF] + [Role.MAFIA] * 2 + [Role.DON]]
        random.shuffle(game_states)

        mafia_player_indexes = [i for i in range(10) if
                                game_states[i].private_data.role in (Role.MAFIA, Role.DON)]

        for mafia_player in mafia_player_indexes:
            game_states[mafia_player].private_data.other_mafias.other_mafias = np.array(
                mafia_player_indexes)

        return CompleteGameState(
            game_states=game_states,
            current_phase=DayPhase(),
            active_player=0,
            phase_start_player=0,
            turn=0,
            team_won=Team.UNKNOWN,
            )

    def reset_active_player_for_new_voting_round(self):
        """Reset the active player to the first alive player for a new voting round"""
        # Find the first alive player
        for i in range(MAX_PLAYERS):
            if self.game_states[i].alive:
                self.active_player = i
                self.phase_start_player = i
                break

    def clone(self):
        return self.deserialize(self.serialize())

    def get_reward(self, player_index):
        player_team = self.game_states[player_index].private_data.team
        if self.turn >= 10:
            # Penalize paths that reach turn 10
            return -1.0
        if self.team_won == player_team:
            return 1.0  # Win
        elif self.team_won == Team.UNKNOWN:
            return 0.0  # Game not finished
        else:
            return -1.0  # Loss


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
            phase_start_player=active_player,  # Initialize phase_start_player to active_player
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
    def next_state(game_state: "CompleteGameState", action_vector: Union["Action", None]):
        new_game_state = game_state.clone()
        if action_vector:
            new_game_state.current_phase.execute_action(new_game_state, action_vector)
            new_game_state.transition_to_next_phase()
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

        if isinstance(self.current_phase, DayPhase) and self.turn != 0:
            # During the day, all players can make declarations and nominations
            available_action_classes.append(NominationAction)
            # available_action_classes.append(SheriffDeclarationAction)
            # available_action_classes.append(PublicSheriffDeclarationAction)

        elif isinstance(self.current_phase, VotingPhase):
            # During the voting phase, players vote for nominated players
            if self.voting_round == 2:
                # In the third voting round, players vote to eliminate all tied players or not
                available_action_classes.append(EliminateAllNominatedVoteAction)
            else:
                # In the first and second voting rounds, players vote for specific players
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

    def get_mafia_player_indexes(self):
        # Returns a list of indexes for players who are Mafia or Don
        mafia_player_indexes = [
            i for i, state in enumerate(self.game_states)
            if state.private_data.role in [Role.MAFIA, Role.DON] and state.alive
        ]
        return mafia_player_indexes

    def get_available_actions(self):
        action_classes = self.get_available_action_classes()
        actions = []
        for action_class in action_classes:
            mask = action_class.generate_action_mask(self, self.active_player)
            for action_index, is_available in enumerate(mask):
                if is_available:
                    action = action_class.from_index(action_index, self, self.active_player)
                    actions.append(action)

        if self.current_phase.value == VotingPhase.value and (
            (self.voting_round == 0 and self.nominated_players) or 
            (self.voting_round == 1 and self.tied_players) or
            self.voting_round == 2
        ):
            return actions

        actions.append(NullAction(self.active_player))
        return actions


    def execute_action(self, action):
        # Store the player who started this phase if this is the first action in the phase
        if self.phase_start_player == -1:
            self.phase_start_player = self.active_player
            
        # Execute the action
        self.current_phase.execute_action(self, action)
        
        # Move to the next alive player
        original_player = self.active_player
        while True:
            self.active_player = (self.active_player + 1) % MAX_PLAYERS
            # If we've gone through all players and returned to the starting player
            if self.active_player == self.phase_start_player:
                # Transition to the next phase
                self.transition_to_next_phase()
                # Reset phase_start_player for the new phase
                self.phase_start_player = self.active_player
                break
            # If we found an alive player, stop searching
            if self.game_states[self.active_player].alive:
                break
            # If we've checked all players and none are alive (shouldn't happen in normal gameplay)
            if self.active_player == original_player:
                break

    def transition_to_next_phase(self):
        self.current_phase = self.current_phase.next_phase(self)
        # Reset the phase_start_player for the new phase
        self.phase_start_player = self.active_player

    def resolve_votes(self):
        # Count the votes for each player
        vote_counts = np.zeros(MAX_PLAYERS, dtype=int)
        
        # If we're in a tie-breaking round, only count votes for tied players
        if self.voting_round > 0 and self.tied_players:
            # Only count votes for tied players
            for player_state in self.game_states:
                if player_state.alive:  # Only alive players can vote
                    votes = player_state.public_data.votes.checks[self.turn]
                    for target_player in self.tied_players:
                        if votes[target_player]:
                            vote_counts[target_player] += 1
            
            logger.info(f"Tie-breaking round {self.voting_round} vote counts: {vote_counts}")
        else:
            # Regular voting round - count all votes
            for player_state in self.game_states:
                if player_state.alive:  # Only alive players can vote
                    votes = player_state.public_data.votes.checks[self.turn]
                    for target_player, vote in enumerate(votes):
                        if vote:
                            vote_counts[target_player] += 1
            
            logger.info(f"First round vote counts: {vote_counts}")

        # Determine if a player has been voted out
        if np.sum(vote_counts) == 0:
            logger.info("No votes cast, no one is eliminated.")
            self.voting_round = 0  # Reset voting round
            self.tied_players = []  # Clear tied players
            return
            
        max_votes = np.max(vote_counts)
        players_with_max_votes = np.where(vote_counts == max_votes)[0]

        # Filter out players with zero votes
        players_with_max_votes = [p for p in players_with_max_votes if vote_counts[p] > 0]
        
        if not players_with_max_votes:
            logger.info("No valid votes, no one is eliminated.")
            self.voting_round = 0  # Reset voting round
            self.tie_players = []  # Clear tied players
            return

        if len(players_with_max_votes) == 1:
            # If there is a clear player with the most votes, eliminate that player
            eliminated_player = players_with_max_votes[0]
            self.game_states[eliminated_player].alive = 0
            logger.info(f'Eliminated player {eliminated_player}')
            
            # Reset voting state
            self.voting_round = 0
            self.tied_players = []
        else:
            # There's a tie
            if self.voting_round == 0:
                # First round tie - move to second round with tied players
                logger.info(f"First round tie between players {players_with_max_votes}. Moving to second round.")
                self.tied_players = players_with_max_votes
                self.voting_round = 1
            elif self.voting_round == 1:
                # Second round tie - move to third round
                logger.info(f"Second round tie between players {players_with_max_votes}. Moving to third round.")
                self.tied_players = players_with_max_votes
                self.voting_round = 2
                # Reset eliminate_all_votes for the third round
                self.eliminate_all_votes = np.zeros(MAX_PLAYERS, dtype=int)

        # Clear the votes for the next round
        for player_state in self.game_states:
            player_state.public_data.votes.checks[self.turn].checks.fill(0)

    def resolve_eliminate_all_vote(self):
        """Resolve the vote to eliminate all tied players in the third voting round"""
        # Count the number of alive players
        alive_players_count = sum(1 for state in self.game_states if state.alive)
        
        # Count yes votes
        yes_votes = np.sum(self.eliminate_all_votes)
        
        logger.info(f"Eliminate all vote: {yes_votes} yes votes out of {alive_players_count} alive players")
        
        # If more than half of alive players voted yes, eliminate all tied players
        if yes_votes > alive_players_count / 2:
            logger.info(f"Majority voted to eliminate all tied players: {self.tied_players}")
            for player in self.tied_players:
                self.game_states[player].alive = 0
        else:
            logger.info("Not enough votes to eliminate tied players, no one is eliminated.")
            
        # Reset voting state
        self.voting_round = 0
        self.tied_players = []
        self.eliminate_all_votes = np.zeros(MAX_PLAYERS, dtype=int)

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

    def is_terminal(self):
        self.check_end_conditions()
        return self.team_won != Team.UNKNOWN or self.turn >= 10


    def final_speech(self):
        """Implement final speech of a player that goes to the public log"""
        pass


def create_game_state_with_role(role: Role, alive: bool = True):
    return GameState(
        private_data=PrivateData(role=role), public_data=PublicData(), alive=alive
        )
