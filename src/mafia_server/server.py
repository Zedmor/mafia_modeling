import json
import logging
import random
import socket
import threading
from typing import Dict, Any, List, Optional, Tuple, Union

from mafia_server.models import (
    Role, Team, Phase, Player, GameState,
    ActionRequest, ActionResponse, GameEvent
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MafiaServer")

# Get the game logger from run_simulation.py
game_logger = logging.getLogger("GameLog")


class MafiaServer:
    """
    Server implementation for the Mafia game.
    
    The server manages connections to clients, game state, and the communication protocol.
    It provides a WebSocket-like interface where clients can connect and exchange JSON messages.
    """
    
    # Flag to indicate if the game is complete
    game_completed = False
    
    @staticmethod
    def get_player_roles_display(game_state: GameState) -> str:
        """Return a string showing players and their roles for game log display"""
        role_indicators = []
        for i, player in enumerate(game_state.players):
            # Only include alive players in the display
            if player.alive:
                # Abbreviate role: Citizen -> c, Sheriff -> s, Mafia -> m, Don -> d
                role_abbr = player.role.name[0].lower()
                role_indicators.append(f"{i}{role_abbr}")
        return "[" + ",".join(role_indicators) + "]"
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """
        Initialize the server
        
        Args:
            host: Host address to bind the server to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.clients = {}  # Dictionary mapping player_id to {socket, address}
        self.game_state = GameState.new_game()
        self.active_player = 0
        self.socket = None
        self.is_running = False
        self.lock = threading.Lock()  # For thread safety when modifying game state
        
        # Log initial game state with player roles
        player_roles = self.get_player_roles_display(self.game_state)
        game_logger.info(f"Players: {player_roles}")
    
    def start(self):
        """Start the server and listen for connections"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(10)  # Allow up to 10 queued connections
            self.is_running = True
            logger.info(f"Server started on {self.host}:{self.port}")
            
            # Start connection handler thread
            thread = threading.Thread(target=self._accept_connections)
            thread.daemon = True
            thread.start()
            
            return True
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    def stop(self):
        """Stop the server and close all connections"""
        self.is_running = False
        
        # Close all client connections
        client_ids = list(self.clients.keys())  # Create a copy of the keys to avoid dictionary changed during iteration
        for player_id in client_ids:
            if player_id in self.clients:
                try:
                    self.clients[player_id]["socket"].close()
                except Exception as e:
                    logger.error(f"Error closing client socket for player {player_id}: {e}")
        
        # Clear the clients dictionary
        self.clients.clear()
        
        # Close server socket
        if self.socket:
            try:
                self.socket.close()
                self.socket = None  # Explicitly set to None to aid garbage collection
            except Exception as e:
                logger.error(f"Error closing server socket: {e}")
        
        logger.info("Server stopped")
    
    def _accept_connections(self):
        """Accept incoming connections from clients"""
        while self.is_running:
            try:
                client_socket, address = self.socket.accept()
                logger.info(f"New connection from {address}")
                
                # Assign the client to the next available player_id
                player_id = self._get_next_available_player_id()
                if player_id is not None:
                    # Start a new thread to handle this client
                    client_thread = threading.Thread(
                        target=self._handle_client_connection,
                        args=(client_socket, address, player_id)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                else:
                    # No available player slots - use length-prefixed protocol
                    error_msg = json.dumps({
                        "type": "ERROR",
                        "message": "Game is full"
                    }, indent=2)
                    error_bytes = error_msg.encode('utf-8')
                    length_header = len(error_bytes).to_bytes(8, byteorder='big')
                    client_socket.sendall(length_header + error_bytes)
                    client_socket.close()
            except Exception as e:
                if self.is_running:
                    logger.error(f"Error accepting connection: {e}")
    
    def _get_next_available_player_id(self) -> Optional[int]:
        """
        Get the next available player ID
        
        Returns:
            The next available player ID, or None if the game is full
        """
        # Check if we have fewer than 10 connected clients
        if len(self.clients) < 10:
            # Find the first player_id that isn't already connected
            for i in range(10):
                if i not in self.clients:
                    return i
        return None
    
    def _handle_client_connection(self, client_socket: socket.socket, address: Tuple[str, int], player_id: int):
        """
        Handle a client connection
        
        Args:
            client_socket: The client's socket
            address: The client's address
            player_id: The assigned player ID
        """
        # Add the client to our dictionary
        self.clients[player_id] = {
            "socket": client_socket,
            "address": address
        }
        
        try:
            # Send initial game state to the client
            self._send_game_state(player_id)
            
            # Handle client messages
            self._handle_client_messages(client_socket, player_id)
        except Exception as e:
            logger.error(f"Error handling client connection: {e}")
        finally:
            # Remove client from dictionary and close the socket
            if player_id in self.clients:
                del self.clients[player_id]
            
            try:
                client_socket.close()
            except:
                pass
            
            logger.info(f"Connection closed for player {player_id}")
    
    def _handle_client_messages(self, client_socket: socket.socket, player_id: int):
        """
        Handle messages from a client using length-prefixed message framing
        
        Args:
            client_socket: The client's socket
            player_id: The player's ID
        """
        message_buffer = b""  # Binary buffer to store received data
        expected_length = None  # Length of the current message being received
        header_size = 8  # Size of the message length header (8 bytes for a 64-bit integer)
        
        while self.is_running:
            try:
                # Receive chunk of data
                chunk = client_socket.recv(4096)
                if not chunk:
                    # Connection closed by the client
                    break
                
                # Add the received chunk to our buffer
                message_buffer += chunk
                
                # Process all complete messages in the buffer
                while self.is_running and len(message_buffer) > 0:
                    # If we don't know the message length yet, try to read it
                    if expected_length is None:
                        if len(message_buffer) < header_size:
                            # Not enough data to read the header, wait for more
                            break
                            
                        # Extract message length from the first 8 bytes
                        length_bytes = message_buffer[:header_size]
                        expected_length = int.from_bytes(length_bytes, byteorder='big')
                        message_buffer = message_buffer[header_size:]
                    
                    # Check if we have the complete message
                    if len(message_buffer) < expected_length:
                        # Not enough data yet, wait for more
                        break
                    
                    # We have a complete message, extract it
                    message_data = message_buffer[:expected_length]
                    message_buffer = message_buffer[expected_length:]
                    expected_length = None  # Reset for the next message
                    
                    # Decode and parse the message
                    try:
                        message_text = message_data.decode('utf-8', errors='replace')
                        message = json.loads(message_text)
                        
                        # Process the message
                        logger.debug(f"Received complete message from player {player_id}: {message}")
                        self._process_message(message)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from player {player_id}: {e}")
                        logger.error(f"Problematic message: {message_text[:100]}...")
                    except Exception as e:
                        logger.error(f"Error processing message from player {player_id}: {e}")
            except ConnectionResetError:
                logger.info(f"Connection reset by player {player_id}")
                break
            except Exception as e:
                logger.error(f"Error handling message from player {player_id}: {e}")
                if message_buffer:
                    logger.debug(f"Current buffer: {message_buffer[:100]}...")
                break
    
    def _process_message(self, message: Dict[str, Any]):
        """
        Process a message from a client
        
        Args:
            message: The message to process
        """
        if message["type"] == "ACTION_RESPONSE":
            # Validate the message
            player_id = message["player_id"]
            action = message["action"]
            
            # Check if it's the player's turn and they're alive
            if player_id != self.active_player:
                self._send_error(player_id, "Not your turn")
                return
                
            # Check if the player is alive
            if not self.game_state.players[player_id].alive:
                self._send_error(player_id, f"Player {player_id} is not alive and cannot take actions")
                return
            
            # Validate action against current valid actions
            valid_actions = self.game_state.get_valid_actions()
            is_valid, error_msg = self._validate_action(action, valid_actions)
            
            if not is_valid:
                self._send_error(player_id, error_msg)
                return
            
            # Apply the action to the game state
            with self.lock:
                self._apply_action(action)
                
                # Broadcast updated game state to all clients
                self._broadcast_game_state()
        else:
            logger.warning(f"Unknown message type: {message['type']}")
    
    def _apply_action(self, action: Dict[str, Any]):
        """
        Apply an action to the game state
        
        Args:
            action: The action to apply
        """
        action_type = action["type"]
        
        try:
            if action_type == "DECLARATION":
                # Apply declaration
                self.game_state.apply_declaration(
                    self.active_player,
                    action["declaration"],
                    action.get("sheriff_claims")
                )
                
                # Log the declaration for debugging
                game_logger.info(f"Player {self.active_player} belief: {action['declaration']}")
                if action.get("sheriff_claims"):
                    # Interpret sheriff claims in a more readable format
                    sheriff_claims_text = self._format_sheriff_claims(action.get("sheriff_claims"))
                    game_logger.info(f"Player {self.active_player} sheriff declaration: {sheriff_claims_text}")
                
                # Sample and apply nomination if provided
                if "nomination_policy" in action and action["nomination_policy"]:
                    nominated_players = list(map(int, action["nomination_policy"].keys()))
                    probabilities = list(map(float, action["nomination_policy"].values()))
                    
                    # Sample from the nomination policy - fixed indentation
                    if sum(probabilities) > 0:
                        target = random.choices(nominated_players, weights=probabilities, k=1)[0]
                        try:
                            # Store the nominated player
                            target_id = int(target)
                            
                            # Add to player's nominations list
                            self.game_state.players[self.active_player].nominations.append(target_id)
                            
                            # Apply nomination to game state
                            self.game_state.apply_nomination(self.active_player, target_id)
                            
                            # Broadcast the nomination event to all clients
                            self._broadcast_event_to_all(
                                "PLAYER_NOMINATED",
                                by_player=self.active_player,
                                target=target_id
                            )
                            
                            # Log the nomination
                            logger.info(f"Player {self.active_player} nominated player {target_id}")
                        except Exception as e:
                            logger.error(f"Error applying nomination: {e}")
                
                # Advance to the next player - added for test compatibility
                self.active_player = (self.active_player + 1) % len(self.game_state.players)
            
            elif action_type == "VOTE":
                # Apply vote
                target_id = action["target"]
                self.game_state.apply_vote(self.active_player, target_id)
                
                # Log the vote for debugging
                game_logger.info(f"Player {self.active_player} votes for player {target_id}")
            
            elif action_type == "ELIMINATE_ALL_VOTE":
                # Apply eliminate-all vote
                vote = action["vote"]
                self.game_state.apply_eliminate_all_vote(self.active_player, vote)
                
                # Log the eliminate-all vote
                game_logger.info(f"Player {self.active_player} eliminate-all vote: {vote}")
            
            elif action_type == "KILL":
                # Apply kill
                target_id = action["target"]
                self.game_state.apply_kill(target_id)
                
                # Log the kill action
                if target_id != -1:  # Only log if not skipping
                    game_logger.info(f"Mafia ({self.active_player}) kills player {target_id}")
                
                # Process the kill immediately to check for win conditions
                if target_id != -1:
                    # Apply kills immediately to check win condition
                    self.game_state._process_night_end()
                    
                    # Check win condition after kill
                    winner = self.game_state.check_win_condition()
                    if winner:
                        self.game_state.winner = winner
                        self.game_state.current_phase = Phase.GAME_OVER
                        self._broadcast_event_to_all(
                            "GAME_OVER",
                            winner=winner.name
                        )
                        
                        # Log game over
                        game_logger.info(f"Game Over! Winner: {winner.name}")
                        return
                
                # After a kill action, we need to explicitly transition to next phase
                # since there may only be one mafia player (no cycle completion)
                self.game_state._transition_phase()
                self.active_player = self.game_state.active_player
                return
            
            elif action_type == "DON_CHECK":
                # Apply don check
                target_id = action["target"]
                result = self.game_state.apply_don_check(target_id)
                
                # Log the don check
                game_logger.info(f"Don ({self.active_player}) checks player {target_id}, result: {result}")
                
                # Send the result only to the Don
                self._send_check_result(self.active_player, target_id, result)
                
                # After a don check, explicitly transition to next phase
                # since there is only one Don (no cycle completion)
                self.game_state._transition_phase()
                self.active_player = self.game_state.active_player
                return
            
            elif action_type == "SHERIFF_CHECK":
                # Apply sheriff check
                target_id = action["target"]
                result = self.game_state.apply_sheriff_check(target_id)
                
                # Log the sheriff check
                game_logger.info(f"Sheriff ({self.active_player}) checks player {target_id}, result: {result}")
                
                # Send the result only to the Sheriff
                self._send_check_result(self.active_player, target_id, result)
                
                # After a sheriff check, explicitly transition to next phase
                # since there is only one Sheriff (no cycle completion)
                self.game_state._transition_phase()
                self.active_player = self.game_state.active_player
                return
            
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return
            
            # Advance to the next player
            cycle_completed = self.game_state._advance_player()
            # Update server's active player to match game state
            self.active_player = self.game_state.active_player
            if cycle_completed:
                # All players have taken their actions in this phase
                
                # If we're in the voting phase, resolve votes before transitioning
                if self.game_state.current_phase == Phase.VOTING:
                    logger.info(f"Resolving votes for voting round {self.game_state.voting_round}")
                    if self.game_state.voting_round == 0 or self.game_state.voting_round == 1:
                        # Log current votes before resolving
                        votes = {i: player.vote_for for i, player in enumerate(self.game_state.players) 
                               if player.alive and player.vote_for is not None}
                        logger.info(f"Current votes: {votes}")
                        
                        eliminated_player = self.game_state._resolve_votes()
                        
                        if eliminated_player is not None:
                            logger.info(f"Player {eliminated_player} was eliminated by vote")
                            # If a player was eliminated, broadcast it to all clients
                            self._broadcast_event_to_all(
                                "PLAYER_ELIMINATED",
                                player_id=eliminated_player
                            )
                            
                            # Log the player elimination with role (visible only in server logs, not to clients)
                            eliminated_role = self.game_state.players[eliminated_player].role.name
                            game_logger.info(f"Player {eliminated_player} ({eliminated_role}) was eliminated by vote")
                            
                            # Check win condition after elimination
                            winner = self.game_state.check_win_condition()
                            if winner:
                                self.game_state.winner = winner
                                self.game_state.current_phase = Phase.GAME_OVER
                                self._broadcast_event_to_all(
                                    "GAME_OVER",
                                    winner=winner.name
                                )
                                
                                # Log game over
                                game_logger.info(f"Game Over! Winner: {winner.name}")
                                return
                        else:
                            logger.info(f"No player eliminated. Voting round advanced to {self.game_state.voting_round}")
                    elif self.game_state.voting_round == 2:
                        # Resolve eliminate-all voting
                        self.game_state._resolve_eliminate_all_vote()
                        
                        # Check win condition after possible eliminations
                        winner = self.game_state.check_win_condition()
                        if winner:
                            self.game_state.winner = winner
                            self.game_state.current_phase = Phase.GAME_OVER
                            self._broadcast_event_to_all(
                                "GAME_OVER",
                                winner=winner.name
                            )
                            return
                
                # Only transition to next phase if game is not over and we're not in a voting tie situation
                if self.game_state.current_phase != Phase.GAME_OVER:
                    # If we're in the voting phase with a tie, don't transition to the next phase yet
                    if self.game_state.current_phase == Phase.VOTING and self.game_state.voting_round > 0:
                        # Reset active player to first alive player for next voting round
                        self.game_state.active_player = self.game_state._find_first_alive_player()
                        self.active_player = self.game_state.active_player
                        self.game_state.phase_start_player = self.active_player
                        
                        # Log that we're entering a tie-break voting round
                        if self.game_state.voting_round == 1:
                            tied_players_str = ", ".join([str(p) for p in self.game_state.tied_players])
                            game_logger.info(f"Tie detected. Moving to re-vote between players {tied_players_str}")
                        elif self.game_state.voting_round == 2:
                            game_logger.info("Second tie. Moving to eliminate-all voting")
                    else:
                        # Normal phase transition
                        old_phase = self.game_state.current_phase
                        self.game_state._transition_phase()
                        # Log the phase transition
                        current_phase = self.game_state.current_phase
                        alive_players = self.get_player_roles_display(self.game_state)
                        game_logger.info(f"Turn {self.game_state.turn}. Phase {old_phase.name} -> {current_phase.name}")
                        game_logger.info(f"Players alive {alive_players}")
                
                # Update active player
                self.active_player = self.game_state.active_player
                
                # Ensure the active player is connected, if not, find the next connected player
                if self.active_player not in self.clients:
                    logger.warning(f"Active player {self.active_player} not connected, finding next connected player")
                    self._find_next_connected_player()
            
        except Exception as e:
            logger.error(f"Error applying action: {e}")
            # Send error message to the client
            self._send_error(self.active_player, str(e))
    
    def _send_length_prefixed_message(self, client_socket: socket.socket, message: Dict[str, Any]):
        """
        Send a message with length prefix
        
        Args:
            client_socket: The client's socket
            message: The message to send
        """
        # Format the message with length prefix
        message_json = json.dumps(message, indent=2)
        message_bytes = message_json.encode('utf-8')
        message_length = len(message_bytes)
        
        # Create header (8-byte length prefix)
        header = message_length.to_bytes(8, byteorder='big')
        
        # Send header followed by message
        client_socket.sendall(header + message_bytes)
        
        # Log message size for debugging
        if message_length > 10000:
            logger.debug(f"Sent large message: {message_length} bytes")
            
    def _send_game_state(self, player_id: int):
        """
        Send the current game state to a specific player
        
        Args:
            player_id: The player to send the game state to
        """
        if player_id not in self.clients:
            return
        
        client_socket = self.clients[player_id]["socket"]
        
        try:
            # Get the observation for this player
            observation = self.game_state.get_observation(player_id)
            
            # Get valid actions for this player if it's their turn and they're alive
            valid_actions = {}
            if player_id == self.active_player and self.game_state.players[player_id].alive:
                valid_actions = self.game_state.get_valid_actions()
            
            # Create the action request
            request = ActionRequest(
                type="ACTION_REQUEST",
                player_id=player_id,
                phase=self.game_state.current_phase.name,
                valid_actions=valid_actions,
                observation=observation
            )
            
            # Send the request to the client
            self._send_length_prefixed_message(client_socket, request.to_dict())
        except Exception as e:
            logger.error(f"Error sending game state to player {player_id}: {e}")
    
    def _broadcast_game_state(self):
        """
        Send the game state to all connected players, with valid actions only for the active player
        
        This ensures dead players still receive game updates but can't take actions
        """
        # Always send state to active player first
        if self.active_player in self.clients:
            self._send_game_state(self.active_player)
        else:
            logger.warning(f"Active player {self.active_player} not connected")
            
        # Create a copy of the client IDs to avoid dictionary changed during iteration error
        client_ids = list(self.clients.keys())
        
        # Send game state updates to all other connected players
        for player_id in client_ids:
            if player_id != self.active_player and player_id in self.clients:
                self._send_game_state(player_id)
    
    def _broadcast_event_to_all(self, event_type: str, **event_data):
        """
        Broadcast an event to all connected clients without action requests
        
        Args:
            event_type: The type of event
            **event_data: Additional event data
        """
        # Set the game_completed flag when a GAME_OVER event is broadcast
        if event_type == "GAME_OVER":
            self.game_completed = True
            logger.info("Game completed, setting game_completed flag")
            
        event = GameEvent(
            type="GAME_EVENT",
            event=event_type,
            **event_data
        )
        
        # Create a copy of the client IDs to avoid dictionary changed during iteration error
        client_ids = list(self.clients.keys())
        
        for player_id in client_ids:
            if player_id not in self.clients:
                continue
            
            client_socket = self.clients[player_id]["socket"]
            
            try:
                # Send the event to the client using length-prefixed protocol
                self._send_length_prefixed_message(client_socket, event.to_dict())
            except Exception as e:
                logger.error(f"Error sending event to player {player_id}: {e}")
    
    def _send_check_result(self, player_id: int, target_id: int, result: Union[bool, Team]):
        """
        Send the result of a check to a player
        
        Args:
            player_id: The player to send the result to
            target_id: The player that was checked
            result: The result of the check
        """
        if player_id not in self.clients:
            return
        
        client_socket = self.clients[player_id]["socket"]
        
        try:
            # Create the result message
            if isinstance(result, bool):
                # Don check result
                event = GameEvent(
                    type="GAME_EVENT",
                    event="DON_CHECK_RESULT",
                    target=target_id,
                    is_sheriff=result
                )
            else:
                # Sheriff check result
                event = GameEvent(
                    type="GAME_EVENT",
                    event="SHERIFF_CHECK_RESULT",
                    target=target_id,
                    team=result.name
                )
            
            # Send the event to the client using length-prefixed protocol
            self._send_length_prefixed_message(client_socket, event.to_dict())
        except Exception as e:
            logger.error(f"Error sending check result to player {player_id}: {e}")
    
    def _send_error(self, player_id: int, error_message: str):
        """
        Send an error message to a player
        
        Args:
            player_id: The player to send the error to
            error_message: The error message
        """
        if player_id not in self.clients:
            return
        
        client_socket = self.clients[player_id]["socket"]
        
        try:
            # Create the error message
            error = {
                "type": "ERROR",
                "message": error_message
            }
            
            # Send the error to the client using length-prefixed protocol
            self._send_length_prefixed_message(client_socket, error)
        except Exception as e:
            logger.error(f"Error sending error message to player {player_id}: {e}")
    
    def _find_next_connected_player(self):
        """Find the next connected player to be the active player"""
        original_player = self.active_player
        
        # Keep advancing until we find a connected player or come back to the original player
        while True:
            self.active_player = (self.active_player + 1) % 10
            
            # If we're back at the original player, none are connected
            if self.active_player == original_player:
                break
            
            # If this player is connected, we found our active player
            if self.active_player in self.clients and self.game_state.players[self.active_player].alive:
                logger.info(f"New active player is {self.active_player}")
                
                # Update the game state's active player
                self.game_state.active_player = self.active_player
                
                # Send the updated game state to the active player
                self._broadcast_game_state()
                return
    
    def _format_sheriff_claims(self, sheriff_claims: List[List[int]]) -> str:
        """
        Format sheriff claims in a more readable format
        
        Args:
            sheriff_claims: 10x10 matrix of sheriff claims
            
        Returns:
            A string representation of the sheriff claims
        """
        readable_claims = []
        
        for turn, row in enumerate(sheriff_claims):
            # Skip rows with no claims (all zeros)
            if all(val == 0 for val in row):
                continue
                
            for player_idx, result in enumerate(row):
                if result != 0:
                    # Convert result to a string representation
                    result_str = "r" if result == 1 else "b"  # r for RED, b for BLACK
                    readable_claims.append(f"Turn{turn}: {player_idx}{result_str}")
        
        if not readable_claims:
            return "No claims"
            
        return ", ".join(readable_claims)
    
    def _validate_action(self, action: Dict[str, Any], valid_actions: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate an action against the current valid actions
        
        Args:
            action: The action to validate
            valid_actions: The current valid actions
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        action_type = action["type"]
        
        if action_type == "DECLARATION":
            # Declarations are always valid as long as they're allowed
            if "declaration" in valid_actions:
                return True, ""
            return False, "Declarations not valid in current phase"
            
        elif action_type == "VOTE":
            if "vote" not in valid_actions:
                return False, "Voting not valid in current phase"
            
            target_id = action.get("target")
            if target_id not in valid_actions["vote"]:
                return False, f"Cannot vote for player {target_id}"
                
            return True, ""
            
        elif action_type == "ELIMINATE_ALL_VOTE":
            if "eliminate_all" not in valid_actions:
                return False, "Eliminate-all voting not valid in current phase"
            return True, ""
            
        elif action_type == "KILL":
            if "kill" not in valid_actions:
                return False, "Killing not valid in current phase or for this role"
                
            target_id = action.get("target")
            if target_id not in valid_actions["kill"]:
                return False, f"Cannot kill player {target_id}"
                
            return True, ""
            
        elif action_type == "DON_CHECK":
            if "don_check" not in valid_actions:
                return False, "Don check not valid in current phase or for this role"
                
            target_id = action.get("target")
            if target_id not in valid_actions["don_check"]:
                return False, f"Cannot check player {target_id}"
                
            return True, ""
            
        elif action_type == "SHERIFF_CHECK":
            if "sheriff_check" not in valid_actions:
                return False, "Sheriff check not valid in current phase or for this role"
                
            target_id = action.get("target")
            if target_id not in valid_actions["sheriff_check"]:
                return False, f"Cannot check player {target_id}"
                
            return True, ""
            
        return False, f"Unknown action type: {action_type}"
    
    def _broadcast_event(self, event: GameEvent):
        """
        Broadcast a game event to all connected clients
        
        Args:
            event: The event to broadcast
        """
        # Create a copy of the client IDs to avoid dictionary changed during iteration error
        client_ids = list(self.clients.keys())
        
        for player_id in client_ids:
            if player_id not in self.clients:
                continue
            
            client_socket = self.clients[player_id]["socket"]
            
            try:
                # Send the event to the client using length-prefixed protocol
                self._send_length_prefixed_message(client_socket, event.to_dict())
            except Exception as e:
                logger.error(f"Error sending event to player {player_id}: {e}")


if __name__ == "__main__":
    # Create and start the server
    server = MafiaServer()
    if server.start():
        try:
            # Keep the main thread running
            while True:
                pass
        except KeyboardInterrupt:
            # Stop the server on Ctrl+C
            server.stop()
