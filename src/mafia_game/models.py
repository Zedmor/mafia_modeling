from enum import Enum

import torch

from mafia_game.logger import logger


class IndexedEnum(Enum):
    def index(self):
        return list(self.__class__.__members__).index(self.name)


class Role(IndexedEnum):
    MAFIA = "Mafia"
    CITIZEN = "Citizen"



class GameActionType(IndexedEnum):
    NOMINATION = "Nomination"
    DECLARATION = "Declaration"
    VOTE = "Vote"
    VOTE_RESULT = "Vote Result"
    KILL = "Kill"
    FINAL_DECLARATION = "Final Declaration"


class Team(IndexedEnum):
    RED = "Red"
    BLACK = "Black"


class GameAction:
    def __init__(self, action_type, player, target=None, belief=None):
        self.action_type = action_type
        self.player = player
        self.target = target
        self.belief = belief

    def __repr__(self):
        return f"Action: [{self.action_type.value}]: {self.player} -> {self.target} ({self.belief})"


class Policy:
    policy_name = "generic"

    @staticmethod
    def empty():
        return Policy(None, None, None, None)

    def __init__(self, declarations_func, vote_func, kill_func, nomination_func):
        self.declarations_func = declarations_func
        self.vote_func = vote_func
        self.kill_func = kill_func
        self.nomination_func = nomination_func

    def __repr__(self):
        return self.policy_name

    def make_declarations(self, game_state, player):
        return self.declarations_func(game_state, player)

    def vote(self, game_state, player):
        return self.vote_func(game_state, player)

    def kill(self, game_state, player):
        return self.kill_func(game_state, player)

    def nominate_player(self, game_state, player):
        return self.nomination_func(game_state, player)


class Player:
    def __init__(self, _id, role, policy):
        self.id = _id
        self.role = role
        self.is_alive = True
        self.policy = policy
        self.reward = 0
        self.cumulative_reward = 0
        self.action_result = None

    def __hash__(self):
        return self.id

    @property
    def team(self):
        if self.role == Role.CITIZEN:
            return Team.RED
        if self.role == Role.MAFIA:
            return Team.BLACK

    def __eq__(self, other):
        return self.id == other.id

    def __repr__(self):
        return f"{self.id} ({self.role.value}) with policy: {self.policy}"

    def action(self, action_type, game_state, agent):
        total_reward = 0
        old_state_vector = game_state.get_state_vector(self, action_type)

        self.action_result = torch.zeros(94)
        result = getattr(self, action_type)(game_state)

        winner = game_state.determine_winner()
        if winner:
            if winner == self.role:
                self.reward = 10
            else:
                self.reward -= 10

        self.cumulative_reward += self.reward

        total_reward = sum(
            [p.cumulative_reward for p in game_state.players if p.team == Team.RED])

        if agent and self.action_result is not None:
            agent.store_experience(
                old_state_vector,
                self.action_result,
                game_state.get_state_vector(self, action_type),
                torch.tensor([self.reward]),
            )
            agent.update_policy(64, action_type, winner, total_reward)
        return result

    def make_declarations(self, game_state):
        declarations = self.policy.make_declarations(game_state, self)
        self.reward = 0
        for target, belief in declarations:
            game_state.game_actions.append(
                GameAction(GameActionType.DECLARATION, self, target, belief)
            )
            if self.team == Team.RED:
                if target.role == belief:
                    self.reward += 1
                else:
                    self.reward -= 1

    def nominate_player(self, game_state):
        nomination = self.policy.nominate_player(game_state, self)
        self.reward = 0

        if (
            nomination
            and nomination.is_alive
            and nomination not in game_state.nominated_players
        ):
            if self.team == Team.RED:
                if nomination.team == Team.BLACK:
                    self.reward += 1
                else:
                    self.reward -= 1

            game_state.game_actions.append(
                GameAction(GameActionType.NOMINATION, self, nomination)
            )
            game_state.nominated_players.append(nomination)

    def vote(self, game_state):
        self.reward = 0
        target = self.policy.vote(game_state, self)

        if target:
            if self.team == Team.RED:
                if target.team == Team.BLACK:
                    self.reward += 3
                else:
                    self.reward -= 3
            game_state.game_actions.append(
                GameAction(GameActionType.VOTE, self, target)
            )
        return target

    def night_action(self, game_state, agent):
        # Add more night action as we will build this
        target = self.policy.kill(game_state, self)
        game_state.game_actions.append(GameAction(GameActionType.KILL, self, target))
        game_state.eliminate(target)
        # target.action("make_declarations", game_state, agent)
        if game_state.determine_winner():
            for player in game_state.players:
                player.action("make_declarations", game_state, agent)


