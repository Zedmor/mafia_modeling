import random
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import List, Type, Union, Optional
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
    SayAction,
)
from mafia_game.agent import Agent, HumanAgent, LLMAgent, TestAgent
from mafia_game.common import (
    ARRAY_SIZE,
    Beliefs,
    Booleans,
    Checks,
    DeserializeMixin,
    Kills,
    MAX_PLAYERS,
    MAX_TURNS,
    Nominations,
    Role,
    SerializeMixin,
    T,
    Team,
    Votes,
)
from mafia_game.logger import logger, LogMessage, LogType


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
    log: List[LogMessage] = field(default_factory=list)

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
    agent: Agent = field(default=None)
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
        SayAction,
        NullAction,
    ]

    def next_phase(self, game_state: "CompleteGameState"):
        # Transition to the voting phase after all players have taken their actions
        game_state.log(
            f"Переход из Дневной Фазы в Фазу Голосования", log_type=LogType.PHASE_CHANGE
        )
        return VotingPhase()

    def __repr__(self):
        return f"DayPhase"


class VotingPhase(Phase):
    allowed_actions = [VoteAction, EliminateAllNominatedVoteAction]  # No NullAction - players must vote
    value = 1

    def execute_action(self, game_state: "CompleteGameState", action):
        # Allow NullAction for dead players giving speeches, even during voting phase
        if isinstance(action, NullAction):
            player_is_dead = not game_state.game_states[action.player_index].alive
            if player_is_dead:
                # Dead players can always end their speech with NullAction
                action.apply(game_state)
                return
            else:
                # Alive players cannot abstain during voting - they must vote
                raise ValueError(
                    f"Action {action.__class__} is not allowed during {self.__class__} phase"
                )
        
        # Use parent method for all other actions
        super().execute_action(game_state, action)

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        if game_state.voting_round == 0:
            # First voting round
            if game_state.nominated_players:
                game_state.resolve_votes()
                if game_state.voting_round == 1:
                    # If there was a tie, stay in VotingPhase for second round
                    game_state.log(
                        f"Ничья в первом раунде голосования. Переход ко второму раунду голосования.",
                        log_type=LogType.VOTE_RESULT,
                    )
                    game_state.reset_active_player_for_new_voting_round()
                    return VotingPhase()
                # Otherwise, clear nominations and move to night phase
                game_state.nominated_players = []
            else:
                game_state.log(
                    "Никто не был номинирован. Пропуск голосования.",
                    log_type=LogType.VOTE_RESULT,
                )
                # Auto-skip to night phase when no nominations
                game_state.log(
                    "Переход из Фазы Голосования в Ночную Фазу Убийства",
                    log_type=LogType.PHASE_CHANGE,
                )
                return NightKillPhase()
        elif game_state.voting_round == 1:
            # Second voting round
            game_state.resolve_votes()
            if game_state.voting_round == 2:
                # If there was a tie again, stay in VotingPhase for third round
                game_state.log(
                    f"Ничья во втором раунде голосования. Переход к третьему раунду (голосование за исключение всех).",
                    log_type=LogType.VOTE_RESULT,
                )
                game_state.reset_active_player_for_new_voting_round()
                return VotingPhase()
            # Otherwise, clear tied players and move to night phase
            game_state.tied_players = []
        elif game_state.voting_round == 2:
            # Third voting round - eliminate all vote
            game_state.resolve_eliminate_all_vote()
            # Clear tied players and move to night phase
            game_state.tied_players = []

        game_state.log(
            "Переход из Фазы Голосования в Ночную Фазу Убийства",
            log_type=LogType.PHASE_CHANGE,
        )
        return NightKillPhase()

    def __repr__(self):
        return f"VotingPhase"


class NightKillPhase(Phase):
    allowed_actions = [KillAction, NullAction]
    value = 2

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        game_state.log(
            "Переход из Ночной Фазы Убийства в Ночную Фазу Дона",
            log_type=LogType.PHASE_CHANGE,
        )
        return NightDonPhase()

    def __repr__(self):
        return f"NightKillPhase"


