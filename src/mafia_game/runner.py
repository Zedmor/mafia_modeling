from mafia_game.game_state import CompleteGameState
from mafia_game.mcts import mcts_search

def run_simulations(num_simulations, computation_budget):
    initial_state = CompleteGameState.build()
    
    for _ in range(num_simulations):
        game_state = initial_state.clone()
        best_action = mcts_search(game_state, computation_budget)
        game_state.current_phase.execute_action(game_state, best_action)
        game_state.transition_to_next_phase()
        
        # Optional: Update weights or record statistics here
        # update_weights(game_state)
    
    # Optional: Save the updated weights or MCTS tree to disk
    # save_weights('weights.pkl')

if __name__ == "__main__":
    num_simulations = 100  # Adjust as needed
    computation_budget = 1000  # Adjust as needed
    
    run_simulations(num_simulations, computation_budget)
