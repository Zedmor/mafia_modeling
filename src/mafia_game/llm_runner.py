import random

from mafia_game.actions import NullAction
from mafia_game.game_state import CompleteGameState, EndPhase, Phase

from mafia_game.logger import logger

def run_simulations(num_simulations):

    for _ in range(num_simulations):
        logger.info("============ NEW GAME ===========")
        game_state = CompleteGameState.build()
        while not game_state.is_terminal():
            allowed_actions = game_state.get_available_actions()
            best_action = random.choice(allowed_actions)
            if not isinstance(best_action, NullAction):
                logger.info(best_action)
            game_state.execute_action(best_action)
        logger.info(f"Game concluded, team won: {game_state.team_won}")


        # Optional: Update weights or record statistics here
        # update_weights(game_state)
    
    # Optional: Save the updated weights or MCTS tree to disk
    # save_weights('weights.pkl')

if __name__ == "__main__":
    num_simulations = 10000  # Adjust as needed

    run_simulations(num_simulations)
