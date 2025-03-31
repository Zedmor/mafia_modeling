import argparse
import threading
import time
import logging
import os
from typing import List, Union, Dict, Any
import json

from mafia_server.server import MafiaServer
from mafia_server.client import MafiaClient
from mafia_server.random_agent import RandomAgent
from mafia_server.models import Role, Team, Phase, GameState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MafiaSimulation")

# Configure file logger for sanitized game logs
# Use absolute path to logs directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
game_log_file = os.path.join(project_root, 'logs', 'run_simulation.log')
game_logger = logging.getLogger("GameLog")
game_logger.setLevel(logging.INFO)
# We'll set up the file handler in the run_simulation function to clear the log file for each run

def configure_logging(verbose=False, log_to_file=True):
    """
    Configure logging levels for all loggers
    
    Args:
        verbose: Whether to enable verbose (DEBUG) logging
    """
    root_logger = logging.getLogger()
    if verbose:
        root_logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled (DEBUG level)")
    else:
        root_logger.setLevel(logging.INFO)

def setup_game_logger():
    """Configure the file logger for game logs and clear the log file"""
    # Remove existing file handlers to avoid duplicate log entries
    for handler in game_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            game_logger.removeHandler(handler)
            handler.close()
    
    # Clear the log file if it exists
    with open(game_log_file, 'w') as f:
        f.write('')  # Clear file
    
    # Add file handler
    file_handler = logging.FileHandler(game_log_file)
    file_formatter = logging.Formatter('%(message)s')  # Simple format for readability
    file_handler.setFormatter(file_formatter)
    game_logger.addHandler(file_handler)
    
    logger.info(f"Game log file initialized at {game_log_file}")

def run_simulation(num_clients: int = 10, delay: float = 0.5, host: str = "localhost", port: int = 8765, 
                 use_random_agents: bool = False, verbose: bool = False, num_games: int = 1):
    """
    Run a simulation with multiple clients
    
    Args:
        num_clients: Number of clients to start
        delay: Delay between starting clients
        host: Host address of the server
        port: Port of the server
        use_random_agents: Whether to use random agents instead of basic clients
        verbose: Whether to enable verbose logging for random agents
        num_games: Number of games to run in succession
    """
    # Configure logging based on verbose flag
    configure_logging(verbose)
    
    # Set up game logger
    setup_game_logger()
    
    for game_num in range(num_games):
        # Use a different port for each game to avoid address already in use errors
        current_port = port + game_num
        
        logger.info(f"Starting game {game_num + 1} of {num_games}")
        game_logger.info(f"Game {game_num} started.")
        
        # Start the server with a unique port
        server = MafiaServer(host=host, port=current_port)
        
        # Reset the game_completed flag for this game
        server.game_completed = False
        
        if not server.start():
            logger.error(f"Failed to start server on port {current_port}")
            # Try with a different port
            current_port = current_port + 1000
            logger.info(f"Retrying with port {current_port}")
            server = MafiaServer(host=host, port=current_port)
            if not server.start():
                logger.error(f"Failed to start server on alternate port {current_port}")
                return
        
        logger.info(f"Server started on {host}:{current_port}")
        
        # Wait a bit for the server to initialize
        # time.sleep(1)
        
        # Start the clients
        clients: List[Union[MafiaClient, RandomAgent]] = []
        
        for i in range(num_clients):
            if use_random_agents:
                # Create a random agent
                client = RandomAgent(host=host, port=current_port, agent_id=i, verbose=verbose)
                if client.connect():
                    logger.info(f"RandomAgent {i} connected")
                    clients.append(client)
                else:
                    logger.error(f"Failed to connect RandomAgent {i}")
            else:
                # Create a regular client
                client = MafiaClient(host=host, port=current_port)
                if client.connect():
                    logger.info(f"Client {i} connected")
                    clients.append(client)
                else:
                    logger.error(f"Failed to connect client {i}")
            
            # Wait a bit before starting the next client
            # time.sleep(delay)
        
        logger.info(f"Started {len(clients)} clients")
        
        # Wait for the game to complete or until interrupted
        try:
            completed_normally = False
            start_time = time.time()  # Track when the game started
            while server.is_running:
                # Check if the server has marked the game as completed
                if server.game_completed:
                    logger.info("Game completed flag set, ending game")
                    completed_normally = True
                    break
                
                # Check if any clients are still connected
                connected_clients = False
                for client in clients:
                    if isinstance(client, RandomAgent) and client.connected:
                        connected_clients = True
                        break
                    elif isinstance(client, MafiaClient) and client.is_connected:
                        connected_clients = True
                        break
                
                if not connected_clients:
                    logger.info("All clients disconnected, game complete")
                    completed_normally = True
                    break
                    
                time.sleep(1)
                
                # If the game is taking too long (over 3 minutes), break
                if not completed_normally and time.time() - start_time > 180:
                    logger.warning("Game taking too long, forcing completion")
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            break  # Exit the game loop entirely
        finally:
            # Stop all clients
            for client in clients:
                if isinstance(client, RandomAgent):
                    client.disconnect()
                else:
                    client.disconnect()
            
            # Stop the server
            server.stop()
            
            logger.info(f"Game {game_num + 1} ended")
            
            # Add a short delay to ensure sockets are fully released before next game
            time.sleep(3)
    
    # Log the actual number of completed games
    completed_games = min(game_num + 1, num_games)
    logger.info(f"Simulation of {completed_games} games completed")
    
    # Verify all clients and servers are shut down
    if 'clients' in locals():
        active_clients = sum(1 for client in clients if 
                             (isinstance(client, RandomAgent) and client.connected) or
                             (isinstance(client, MafiaClient) and client.is_connected))
        if active_clients > 0:
            logger.warning(f"{active_clients} clients still connected. Forcing disconnect...")
            for client in clients:
                try:
                    if isinstance(client, RandomAgent) and client.connected:
                        client.disconnect()
                    elif isinstance(client, MafiaClient) and client.is_connected:
                        client.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting client: {e}")
    
    if 'server' in locals() and server.is_running:
        logger.warning("Server still running. Forcing shutdown...")
        try:
            server.stop()
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
            
    logger.info("All clients and servers have been shut down")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a Mafia game simulation with multiple clients")
    parser.add_argument("--num-clients", type=int, default=10, help="Number of clients to start")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between starting clients")
    parser.add_argument("--host", type=str, default="localhost", help="Host address of the server")
    parser.add_argument("--port", type=int, default=8765, help="Port of the server")
    parser.add_argument("--random", action="store_true", help="Use random agents that make automatic decisions")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging for random agents")
    parser.add_argument("--num-games", type=int, default=1, help="Number of games to run in succession")
    args = parser.parse_args()
    
    run_simulation(
        num_clients=args.num_clients,
        delay=args.delay,
        host=args.host,
        port=args.port,
        use_random_agents=args.random,
        verbose=args.verbose,
        num_games=args.num_games
    )
