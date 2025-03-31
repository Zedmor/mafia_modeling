import random
import logging
import numpy as np
from typing import Dict, Any, Optional, List

from mafia_server.client import MafiaClient
from mafia_server.sheriff_policy import (
    SheriffPolicy, 
    ProbabilisticVotingPolicy, 
    ProbabilisticNightActionPolicy,
    ProbabilisticDeclarationPolicy,
    ProbabilisticEliminateAllPolicy
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RandomAgent")


class RandomAgent:
    """
    Random agent implementation for Mafia game.
    
    This agent makes completely random but valid decisions in the game,
    which is useful for testing the game flow and validating state transitions.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765, agent_id: Optional[int] = None, 
                 verbose: bool = False):
        """
        Initialize the random agent
        
        Args:
            host: Host address of the server
            port: Port of the server
            agent_id: Optional identifier for the agent
            verbose: Whether to log detailed action information
        """
        self.host = host
        self.port = port
        self.agent_id = agent_id  # Just for logging, not used in game logic
        self.verbose = verbose
        self.client = MafiaClient(host=host, port=port, action_callback=self._action_callback)
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to the server and start responding to action requests"""
        self.connected = self.client.connect()
        return self.connected
    
    def disconnect(self):
        """Disconnect from the server"""
        if self.connected:
            self.client.disconnect()
            self.connected = False
    
    def _action_callback(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a random action based on the current game state and valid actions
        
        Args:
            message: Game state message from the server
        
        Returns:
            A valid random action to take
        """
        # If it's not our turn, do nothing
        if message["player_id"] != self.client.player_id:
            return None
        
        player_id = message["player_id"]
        phase = message["phase"]
        valid_actions = message["valid_actions"]
        # Handle messages that don't have an observation field (for backwards compatibility with tests)
        observation = message.get("observation", {"turn": 0, "alive_players": list(range(10))})
        
        if not valid_actions:
            if self.verbose:
                logger.info("No valid actions available")
            return None
        
        agent_name = f"RandomAgent{f'-{self.agent_id}' if self.agent_id is not None else ''}"
        
        # Check for eliminate-all voting phase by looking at valid_actions
        if "eliminate_all" in valid_actions:
            action = {"type": "ELIMINATE_ALL_VOTE"}
            action["vote"] = random.choice(valid_actions["eliminate_all"])
            if self.verbose:
                logger.info(f"{agent_name} eliminate-all vote: {action['vote']}")
            return action
            
        # Map other phase names to action types expected by the server
        action_type_map = {
            "DECLARATION": "DECLARATION",
            "VOTING": "VOTE",  # Server expects "VOTE", not "VOTING"
            "NIGHT_KILL": "KILL",  # Server expects "KILL", not "NIGHT_KILL"
            "NIGHT_DON": "DON_CHECK",
            "NIGHT_SHERIFF": "SHERIFF_CHECK"
        }
        
        action = {"type": action_type_map.get(phase, phase)}
        
        # Handle different phases
        if phase == "DECLARATION":
            # Create a probabilistic declaration policy
            declaration_policy = ProbabilisticDeclarationPolicy.create_random_policy(10)
            action["declaration"] = declaration_policy.sample_declaration()
            
            # Extract the turn from the observation
            current_turn = observation.get("turn", 0)
            
            # Create a sheriff policy
            sheriff_policy = SheriffPolicy.create_random_policy(
                player_id, 
                current_turn,
                list(range(10))
            )
            
            # Sample sheriff claims using our more advanced policy
            action["sheriff_claims"] = sheriff_policy.sample_sheriff_claims()
            
            # Add a probabilistic nomination policy
            if "nomination" in valid_actions and valid_actions["nomination"]:
                valid_nominations = []
                for nominee in valid_actions["nomination"]:
                    if nominee != -1:  # Skip -1 (no nomination)
                        valid_nominations.append(nominee)
                
                if valid_nominations:
                    # Create a probabilistic voting policy for nominations
                    nomination_policy_obj = ProbabilisticVotingPolicy.create_random_policy(valid_nominations)
                    
                    # Convert to the format expected by the server
                    nomination_policy = {}
                    for target, prob in nomination_policy_obj.target_probs.items():
                        nomination_policy[str(target)] = prob
                    
                    action["nomination_policy"] = nomination_policy
            
            # Format nomination policy for logging with 2 decimal places
            if self.verbose:
                log_nominations = {}
                for k, v in action.get('nomination_policy', {}).items():
                    log_nominations[k] = round(v, 2)
                logger.info(f"{agent_name} declared, nominations: {log_nominations}")
        
        elif phase == "VOTING":
            if "vote" in valid_actions and valid_actions["vote"]:
                # Create a probabilistic voting policy
                vote_policy = ProbabilisticVotingPolicy.create_random_policy(valid_actions["vote"])
                
                # Instead of returning a policy directly, we'll sample from it to get a concrete vote
                # This maintains compatibility with the current API
                target = vote_policy.sample_vote()
                action["target"] = target
                
                # But we could also return the full policy if the server API were extended:
                # action["vote_policy"] = {str(t): p for t, p in vote_policy.target_probs.items()}
                
                if self.verbose:
                    logger.info(f"{agent_name} voting for player {action['target']}")
        
        elif phase == "ELIMINATE_ALL_VOTE":
            if "eliminate_all" in valid_actions and valid_actions["eliminate_all"]:
                # Create a probabilistic eliminate-all voting policy
                eliminate_policy = ProbabilisticEliminateAllPolicy.create_random_policy()
                
                # Sample a vote from the policy
                action["vote"] = eliminate_policy.sample_vote()
                
                if self.verbose:
                    logger.info(f"{agent_name} eliminate-all vote: {action['vote']} (prob: {eliminate_policy.true_prob:.2f})")
        
        elif phase == "NIGHT_KILL":
            if "kill" in valid_actions and valid_actions["kill"]:
                # Create a probabilistic night action policy
                kill_policy = ProbabilisticNightActionPolicy.create_random_policy(
                    "KILL", valid_actions["kill"]
                )
                
                # Sample a target from the policy, but ensure it's a valid target
                # (avoid -1/skip which may not be supported in tests)
                target = kill_policy.sample_target()
                if target == -1 and valid_actions["kill"]:  # If -1 but we have valid targets
                    target = random.choice(valid_actions["kill"])  # Pick a random valid target instead
                
                action["target"] = target
                
                if self.verbose:
                    logger.info(f"{agent_name} killing player {action['target']}")
        
        elif phase == "NIGHT_DON":
            if "don_check" in valid_actions and valid_actions["don_check"]:
                # Create a probabilistic night action policy
                check_policy = ProbabilisticNightActionPolicy.create_random_policy(
                    "DON_CHECK", valid_actions["don_check"]
                )
                
                # Sample a target from the policy
                target = check_policy.sample_target()
                action["target"] = target
                
                if self.verbose:
                    logger.info(f"{agent_name} checking if player {action['target']} is sheriff")
        
        elif phase == "NIGHT_SHERIFF":
            if "sheriff_check" in valid_actions and valid_actions["sheriff_check"]:
                # Create a probabilistic night action policy
                check_policy = ProbabilisticNightActionPolicy.create_random_policy(
                    "SHERIFF_CHECK", valid_actions["sheriff_check"]
                )
                
                # Sample a target from the policy
                target = check_policy.sample_target()
                action["target"] = target
                
                if self.verbose:
                    logger.info(f"{agent_name} checking player {action['target']}'s team")
        
        return action


if __name__ == "__main__":
    # Example standalone usage
    agent = RandomAgent(verbose=True)
    if agent.connect():
        logger.info("Agent connected to server")
        try:
            # Keep the main thread running
            while agent.connected:
                pass
        except KeyboardInterrupt:
            # Disconnect on Ctrl+C
            agent.disconnect()