class GameController:
    def __init__(self, game_state, agent=None):
        self.game_state = game_state
        self.agent = agent

    def start_game(self):
        while not self.game_state.check_end_condition():
            self.play_round()
        return self.game_state.determine_winner()

    def play_round(self):
        if self.game_state.day:
            logger.info(f"\nStarting round: {self.game_state.round}")
            players = [p for p in self.game_state.players if p.is_alive]
            logger.info(f"Remaining: {len(players)}")
            logger.info(f"Players: {players}")
            self.day_phase()
        else:
            self.night_phase()
            self.game_state.round += 1
        self.game_state.day = not self.game_state.day

    def day_phase(self):
        self.game_state.nominated_players = []
        self.declaration_phase()
        self.voting_phase()

    def declaration_phase(self):
        # TODO: Add vote nomination
        start_player_index = self.game_state.current_player_index
        while True:
            player = self.game_state.players[self.game_state.current_player_index]
            if player.is_alive:
                player.action("make_declarations", self.game_state, self.agent)
                player.action("nominate_player", self.game_state, self.agent)
            self.game_state.current_player_index = (
                self.game_state.get_next_alive_player_index()
            )
            if self.game_state.current_player_index == start_player_index:
                break

    def voting_phase(self):
        votes = {player: 0 for player in self.game_state.nominated_players}
        logger.info(f"On the vote: {self.game_state.nominated_players}")
        # TODO: Fix voting according to the rules
        for player in self.game_state.players:
            if player.is_alive:
                player_to_vote = player.action("vote", self.game_state, self.agent)
                if player_to_vote:
                    try:
                        votes[player_to_vote] += 1
                    except KeyError:
                        player.reward = -1e9
        # Eliminate the player with the most votes
        if votes:
            player_to_eliminate = max(votes, key=votes.get)
            self.game_state.eliminate(player_to_eliminate)
            self.game_state.game_actions.append(
                GameAction(GameActionType.VOTE_RESULT, None, player_to_eliminate, None)
            )
            player_to_eliminate.make_declarations(self.game_state)

    def night_phase(self):
        for player in self.game_state.players:
            if player.is_alive and player.role == Role.MAFIA:
                player.night_action(self.game_state, self.agent)
                break


class ListWithEcho(list):
    def __init__(self, echo=False):
        super().__init__()
        self.echo = echo

    def append(self, __object) -> None:
        super().append(__object)
        if self.echo:
            logger.info(__object)


class GameState:
    def __init__(self, players, echo=True):
        self.players = players
        self.day = True
        self.round = 1
        self.game_actions = ListWithEcho(echo)
        self.current_player_index = 0
        self.nominated_players = []

    def get_next_alive_player_index(self):
        next_index = (self.current_player_index + 1) % len(self.players)
        while not self.players[next_index].is_alive:
            next_index = (next_index + 1) % len(self.players)
        return next_index

    def eliminate(self, player):
        player.is_alive = False
        if player == self.players[self.current_player_index]:
            self.current_player_index = self.get_next_alive_player_index()

    def check_end_condition(self):
        alive_players = [player for player in self.players if player.is_alive]
        mafia_count = sum(player.role == Role.MAFIA for player in alive_players)
        citizen_count = sum(player.role == Role.CITIZEN for player in alive_players)
        if mafia_count >= citizen_count or mafia_count == 0:
            return True
        return False

    def apply_rewards(self, citizen_reward, mafia_reward):
        for player in self.players:
            if player.team == Team.RED:
                player.reward += citizen_reward
            else:
                player.reward += mafia_reward

    def determine_winner(self):
        if not self.check_end_condition():
            return None  # The game has not ended yet
        alive_players = [player for player in self.players if player.is_alive]
        mafia_count = sum(player.role == Role.MAFIA for player in alive_players)
        if mafia_count == 0:
            logger.info("Citizens won")
            self.apply_rewards(10, -10)
            return Role.CITIZEN
        else:
            self.apply_rewards(-10, 10)
            logger.info("Mafia won")
            return Role.MAFIA

    def serialize(self):
        serialized_actions = []
        for action in self.game_actions:
            serialized_actions.append(repr(action))
        return serialized_actions

    def get_game_state_vector(self, player, max_actions=100):
        state_vector = []

        for p in self.players:
            state_vector.append(int(p.is_alive))
            state_vector.append(int(p in self.nominated_players))
            state_vector.append(p.team.index())
            if player == p:
                state_vector.append(1)
            else:
                state_vector.append(0)

        actions = [
            a
            for a in self.game_actions[:max_actions]
            if a.action_type != GameActionType.VOTE_RESULT
        ]
        for action in actions:
            action_type_vector = [0] * len(GameActionType)
            action_type_vector[action.action_type.index()] = 1
            state_vector.extend(action_type_vector)

            player_vector = [0] * len(self.players)
            player_vector[action.player.id] = 1
            state_vector.extend(player_vector)

            target_vector = [0] * (len(self.players) + 1)
            if action.target:
                target_vector[action.target.id] = 1
            else:
                target_vector[-1] = 1
            state_vector.extend(target_vector)

            belief_vector = [0] * (len(Role) + 1)
            if action.belief:
                belief_vector[action.belief.index()] = 1
            else:
                belief_vector[-1] = 1
            state_vector.extend(belief_vector)

        action_length = 30

        # Pad the state vector with zeros if there are fewer actions
        if len(actions) < max_actions:
            padding = [0] * (max_actions - len(actions)) * action_length
            state_vector.extend(padding)

        return torch.tensor(state_vector, dtype=torch.float32)

    def get_state_vector(self, player, action_type):
        # Convert the action type to a one-hot encoded vector
        action_vector = [0, 0, 0, 0]
        if action_type == "make_declarations":
            action_vector[0] = 1
        elif action_type == "vote":
            action_vector[1] = 1
        elif action_type == "kill":
            action_vector[2] = 1
        elif action_type == "nominate_player":
            action_vector[3] = 1

        state_vector = self.get_game_state_vector(player)

        # Concatenate the action vector and state vector
        full_vector = torch.cat(
            (torch.tensor(action_vector, dtype=torch.float32), state_vector)
        )

        return full_vector

    def create_mask(self, action_type):
        mask = torch.zeros(94)  # Total number of actions is 94 (10+11+63+10)
        if action_type == 'vote':
            for player in self.nominated_players:
                mask[player.id] = 1  # Only nominated players are considered
        elif action_type == 'nominate_player':
            for player in self.players:
                if player.is_alive:
                    mask[player.id + 10] = 1
        elif action_type == 'make_declarations':
            mask[21:84] = 1  # The next 63 actions are for declaring
        elif action_type == 'kill':
            mask[84:] = 1  # The last 10 actions are for killing
        return mask.bool()
