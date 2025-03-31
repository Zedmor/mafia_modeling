from mafia_game.common import Role
from mafia_game.game_state import CompleteGameState, DayPhase

from mafia_game.logger import logger

def run_simulations(num_simulations):

    for _ in range(num_simulations):
        logger.info("============ NEW GAME ===========")
        game_state = CompleteGameState.build(human_player=Role.DON)
        while not game_state.is_terminal():
            if isinstance(game_state.current_phase, DayPhase):
                game_state.current_player.agent.utterance()
            allowed_actions = game_state.get_available_actions()
            best_action = game_state.current_player.agent.select_action(allowed_actions)
            game_state.execute_action(best_action)
        # logger.info(f"Game concluded, team won: {game_state.team_won}")


        # Optional: Update weights or record statistics here
        # update_weights(game_state)
    
    # Optional: Save the updated weights or MCTS tree to disk
    # save_weights('weights.pkl')

if __name__ == "__main__":
    num_simulations = 100  # Adjust as needed

    run_simulations(num_simulations)