class NightDonPhase(Phase):
    allowed_actions = [DonCheckAction, NullAction]
    value = 3

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        game_state.log(
            "Переход из Ночной Фазы Дона в Ночную Фазу Шерифа",
            log_type=LogType.PHASE_CHANGE,
        )
        return NightSheriffPhase()

    def __repr__(self):
        return f"NightDonPhase"


class NightSheriffPhase(Phase):
    allowed_actions = [SheriffCheckAction, NullAction]
    value = 4

    def next_phase(self, game_state: "CompleteGameState"):
        # Resolve votes and transition to the night kill phase
        game_state.log(
            "Переход из Ночной Фазы Шерифа в Завершающую Фазу",
            log_type=LogType.PHASE_CHANGE,
        )
        return EndPhase()

    def __repr__(self):
        return f"NightSheriffPhase"


class EndPhase(Phase):
    allowed_actions = []  # No actions allowed in EndPhase
    value = 5

    def next_phase(self, game_state: "CompleteGameState"):
        # EndPhase processing is now handled by _process_end_phase() in transition_to_next_phase()
        # This method just returns the next phase without doing any processing
        return DayPhase()

    def __repr__(self):
        return f"EndPhase"


@dataclass
class CompleteGameState(SerializeMixin, DeserializeMixin):
    game_states: List[GameState] = field(
        default_factory=lambda: [
            GameState(
                private_data=PrivateData(role=Role.UNKNOWN), public_data=PublicData(), agent=LLMAgent(None)
            )
            for _ in range(MAX_PLAYERS)
        ]
    )

    current_phase: Phase = field(default_factory=DayPhase)
    active_player: int = 0
    turn: int = field(default=0)
    team_won: Team = field(default=Team.UNKNOWN)
    nominated_players: list = field(default_factory=list)
    phase_start_player: int = field(
        default=-1
    )  # Track the player who started the current phase
    voting_round: int = field(
        default=0
    )  # Track which voting round we're in (0=first, 1=second, 2=third)
    phase_actions_count: int = field(
        default=0
    )  # Track how many actions have been taken in the current phase
    tied_players: list = field(default_factory=list)  # Track players who tied in voting
    eliminate_all_votes: np.array = field(
        default_factory=lambda: np.zeros(MAX_PLAYERS, dtype=int)
    )  # Track votes for eliminating all tied players
    day_starter_backup: int = field(
        default=-1
    )  # Backup of the intended day starter before switching to dead player for final speech
    game_log: List[LogMessage] = field(default_factory=list)  # Global game log

    def log(
        self,
        message: str,
        log_type: LogType = LogType.OTHER,
        player_index: Optional[int] = None,
        target_player: Optional[int] = None,
    ):
        """
        Add a log message to the game log and optionally to a specific player's log.

        Args:
            message: The log message
            log_type: Type of log message
            player_index: The player who performed the action (optional)
            target_player: The player who was the target of the action (optional)
        """
        # Create the log message
        log_msg = LogMessage(
            message=message,
            log_type=log_type,
            turn=self.turn,
            player_index=player_index,
            target_player_index=target_player,
        )

        # Add to global game log
        self.game_log.append(log_msg)

        # If target_player is specified, only add to that player's log
        if player_index is not None:
            self.game_states[player_index].private_data.log.append(log_msg)
            if isinstance(self.game_states[player_index].agent, HumanAgent):
                logger.info(str(log_msg))

        else:
            logger.info(str(log_msg))
            # Otherwise add to all players' logs
            for player_state in self.game_states:
                player_state.private_data.log.append(log_msg)


    @property
    def current_player(self) -> GameState:
        return self.game_states[self.active_player]

    @staticmethod
    def build(human_player: Role = None, use_test_agents: bool = False):
        game_states = [
            create_game_state_with_role(r)
            for r in [Role.CITIZEN] * 6 + [Role.SHERIFF] + [Role.MAFIA] * 2 + [Role.DON]
        ]
        random.shuffle(game_states)

        mafia_player_indexes = [
            i
            for i in range(10)
            if game_states[i].private_data.role in (Role.MAFIA, Role.DON)
        ]

        for mafia_player in mafia_player_indexes:
            game_states[mafia_player].private_data.other_mafias.other_mafias = np.array(
                mafia_player_indexes
            )

        game_state = CompleteGameState(
            game_states=game_states,
            current_phase=DayPhase(),
            active_player=0,
            phase_start_player=-1,
            turn=0,
            team_won=Team.UNKNOWN,
        )

        need_to_deploy_human = True

        # Modify to allow human players
        for n, player in enumerate(game_states):
            if player.private_data.role == human_player and need_to_deploy_human:
            # if need_to_deploy_human:
                logger.info(f"Human player: {n}")
                player.agent = HumanAgent(game_state)
                need_to_deploy_human = False
            else:
                if use_test_agents:
                    player.agent = TestAgent(game_state)
                else:
                    player.agent = LLMAgent(game_state)

        game_state.log("Игра инициализирована", log_type=LogType.GAME_STATE)
        game_state.log(
            f"Начало хода {game_state.turn}. Первый игрок: {game_state.active_player}",
            log_type=LogType.GAME_STATE,
        )

        return game_state

    def reset_active_player_for_new_voting_round(self):
        """Reset the active player to the first alive player for a new voting round"""
        # Find the first alive player
        for i in range(MAX_PLAYERS):
            if self.game_states[i].alive:
                self.active_player = i
                self.phase_start_player = i
                break

        # Reset the phase action count for the new voting round
        self.phase_actions_count = 0

        self.log(
            f"Сброс активного игрока на {self.active_player} для нового раунда голосования",
            log_type=LogType.GAME_STATE,
        )

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

        # Serialize nominated_players list (pad to MAX_PLAYERS length)
        nominated_array = np.full(MAX_PLAYERS, -1, dtype=int)
        for i, player_id in enumerate(self.nominated_players[:MAX_PLAYERS]):
            nominated_array[i] = player_id

        # Serialize tied_players list (pad to MAX_PLAYERS length) 
        tied_array = np.full(MAX_PLAYERS, -1, dtype=int)
        for i, player_id in enumerate(self.tied_players[:MAX_PLAYERS]):
            tied_array[i] = player_id

        serialized_state = np.concatenate(
            [
                np.concatenate(game_states),
                np.array([self.active_player]),
                np.array([self.current_phase.value]),
                np.array([self.turn]),
                np.array([self.team_won.value]),
                np.array([self.phase_start_player]),
                np.array([self.voting_round]),
                np.array([self.phase_actions_count]),
                np.array([self.day_starter_backup]),
                nominated_array,
                tied_array,
                self.eliminate_all_votes,
            ]
        )
        return serialized_state

    def update_turn(self):
        # Update the turn, ensuring it doesn't exceed the maximum number of turns
        if self.turn < MAX_TURNS - 1:
            self.turn += 1
            self.log(f"Ход обновлен до {self.turn}", log_type=LogType.GAME_STATE)
        else:
            self.log(
                "Достигнуто максимальное количество ходов", log_type=LogType.GAME_STATE
            )
            raise ValueError("Maximum number of turns reached")

    @staticmethod
    def deserialize(serialized_state: np.ndarray):
        # Deserialize the complete game state into individual GameState objects
        # CompleteGameState is [GameState * MAX_PLAYERS, active_player, game_phase, turn, team_won, phase_start_player, voting_round, phase_actions_count, day_starter_backup, nominated_array, tied_array, eliminate_all_votes]
        expected_size = ARRAY_SIZE * MAX_PLAYERS + 8 + (3 * MAX_PLAYERS)  # 8 single values + 3 arrays of MAX_PLAYERS each
        if serialized_state.size != expected_size:
            raise ValueError(
                f"Serialized state must have a size of {expected_size}, got {serialized_state.size}"
            )

        # Deserialize game states
        game_states = []
        for i in range(MAX_PLAYERS):
            start_idx = i * ARRAY_SIZE
            end_idx = (i + 1) * ARRAY_SIZE
            game_state = GameState.deserialize(serialized_state[start_idx:end_idx])
            game_states.append(game_state)

        # Calculate indices for the additional fields
        base_idx = ARRAY_SIZE * MAX_PLAYERS
        active_player = int(serialized_state[base_idx])
        game_phase = Phase.from_value(serialized_state[base_idx + 1])
        turn = int(serialized_state[base_idx + 2])
        team_won = Team(serialized_state[base_idx + 3])
        phase_start_player = int(serialized_state[base_idx + 4])
        voting_round = int(serialized_state[base_idx + 5])
        phase_actions_count = int(serialized_state[base_idx + 6])
        day_starter_backup = int(serialized_state[base_idx + 7])
        
        # Deserialize nominated_players (next MAX_PLAYERS elements)
        nominated_start = base_idx + 8
        nominated_end = nominated_start + MAX_PLAYERS
        nominated_array = serialized_state[nominated_start:nominated_end]
        nominated_players = [int(p) for p in nominated_array if p != -1]
        
        # Deserialize tied_players (next MAX_PLAYERS elements)
        tied_start = nominated_end
        tied_end = tied_start + MAX_PLAYERS
        tied_array = serialized_state[tied_start:tied_end]
        tied_players = [int(p) for p in tied_array if p != -1]
        
        # Deserialize eliminate_all_votes (next MAX_PLAYERS elements)
        votes_start = tied_end
        votes_end = votes_start + MAX_PLAYERS
        eliminate_all_votes = serialized_state[votes_start:votes_end].astype(int)

        return CompleteGameState(
            game_states=game_states,
            current_phase=game_phase,
            active_player=active_player,
            team_won=team_won,
            turn=turn,
            phase_start_player=phase_start_player,
            voting_round=voting_round,
            phase_actions_count=phase_actions_count,
            day_starter_backup=day_starter_backup,
            nominated_players=nominated_players,
            tied_players=tied_players,
            eliminate_all_votes=eliminate_all_votes,
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
    def next_state(
        game_state: "CompleteGameState", action_vector: Union["Action", None]
    ):
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
        
        # Debug: log the killer finding process
        if killer == -1:
            alive_roles = [(i, state.private_data.role, state.alive) for i, state in enumerate(self.game_states) if state.alive]
            self.log(f"DEBUG: No killer found. Alive players: {alive_roles}", log_type=LogType.GAME_STATE)
        else:
            self.log(f"DEBUG: Killer found: Player {killer} (Role: {self.game_states[killer].private_data.role})", log_type=LogType.GAME_STATE)
        
        return killer

    def get_available_action_classes(self):
        # Get the GameState for the active player
        active_player_state = self.game_states[self.active_player]
        active_player_role = active_player_state.private_data.role
        available_action_classes = []

        if isinstance(self.current_phase, DayPhase):
            # During the day, all players can make declarations and nominations
            available_action_classes.append(NominationAction)
            available_action_classes.append(SheriffDeclarationAction)
            available_action_classes.append(PublicSheriffDeclarationAction)
            available_action_classes.append(SayAction)

        elif isinstance(self.current_phase, VotingPhase):
            # During the voting phase, players vote for nominated players
            if self.voting_round == 2:
                # In the third voting round, players vote to eliminate all tied players or not
                available_action_classes.append(EliminateAllNominatedVoteAction)
            else:
                # In the first and second voting rounds, players vote for specific players
                available_action_classes.append(VoteAction)

        elif isinstance(self.current_phase, NightKillPhase):
            if self.index_of_night_killer() == self.active_player and self.current_player.alive:
                # Mafia and Don decide who to kill
                available_action_classes.append(KillAction)

        elif isinstance(self.current_phase, NightDonPhase):
            if active_player_role == Role.DON  and active_player_state.alive:
                # Don checks if a player is the Sheriff
                available_action_classes.append(DonCheckAction)

        elif isinstance(self.current_phase, NightSheriffPhase):
            if active_player_role == Role.SHERIFF and active_player_state.alive:
                # Sheriff checks a player's allegiance
                available_action_classes.append(SheriffCheckAction)

        return available_action_classes

    def get_mafia_player_indexes(self):
        # Returns a list of indexes for players who are Mafia or Don
        mafia_player_indexes = [
            i
            for i, state in enumerate(self.game_states)
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
                    action = action_class.from_index(
                        action_index, self, self.active_player
                    )
                    actions.append(action)

        # During voting phase, players cannot abstain - they must vote
        if self.current_phase.value == VotingPhase.value:
            return actions

        # During EndPhase, no actions are allowed - return empty list
        if isinstance(self.current_phase, EndPhase):
            return actions  # Empty list

        # For all other phases, allow NullAction (abstaining)
        actions.append(NullAction(self.active_player))
        return actions

    def execute_action(self, action):
        # Store the player who started this phase if this is the first action in the phase
        if self.phase_start_player == -1:
            self.phase_start_player = self.active_player

        # Execute the action
        self.current_phase.execute_action(self, action)

        # Log the action
        if not isinstance(action, NullAction):
            player_index = action.player_index
            target_player = getattr(action, "target_player", None)
            # self.log(str(action), log_type=LogType.ACTION, player_index=player_index, target_player=target_player)

        # Increment the phase action count
        self.phase_actions_count += 1

        # Handle phase transitions based on phase type
        if isinstance(self.current_phase, VotingPhase):
            # Move to next alive player for voting
            original_player = self.active_player
            while True:
                self.active_player = (self.active_player + 1) % MAX_PLAYERS
                if self.game_states[self.active_player].alive:
                    break
                if self.active_player == original_player:
                    break  # No alive players (shouldn't happen)
            
            # Check if all alive players have voted
            alive_players_count = sum(1 for state in self.game_states if state.alive)
            if self.phase_actions_count >= alive_players_count:
                self.resolve_voting_and_transition()
                return
                
        elif isinstance(self.current_phase, DayPhase):
            # Check if this is a final speech situation (dead player taking any action)
            if not self.game_states[self.active_player].alive:
                # This is a dead player acting - restore the intended day starter from backup after any action
                # Restore the intended day starter from backup
                if self.day_starter_backup != -1:
                    self.active_player = self.day_starter_backup
                    self.phase_start_player = self.day_starter_backup
                    self.phase_actions_count = 0
                    self.day_starter_backup = -1  # Clear the backup
                    
                    self.log(
                        f"После действия убитого игрока, переход к нормальной дневной фазе. Активный игрок: {self.active_player}",
                        log_type=LogType.GAME_STATE,
                    )
                else:
                    # Fallback if no backup - transition to next phase
                    self.transition_to_next_phase()
                return
                
            # Normal day phase - move to next alive player
            original_player = self.active_player
            while True:
                self.active_player = (self.active_player + 1) % MAX_PLAYERS
                if self.game_states[self.active_player].alive:
                    break
                if self.active_player == original_player:
                    break  # No alive players (shouldn't happen)
            
            # Check if we've completed a full cycle through all alive players
            if self.active_player == self.phase_start_player:
                self.transition_to_next_phase()
        
        elif isinstance(self.current_phase, (NightKillPhase, NightDonPhase, NightSheriffPhase)):
            # Night phases are role-specific, not round-robin
            # Transition immediately after the role-holder acts (or skips)
            phase_name = self.current_phase.__class__.__name__
            self.log(f"DEBUG: Night phase action completed in {phase_name}, transitioning to next phase", log_type=LogType.GAME_STATE)
            self.transition_to_next_phase()
            
        elif isinstance(self.current_phase, EndPhase):
            # EndPhase should complete automatically
            self.transition_to_next_phase()

    def resolve_voting_and_transition(self):
        """Resolve votes and transition to the next phase for voting phases"""
        # This method is called when all players have voted in a voting phase
        # Let the VotingPhase.next_phase() handle the vote resolution
        self.transition_to_next_phase()

    def transition_to_next_phase(self):
        old_phase = self.current_phase
        new_phase = self.current_phase.next_phase(self)
        
        # Check if we're staying in the same phase type (e.g., VotingPhase -> VotingPhase for tie-breaking)
        staying_in_same_phase_type = type(old_phase) == type(new_phase)
        
        self.current_phase = new_phase
        
        # Auto-skip VotingPhase if there are no nominations
        if isinstance(new_phase, VotingPhase) and not self.nominated_players:
            self.log(
                "Никто не был номинирован. Автоматический пропуск фазы голосования.",
                log_type=LogType.VOTE_RESULT,
            )
            self.log(
                "Переход из Фазы Голосования в Ночную Фазу Убийства",
                log_type=LogType.PHASE_CHANGE,
            )
            self.current_phase = NightKillPhase()
            new_phase = self.current_phase
        
        # Set active player for night phases when transitioning INTO them
        if isinstance(new_phase, NightKillPhase):
            # Set active player to killer for kill phase
            killer_index = self.index_of_night_killer()
            self.log(f"DEBUG: Transitioning to NightKillPhase, killer_index={killer_index}", log_type=LogType.GAME_STATE)
            if killer_index != -1:
                self.active_player = killer_index
                self.log(f"DEBUG: Set active player to {killer_index} for NightKillPhase", log_type=LogType.GAME_STATE)
            else:
                # No mafia alive, skip this phase automatically
                self.log(f"DEBUG: No killer found, skipping NightKillPhase", log_type=LogType.GAME_STATE)
                self.transition_to_next_phase()
                return
                
        elif isinstance(new_phase, NightDonPhase):
            # Set active player to Don for don check phase
            don_index = -1
            for i, state in enumerate(self.game_states):
                if state.private_data.role == Role.DON and state.alive:
                    don_index = i
                    break
            if don_index != -1:
                self.active_player = don_index
            else:
                # No Don alive, skip this phase automatically
                self.transition_to_next_phase()
                return
                
        elif isinstance(new_phase, NightSheriffPhase):
            # Set active player to Sheriff for sheriff check phase
            sheriff_index = -1
            for i, state in enumerate(self.game_states):
                if state.private_data.role == Role.SHERIFF and state.alive:
                    sheriff_index = i
                    break
            if sheriff_index != -1:
                self.active_player = sheriff_index
            else:
                # No Sheriff alive, skip this phase automatically
                self.transition_to_next_phase()
                return
        
        # Only reset phase tracking when transitioning to a different phase type
        # If we're staying in the same phase (e.g., tie-breaking voting), preserve the tracking set by reset methods
        if not staying_in_same_phase_type:
            self.phase_start_player = -1
            self.phase_actions_count = 0
            
        # Handle EndPhase immediate transition - EndPhase should not wait for actions
        if isinstance(new_phase, EndPhase):
            # Process end phase immediately (kill players, check win conditions, advance turn)
            self._process_end_phase()
            # Then transition to next phase (DayPhase for next turn)
            self.transition_to_next_phase()
    
    def _process_end_phase(self):
        """Process the end phase logic: kill players, check win conditions, advance turn"""
        # Check if any players died during the night and will need death speeches
        killed_players = []
        for n, player in enumerate(self.game_states):
            if player.alive == -1:
                killed_players.append(n)
        
        # Kill players who were marked for death during the night
        for n, player in enumerate(self.game_states):
            if player.alive == -1:
                player.alive = 0  # Player killed during the night dead for good
                self.log(
                    f"Игрок {n} был убит ночью", log_type=LogType.ELIMINATION
                )
                # Only call utterance if agent exists (avoid None agent error)
                if self.game_states[n].agent is not None:
                    self.game_states[n].agent.utterance(n)

        # Check win conditions
        self.check_end_conditions()
        
        # If game hasn't ended, advance to next turn
        if self.team_won == Team.UNKNOWN:
            # Store the current turn's starting player
            current_turn_start_player = 0 if self.turn == 0 else (self.turn % MAX_PLAYERS)
            
            self.turn += 1
            
            # Find next alive player to start the new day based on turn rotation
            # Next turn should start with (current_turn_start_player + 1) % MAX_PLAYERS
            next_start_player = (current_turn_start_player + 1) % MAX_PLAYERS
            
            # Find the next alive player starting from the calculated position
            attempts = 0
            while attempts < MAX_PLAYERS:
                if self.game_states[next_start_player].alive:
                    intended_day_starter = next_start_player
                    break
                next_start_player = (next_start_player + 1) % MAX_PLAYERS
                attempts += 1
            
            # Fallback: if no player found (shouldn't happen), find first alive player
            if attempts >= MAX_PLAYERS:
                for i in range(MAX_PLAYERS):
                    if self.game_states[i].alive:
                        intended_day_starter = i
                        break
            
            # Save the intended day starter before any potential death speeches
            self.day_starter_backup = intended_day_starter
            
            # If there are killed players, first dead player becomes active for death speech
            # Otherwise, intended day starter becomes active immediately
            if killed_players:
                self.active_player = killed_players[0]  # First killed player gives death speech
                self.log(
                    f"Игрок {killed_players[0]} был убит и получает последнее слово",
                    log_type=LogType.GAME_STATE,
                )
            else:
                self.active_player = intended_day_starter

            alive_players = [
                i for i, game_state in enumerate(self.game_states) if game_state.alive
            ]
            self.log(
                f"Конец хода {self.turn-1}. Живые игроки: {alive_players}",
                log_type=LogType.GAME_STATE,
            )
            self.log(
                f"Начало хода {self.turn}. Первый игрок для дня: {intended_day_starter}, активный игрок: {self.active_player}",
                log_type=LogType.GAME_STATE,
            )

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

            self.log(
                f"Результаты голосования в раунде {self.voting_round} для разрешения ничьей: {vote_counts}",
                log_type=LogType.VOTE_RESULT,
            )
        else:
            # Regular voting round - count all votes
            for player_state in self.game_states:
                if player_state.alive:  # Only alive players can vote
                    votes = player_state.public_data.votes.checks[self.turn]
                    for target_player, vote in enumerate(votes):
                        if vote:
                            vote_counts[target_player] += 1

            self.log(
                f"Результаты первого раунда голосования: {vote_counts}",
                log_type=LogType.VOTE_RESULT,
            )

        # Determine if a player has been voted out
        if np.sum(vote_counts) == 0:
            self.log(
                "Голосов не подано, никто не исключен.", log_type=LogType.VOTE_RESULT
            )
            self.voting_round = 0  # Reset voting round
            self.tied_players = []  # Clear tied players
            return

        max_votes = np.max(vote_counts)
        players_with_max_votes = np.where(vote_counts == max_votes)[0]

        # Filter out players with zero votes
        players_with_max_votes = [
            p for p in players_with_max_votes if vote_counts[p] > 0
        ]

        if not players_with_max_votes:
            self.log(
                "Нет действительных голосов, никто не исключен.",
                log_type=LogType.VOTE_RESULT,
            )
            self.voting_round = 0  # Reset voting round
            self.tied_players = []  # Clear tied players
            return

        if len(players_with_max_votes) == 1:
            # If there is a clear player with the most votes, eliminate that player
            eliminated_player = players_with_max_votes[0]
            self.game_states[eliminated_player].alive = 0
            self.game_states[eliminated_player].agent.utterance(eliminated_player)
            self.log(
                f"Игрок {eliminated_player} был исключен голосованием",
                log_type=LogType.ELIMINATION,
            )

            # Reset voting state
            self.voting_round = 0
            self.tied_players = []
        else:
            # There's a tie
            if self.voting_round == 0:
                # First round tie - move to second round with tied players
                self.log(
                    f"Ничья в первом раунде между игроками {players_with_max_votes}. Переход ко второму раунду.",
                    log_type=LogType.VOTE_RESULT,
                )
                self.tied_players = players_with_max_votes
                self.voting_round = 1
            elif self.voting_round == 1:
                # Second round tie - move to third round
                self.log(
                    f"Ничья во втором раунде между игроками {players_with_max_votes}. Переход к третьему раунду.",
                    log_type=LogType.VOTE_RESULT,
                )
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

        self.log(
            f"Голосование за исключение всех: {yes_votes} голосов 'за' из {alive_players_count} живых игроков",
            log_type=LogType.VOTE_RESULT,
        )

        # If more than half of alive players voted yes, eliminate all tied players
        if yes_votes > alive_players_count / 2:
            self.log(
                f"Большинство проголосовало за исключение всех игроков с ничьей: {self.tied_players}",
                log_type=LogType.VOTE_RESULT,
            )
            for player in self.tied_players:
                self.game_states[player].alive = 0
                self.game_states[player].agent.utterance(player)
                self.log(
                    f"Игрок {player} был исключен голосованием",
                    log_type=LogType.ELIMINATION,
                )
        else:
            self.log(
                "Недостаточно голосов для исключения игроков с ничьей, никто не исключен.",
                log_type=LogType.VOTE_RESULT,
            )

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
            self.log(
                "Черная команда (Мафия) победила в игре!", log_type=LogType.GAME_END
            )
        elif black_team_count == 0:
            self.team_won = Team.RED_TEAM
            self.log(
                "Красная команда (Мирные жители) победила в игре!",
                log_type=LogType.GAME_END,
            )
        else:
            self.team_won = Team.UNKNOWN  # Game continues

        # If the game has ended, transition to the EndPhase
        if self.team_won != Team.UNKNOWN:
            self.current_phase = EndPhase()

    def is_terminal(self):
        self.check_end_conditions()
        if self.turn >= 10 and self.team_won == Team.UNKNOWN:
            self.log(
                "Игра достигла максимального количества ходов (10). Игра окончена.",
                log_type=LogType.GAME_END,
            )
        return self.team_won != Team.UNKNOWN or self.turn >= 10

    def final_speech(self):
        """Implement final speech of a player that goes to the public log"""
        pass

    def _set_night_phase_active_player(self):
        """Set the active player for the upcoming night phase based on phase type and alive roles"""
        next_phase = self.current_phase.next_phase(self)
        
        if isinstance(next_phase, NightKillPhase):
            # Set active player to mafia/don killer
            killer_index = self.index_of_night_killer()
            if killer_index != -1:
                self.active_player = killer_index
            else:
                # No mafia alive, skip to next phase
                self.active_player = 0  # Default fallback
                
        elif isinstance(next_phase, NightDonPhase):
            # Set active player to Don (if alive)
            don_index = -1
            for i, state in enumerate(self.game_states):
                if state.private_data.role == Role.DON and state.alive:
                    don_index = i
                    break
            if don_index != -1:
                self.active_player = don_index
            else:
                # No Don alive, will skip this phase automatically
                self.active_player = 0  # Default fallback
                
        elif isinstance(next_phase, NightSheriffPhase):
            # Set active player to Sheriff (if alive)
            sheriff_index = -1
            for i, state in enumerate(self.game_states):
                if state.private_data.role == Role.SHERIFF and state.alive:
                    sheriff_index = i
                    break
            if sheriff_index != -1:
                self.active_player = sheriff_index
            else:
                # No Sheriff alive, will skip this phase automatically
                self.active_player = 0  # Default fallback
                
        elif isinstance(next_phase, EndPhase):
            # Find first alive player for end phase
            for i in range(MAX_PLAYERS):
                if self.game_states[i].alive:
                    self.active_player = i
                    break


def create_game_state_with_role(role: Role, alive: bool = True):
    return GameState(
        private_data=PrivateData(role=role), public_data=PublicData(), alive=alive, agent=None
    )
