import random
import pytest
from mafia_game.models import Role, Policy


def random_citizen_declarations(game_state, player):
    declarations = []
    for _ in range(random.randint(0, 3)):
        target = random.choice(game_state.players)
        belief = random.choice(list(Role))
        declarations.append((target, belief))
    return declarations


def random_citizen_kill(game_state, player):
    return None


def random_mafia_declarations(game_state, player):
    declarations = []
    for _ in range(random.randint(0, 3)):
        target = random.choice(
            [p for p in game_state.players if p.role == Role.CITIZEN]
        )
        belief = random.choice(list(Role))
        declarations.append((target, belief))
    return declarations


def random_vote(game_state, player):
    if game_state.nominated_players:
        return random.choice(game_state.nominated_players)


def mafia_vote(game_state, player):
    citizens = [p for p in game_state.nominated_players if p.role == Role.CITIZEN]
    if citizens:
        return random.choice(citizens)
    return random_vote(game_state, player)


def random_nominate(game_state, player):
    return random.choice([player for player in game_state.players if player.is_alive] + [None] * 3)


def random_mafia_kill(game_state, player):
    alive_citizens = [
        p for p in game_state.players if p.is_alive and p.role == Role.CITIZEN
    ]
    return random.choice(alive_citizens) if alive_citizens else None


class StaticPolicy(Policy):
    policy_name = 'static'

    declarations_func = None
    vote_func = None
    kill_func = None
    nomination_func = None

    @classmethod
    def make_declarations(cls, game_state, player):
        return cls.declarations_func(game_state, player)

    @classmethod
    def vote(cls, game_state, player):
        return cls.vote_func(game_state, player)

    @classmethod
    def kill(cls, game_state, player):
        return cls.kill_func(game_state, player)

    @classmethod
    def nominate_player(cls, game_state, player):
        return cls.nomination_func(game_state, player)

    def __init__(self):
        pass


class StaticCitizenPolicy(StaticPolicy):
    policy_name = 'static_citizen'

    declarations_func = random_citizen_declarations
    vote_func = random_vote
    kill_func = random_citizen_kill
    nomination_func = random_nominate


class StaticMafiaPolicy(StaticPolicy):
    policy_name = 'static_mafia'

    declarations_func = random_mafia_declarations
    vote_func = mafia_vote
    kill_func = random_mafia_kill
    nomination_func = random_nominate
