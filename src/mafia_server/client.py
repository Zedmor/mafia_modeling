import json
import socket
import logging
import threading
from typing import Dict, Any, Optional, Callable

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MafiaClient")


class MafiaClient:
    """
    Client implementation for the Mafia game.
    
    This client connects to a MafiaServer instance and handles the communication protocol.
    It is designed to be simple and allow for easy interaction with the server.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765, 
                 action_callback: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None):
        """
        Initialize the client
        
        Args:
            host: Host address of the server
            port: Port of the server
            action_callback: Callback function to determine what action to take when prompted
        """
        self.host = host
        self.port = port
        self.socket = None
        self.is_connected = False
        self.player_id = None
        self.action_callback = action_callback
        self.receive_thread = None
    
    def connect(self) -> bool:
        """
        Connect to the server
        
        Returns:
            True if the connection was successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.is_connected = True
            logger.info(f"Connected to server at {self.host}:{self.port}")
            
            # Start the receive thread
            self.receive_thread = threading.Thread(target=self._receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            
            return True
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the server"""
        self.is_connected = False
        if self.socket:
            self.socket.close()
        logger.info("Disconnected from server")
    
    def _receive_messages(self):
        """
        Handle messages from the server using length-prefixed message framing
        """
        message_buffer = b""  # Binary buffer to store received data
        expected_length = None  # Length of the current message being received
        header_size = 8  # Size of the message length header (8 bytes for a 64-bit integer)
        
        while self.is_connected:
            try:
                # Receive chunk of data
                chunk = self.socket.recv(4096)
                if not chunk:
                    # Connection closed by the server
                    logger.info("Connection closed by server")
                    self.is_connected = False
                    break
                
                # Add the received chunk to our buffer
                message_buffer += chunk
                
                # Process all complete messages in the buffer
                while self.is_connected and len(message_buffer) > 0:
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
                        self._process_message(message)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON: {e}")
                        logger.error(f"Problematic message: {message_text[:100]}...")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
            except ConnectionResetError:
                logger.info("Connection reset by server")
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                if message_buffer:
                    logger.debug(f"Current buffer: {message_buffer[:100]}...")
                self.is_connected = False
                break
    
    def _process_message(self, message: Dict[str, Any]):
        """
        Process a message from the server
        
        Args:
            message: The message to process
        """
        if message["type"] == "ACTION_REQUEST":
            # Store the player ID
            self.player_id = message["player_id"]
            
            # If it's our turn and we have a callback, call it to get the action
            if self.action_callback:
                try:
                    action = self.action_callback(message)
                    if action:
                        self._send_action(action)
                except Exception as e:
                    logger.error(f"Error in action callback: {e}")
            else:
                logger.info(f"Received ACTION_REQUEST: {message}")
                # We don't have a callback, so the user needs to manually send an action
                # Display the valid actions to the user
                logger.info(f"\nIt's your turn (Player {self.player_id})!")
                logger.info(f"Phase: {message['phase']}")
                logger.info(f"Valid actions: {json.dumps(message['valid_actions'], indent=2)}")
                logger.info(f"Observation: {json.dumps(message['observation'], indent=2)}")
                logger.info("Use the send_action method to respond")
        
        elif message["type"] == "GAME_EVENT":
            logger.info(f"Received GAME_EVENT: {json.dumps(message, indent=2)}")
            logger.info(f"\nGame Event: {message['event']}")
            # Display additional information based on the event
            if message["event"] == "PLAYER_ELIMINATED":
                logger.info(f"Player {message['player_id']} was eliminated")
                logger.info(f"They were a {message['revealed_role']}")
            elif message["event"] == "SHERIFF_CHECK_RESULT":
                logger.info(f"Sheriff check result for Player {message['target']}: {message['team']}")
            elif message["event"] == "DON_CHECK_RESULT":
                logger.info(f"Don check result for Player {message['target']}: {'Sheriff' if message['is_sheriff'] else 'Not Sheriff'}")
            elif message["event"] == "GAME_OVER":
                logger.info(f"Game over! Winner: {message.get('winner', 'Unknown')}")
                # Auto-disconnect when game is over
                self.disconnect()
        
        elif message["type"] == "ERROR":
            logger.error(f"Received ERROR: {json.dumps(message, indent=2)}")
            logger.error(f"\nError: {message['message']}")
    
    def send_action(self, action_type: str, **kwargs):
        """
        Send an action to the server
        
        Args:
            action_type: The type of action to send
            **kwargs: Additional arguments for the action
        """
        action = {
            "type": action_type,
            **kwargs
        }
        
        self._send_action(action)
    
    def _send_action(self, action: Dict[str, Any]):
        """
        Send an action to the server
        
        Args:
            action: The action to send
        """
        if not self.is_connected:
            logger.error("Not connected to server")
            return
        
        if self.player_id is None:
            logger.error("Player ID not yet assigned")
            return
        
        try:
            # Create the action response
            response = {
                "type": "ACTION_RESPONSE",
                "player_id": self.player_id,
                "action": action
            }
            
            # Format the message with length prefix
            message_json = json.dumps(response)
            message_bytes = message_json.encode('utf-8')
            message_length = len(message_bytes)
            
            # Create header (8-byte length prefix)
            header = message_length.to_bytes(8, byteorder='big')
            
            # Send header followed by message
            self.socket.sendall(header + message_bytes)
            logger.debug(f"Sent action: {action} (size: {message_length} bytes)")
        except Exception as e:
            logger.error(f"Error sending action: {e}")


# Example usage
if __name__ == "__main__":
    def sample_action_callback(message):
        """Simple callback that randomly selects an action"""
        import random
        
        # If it's not our turn, do nothing
        if message["player_id"] != client.player_id:
            return None
        
        phase = message["phase"]
        valid_actions = message["valid_actions"]
        
        if not valid_actions:
            logger.info("No valid actions available")
            return None
        
        # Map phase names to action types expected by the server
        action_type_map = {
            "DECLARATION": "DECLARATION",
            "VOTING": "VOTE",
            "ELIMINATE_ALL_VOTE": "ELIMINATE_ALL_VOTE",
            "NIGHT_KILL": "KILL",
            "NIGHT_DON": "DON_CHECK",
            "NIGHT_SHERIFF": "SHERIFF_CHECK"
        }
        
        action = {"type": action_type_map.get(phase, phase)}
        
        # Example of handling different phases
        if phase == "DECLARATION":
            # Create a random declaration
            action["declaration"] = [random.randint(-3, 3) for _ in range(10)]
            
            # Add random sheriff claims
            sheriff_claims = []
            for _ in range(random.randint(0, 2)):
                claim = [0] * 10
                claim[random.randint(0, 9)] = random.choice([-1, 1])
                sheriff_claims.append(claim)
            action["sheriff_claims"] = sheriff_claims
            
            # Add a random nomination policy
            if "nomination" in valid_actions and valid_actions["nomination"]:
                nominees = valid_actions["nomination"]
                if len(nominees) > 1:  # Skip -1 (no nomination)
                    nomination_policy = {}
                    for nominee in nominees[1:]:  # Skip -1
                        nomination_policy[str(nominee)] = random.random()
                    # Normalize probabilities
                    total = sum(nomination_policy.values())
                    if total > 0:
                        for k in nomination_policy:
                            nomination_policy[k] /= total
                        action["nomination_policy"] = nomination_policy
        
        elif phase == "VOTING":
            if "vote" in valid_actions and valid_actions["vote"]:
                action["target"] = random.choice(valid_actions["vote"])
        
        elif phase == "ELIMINATE_ALL_VOTE":
            action["vote"] = random.choice([True, False])
        
        elif phase == "NIGHT_KILL":
            if "kill" in valid_actions and valid_actions["kill"]:
                action["target"] = random.choice(valid_actions["kill"])
        
        elif phase == "NIGHT_DON":
            if "don_check" in valid_actions and valid_actions["don_check"]:
                action["target"] = random.choice(valid_actions["don_check"])
        
        elif phase == "NIGHT_SHERIFF":
            if "sheriff_check" in valid_actions and valid_actions["sheriff_check"]:
                action["target"] = random.choice(valid_actions["sheriff_check"])
        
        return action
    
    # Create a client with a simple random action callback
    client = MafiaClient(action_callback=sample_action_callback)
    
    # Connect to the server
    if client.connect():
        logger.info("Connected to server!")
        logger.info("Press Ctrl+C to disconnect")
        try:
            # Keep the main thread running
            while client.is_connected:
                pass
        except KeyboardInterrupt:
            # Disconnect on Ctrl+C
            client.disconnect()
