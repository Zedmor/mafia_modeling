import random

import numpy as np

from mafia_game.game_state import CompleteGameState, create_game_state_with_role
from mafia_game.common import Role, Team, MAX_PLAYERS
from mafia_game.actions import (
    NominationAction,
    SheriffDeclarationAction,
    PublicSheriffDeclarationAction,
    VoteAction,
    KillAction,
    DonCheckAction,
    SheriffCheckAction,
    )
from mafia_game.game_state import DayPhase
from mafia_game.logger import logger

# Helper function to create a game state with a specific role for testing

# Helper function to generate a random action based on the allowed actions
def generate_random_action(player_index, action_class, game_state):

    if action_class is VoteAction and game_state.nominated_players:
        return VoteAction(game_state.active_player, random.choice(game_state.nominated_players))

    if action_class is SheriffDeclarationAction:
        return action_class(player_index, i_am_sheriff=random.choice([True, False]))

    live_players = [i for i in range(MAX_PLAYERS)
                    if i != player_index and game_state.game_states[i].alive]

    if not live_players:
        return

    target_player = random.choice(live_players)

    # KillAction should be granted to Don or first Mafia on the table.

    if action_class in [
        NominationAction,
        KillAction,
        DonCheckAction,
        SheriffCheckAction,
        ]:
        return action_class(player_index, target_player)
    elif action_class is PublicSheriffDeclarationAction:
        return action_class(player_index, target_player, team=random.choice(list(Team)))
    else:
        raise ValueError("Unknown action class")


# Integration test for the game runner
def test_game_runner():
    # Initialize the game with random roles
    game_states = [
        create_game_state_with_role(r) for r in
        [Role.CITIZEN] * 6 + [Role.SHERIFF] + [Role.MAFIA] * 2 + [Role.DON]]
    random.shuffle(game_states)

    mafia_player_indexes = [i for i in range(10) if
                            game_states[i].private_data.role in  (Role.MAFIA, Role.DON)]

    for mafia_player in mafia_player_indexes:
        game_states[mafia_player].private_data.other_mafias.other_mafias = np.array(mafia_player_indexes)

    game = CompleteGameState(
        game_states=game_states,
        current_phase=DayPhase(),
        active_player=0,
        turn=0,
        team_won=Team.UNKNOWN,
        )
    logger.info(f"Starting turn {game.turn}")
    logger.info(f"First player {game.active_player}")
    # Run the game until it is completed
    while game.team_won == Team.UNKNOWN:

        started_player = game.active_player
        while True:
            allowed_actions = game.get_available_action_classes()
            player_state = game.game_states[game.active_player]
            if player_state.alive:
                for allowed_action_class in allowed_actions:
                    action = generate_random_action(game.active_player,
                                                    allowed_action_class,
                                                    game)
                    if action:
                        logger.info(action)
                        game.execute_action(action)
            game.active_player += 1
            if game.active_player > 9:
                game.active_player = 0
            if game.active_player == started_player:
                break

        game.transition_to_next_phase()
        if isinstance(game.current_phase, DayPhase):
            logger.info('==============================')
            logger.info(f"Starting turn {game.turn}")
            logger.info(f"First player {game.active_player}")

    # Check that the game has a winner
    assert game.team_won in [Team.RED_TEAM, Team.BLACK_TEAM]
    logger.info(f"Won: {game.team_won}")
