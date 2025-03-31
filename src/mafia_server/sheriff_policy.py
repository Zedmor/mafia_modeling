from typing import Dict, List, Optional, Tuple, Union, Any
import random
import numpy as np

class SheriffPolicy:
    """
    A more sophisticated representation of sheriff claims and strategies.
    
    This class allows for complex sheriff strategies such as:
    - Deciding whether to claim sheriff at all on a given day
    - Revealing historical checks from previous days
    - Maintaining consistency with previous claims
    - Strategically lying about checks
    """
    
    def __init__(self, player_id: int, day: int):
        self.player_id = player_id
        self.current_day = day
        
        # Master claim strategy - whether to claim sheriff at all
        # Format: {day: probability_of_claiming}
        self.claim_sheriff_prob = {}
        
        # Check reveal strategy - which checks to reveal on which day
        # Format: {day_of_claim: {day_of_check: {target: probability}}}
        self.check_reveal_prob = {}
        
        # Check result strategy - what results to claim for each check
        # Format: {day_of_check: {target: {"RED": prob_red, "BLACK": prob_black}}}
        self.check_result_prob = {}
        
        # Specific check claims already made (for consistency tracking)
        # Format: {day_of_check: {target: claimed_result}}
        self.past_claims = {}

    def set_claim_sheriff_prob(self, day: int, probability: float):
        """Set probability of claiming to be sheriff on a given day"""
        self.claim_sheriff_prob[day] = probability
    
    def set_check_reveal_prob(self, day_of_claim: int, day_of_check: int, 
                             target_probs: Dict[int, float]):
        """
        Set probability of revealing checks from day_of_check on day_of_claim
        
        Args:
            day_of_claim: The day on which to make the claim
            day_of_check: The day the check was performed
            target_probs: Dictionary mapping target_id to probability of revealing that check
        """
        if day_of_claim not in self.check_reveal_prob:
            self.check_reveal_prob[day_of_claim] = {}
            
        if day_of_check not in self.check_reveal_prob[day_of_claim]:
            self.check_reveal_prob[day_of_claim][day_of_check] = {}
            
        self.check_reveal_prob[day_of_claim][day_of_check] = target_probs
    
    def set_check_result_prob(self, day_of_check: int, target: int, 
                             result_probs: Dict[str, float]):
        """
        Set probability of claiming specific results for a check
        
        Args:
            day_of_check: The day the check was performed
            target: The target player ID
            result_probs: Dictionary mapping result ("RED", "BLACK") to probability
        """
        if day_of_check not in self.check_result_prob:
            self.check_result_prob[day_of_check] = {}
            
        self.check_result_prob[day_of_check][target] = result_probs
    
    def record_claim(self, day_of_check: int, target: int, claimed_result: str):
        """
        Record a claim that was actually made to maintain consistency
        
        Args:
            day_of_check: The day the check was claimed to be performed
            target: The target player ID
            claimed_result: The result that was claimed ("RED" or "BLACK")
        """
        if day_of_check not in self.past_claims:
            self.past_claims[day_of_check] = {}
            
        self.past_claims[day_of_check][target] = claimed_result
    
    def sample_sheriff_claims(self) -> List[List[int]]:
        """
        Sample from the policy to generate concrete sheriff claims
        
        Returns:
            A 10x10 matrix suitable for the current API format
        """
        # Initialize empty claims matrix (10x10)
        claims_matrix = [[0] * 10 for _ in range(10)]
        
        # Decide whether to claim sheriff today
        if self.current_day in self.claim_sheriff_prob:
            claim_prob = self.claim_sheriff_prob[self.current_day]
            claim_sheriff = random.random() < claim_prob
            
            if claim_sheriff:
                # For each previous day, decide which checks to reveal
                for day_of_check in range(self.current_day):
                    if self.current_day in self.check_reveal_prob and day_of_check in self.check_reveal_prob[self.current_day]:
                        target_probs = self.check_reveal_prob[self.current_day][day_of_check]
                        
                        for target, prob in target_probs.items():
                            if random.random() < prob:
                                # Decide claimed result (RED or BLACK)
                                # Check if this check was claimed before for consistency
                                if day_of_check in self.past_claims and target in self.past_claims[day_of_check]:
                                    # Use past claim for consistency
                                    claimed_result = self.past_claims[day_of_check][target]
                                    result_value = 1 if claimed_result == "RED" else -1
                                else:
                                    # Sample new result
                                    result_probs = self.check_result_prob.get(day_of_check, {}).get(target, {"RED": 0.5, "BLACK": 0.5})
                                    if random.random() < result_probs.get("RED", 0.5):
                                        result_value = 1  # RED
                                        self.record_claim(day_of_check, target, "RED")
                                    else:
                                        result_value = -1  # BLACK
                                        self.record_claim(day_of_check, target, "BLACK")
                                
                                # Set the claim in the matrix
                                claims_matrix[day_of_check][target] = result_value
        
        return claims_matrix
    
    @classmethod
    def create_random_policy(cls, player_id: int, day: int, valid_targets: List[int]) -> 'SheriffPolicy':
        """
        Create a random sheriff policy for testing or baseline
        
        Args:
            player_id: The player's ID
            day: The current day
            valid_targets: List of valid target player IDs
            
        Returns:
            A random sheriff policy
        """
        policy = cls(player_id, day)
        
        # Random probability of claiming sheriff today (higher probability as game progresses)
        claim_prob = min(0.2 * day, 0.8)  # Increases by day but caps at 80%
        policy.set_claim_sheriff_prob(day, claim_prob)
        
        # For each previous day, random probability of revealing checks
        for prev_day in range(day):
            target_probs = {}
            for target in valid_targets:
                if target != player_id:  # Can't check yourself
                    target_probs[target] = random.random() * 0.5  # 0-50% chance of revealing
            
            policy.set_check_reveal_prob(day, prev_day, target_probs)
            
            # Random result probabilities for each target
            for target in valid_targets:
                if target != player_id:
                    policy.set_check_result_prob(prev_day, target, {
                        "RED": random.random(),
                        "BLACK": random.random()
                    })
        
        return policy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the policy to a dictionary for serialization"""
        return {
            "player_id": self.player_id,
            "current_day": self.current_day,
            "claim_sheriff_prob": self.claim_sheriff_prob,
            "check_reveal_prob": self.check_reveal_prob,
            "check_result_prob": self.check_result_prob,
            "past_claims": self.past_claims
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SheriffPolicy':
        """Create a policy from a dictionary"""
        policy = cls(data["player_id"], data["current_day"])
        policy.claim_sheriff_prob = data["claim_sheriff_prob"]
        policy.check_reveal_prob = data["check_reveal_prob"] 
        policy.check_result_prob = data["check_result_prob"]
        policy.past_claims = data["past_claims"]
        return policy


class ProbabilisticVotingPolicy:
    """
    Represents a probabilistic voting policy.
    """
    
    def __init__(self, valid_targets: List[int]):
        """
        Initialize a voting policy
        
        Args:
            valid_targets: List of valid target player IDs
        """
        self.valid_targets = valid_targets
        self.target_probs = {}
    
    def set_target_probs(self, target_probs: Dict[int, float]):
        """
        Set voting probabilities for each target
        
        Args:
            target_probs: Dictionary mapping target_id to probability
        """
        # Validate targets
        for target in target_probs:
            if target not in self.valid_targets:
                raise ValueError(f"Invalid target: {target}")
                
        # Normalize probabilities
        total = sum(target_probs.values())
        if total > 0:
            self.target_probs = {t: p/total for t, p in target_probs.items()}
        else:
            self.target_probs = {}
    
    def sample_vote(self) -> Optional[int]:
        """
        Sample from the policy to get a concrete vote
        
        Returns:
            The chosen target player ID, or None if no valid vote
        """
        if not self.target_probs:
            return None
            
        targets = list(self.target_probs.keys())
        probabilities = list(self.target_probs.values())
        
        return int(np.random.choice(targets, p=probabilities))
    
    @classmethod
    def create_random_policy(cls, valid_targets: List[int]) -> 'ProbabilisticVotingPolicy':
        """
        Create a random voting policy
        
        Args:
            valid_targets: List of valid target player IDs
            
        Returns:
            A random voting policy
        """
        policy = cls(valid_targets)
        
        # Assign random probabilities to each target
        target_probs = {}
        for target in valid_targets:
            target_probs[target] = random.random()
            
        # Normalize probabilities
        total = sum(target_probs.values())
        if total > 0:
            target_probs = {t: p/total for t, p in target_probs.items()}
            
        policy.set_target_probs(target_probs)
        return policy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the policy to a dictionary for serialization"""
        return {
            "valid_targets": self.valid_targets,
            "target_probs": self.target_probs
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProbabilisticVotingPolicy':
        """Create a policy from a dictionary"""
        policy = cls(data["valid_targets"])
        policy.target_probs = data["target_probs"]
        return policy


class ProbabilisticNightActionPolicy:
    """
    Represents a probabilistic policy for night actions (kill, checks)
    """
    
    def __init__(self, action_type: str, valid_targets: List[int]):
        """
        Initialize a night action policy
        
        Args:
            action_type: Type of action ("KILL", "DON_CHECK", "SHERIFF_CHECK")
            valid_targets: List of valid target player IDs
        """
        self.action_type = action_type
        self.valid_targets = valid_targets
        self.target_probs = {}
    
    def set_target_probs(self, target_probs: Dict[int, float]):
        """
        Set action probabilities for each target
        
        Args:
            target_probs: Dictionary mapping target_id to probability
        """
        # Validate targets
        for target in target_probs:
            if target not in self.valid_targets and target != -1:  # -1 is valid for skip
                raise ValueError(f"Invalid target: {target}")
                
        # Normalize probabilities
        total = sum(target_probs.values())
        if total > 0:
            self.target_probs = {t: p/total for t, p in target_probs.items()}
        else:
            self.target_probs = {}
    
    def sample_target(self) -> Optional[int]:
        """
        Sample from the policy to get a concrete target
        
        Returns:
            The chosen target player ID, or None if no valid target
        """
        if not self.target_probs:
            return None
            
        targets = list(self.target_probs.keys())
        probabilities = list(self.target_probs.values())
        
        return int(np.random.choice(targets, p=probabilities))
    
    @classmethod
    def create_random_policy(cls, action_type: str, valid_targets: List[int]) -> 'ProbabilisticNightActionPolicy':
        """
        Create a random night action policy
        
        Args:
            action_type: Type of action
            valid_targets: List of valid target player IDs
            
        Returns:
            A random night action policy
        """
        policy = cls(action_type, valid_targets)
        
        # Maybe add -1 (skip) for kill actions
        if action_type == "KILL" and -1 not in valid_targets:
            valid_targets = valid_targets + [-1]
        
        # Assign random probabilities to each target
        target_probs = {}
        for target in valid_targets:
            target_probs[target] = random.random()
            
        # Normalize probabilities
        total = sum(target_probs.values())
        if total > 0:
            target_probs = {t: p/total for t, p in target_probs.items()}
            
        policy.set_target_probs(target_probs)
        return policy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the policy to a dictionary for serialization"""
        return {
            "action_type": self.action_type,
            "valid_targets": self.valid_targets,
            "target_probs": self.target_probs
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProbabilisticNightActionPolicy':
        """Create a policy from a dictionary"""
        policy = cls(data["action_type"], data["valid_targets"])
        policy.target_probs = data["target_probs"]
        return policy


class ProbabilisticDeclarationPolicy:
    """
    Represents a probabilistic declaration policy.
    """
    
    def __init__(self, player_count: int):
        """
        Initialize a declaration policy
        
        Args:
            player_count: Number of players in the game
        """
        self.player_count = player_count
        
        # For each player position, probability of each declaration value (-3 to 3)
        # Format: {player_id: {-3: p1, -2: p2, -1: p3, 0: p4, 1: p5, 2: p6, 3: p7}}
        self.declaration_probs = {}
        
        # Initialize with uniform distribution for each player
        values = list(range(-3, 4))  # -3 to 3
        uniform_prob = 1.0 / len(values)
        
        for i in range(player_count):
            self.declaration_probs[i] = {v: uniform_prob for v in values}
    
    def set_declaration_probs(self, player_id: int, value_probs: Dict[int, float]):
        """
        Set declaration probabilities for a specific player
        
        Args:
            player_id: The player to declare about
            value_probs: Dictionary mapping declaration value (-3 to 3) to probability
        """
        # Validate values
        for value in value_probs:
            if value < -3 or value > 3:
                raise ValueError(f"Invalid declaration value: {value}")
                
        # Normalize probabilities
        total = sum(value_probs.values())
        if total > 0:
            self.declaration_probs[player_id] = {v: p/total for v, p in value_probs.items()}
    
    def sample_declaration(self) -> List[int]:
        """
        Sample from the policy to get a concrete declaration vector
        
        Returns:
            A list of declaration values for each player
        """
        declaration = [0] * self.player_count
        
        for player_id in range(self.player_count):
            if player_id in self.declaration_probs:
                values = list(self.declaration_probs[player_id].keys())
                probabilities = list(self.declaration_probs[player_id].values())
                
                declaration[player_id] = int(np.random.choice(values, p=probabilities))
        
        return declaration
    
    @classmethod
    def create_random_policy(cls, player_count: int) -> 'ProbabilisticDeclarationPolicy':
        """
        Create a random declaration policy
        
        Args:
            player_count: Number of players in the game
            
        Returns:
            A random declaration policy
        """
        policy = cls(player_count)
        
        for player_id in range(player_count):
            # Generate random weights for each value
            values = list(range(-3, 4))  # -3 to 3
            weights = [random.random() for _ in values]
            
            # Normalize to probabilities
            total = sum(weights)
            probs = {v: w/total for v, w in zip(values, weights)}
            
            policy.set_declaration_probs(player_id, probs)
        
        return policy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the policy to a dictionary for serialization"""
        # Convert player_id keys to strings for JSON compatibility
        declaration_probs_str = {str(k): v for k, v in self.declaration_probs.items()}
        
        return {
            "player_count": self.player_count,
            "declaration_probs": declaration_probs_str
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProbabilisticDeclarationPolicy':
        """Create a policy from a dictionary"""
        policy = cls(data["player_count"])
        
        # Convert keys back to integers
        declaration_probs = {int(k): v for k, v in data["declaration_probs"].items()}
        policy.declaration_probs = declaration_probs
        
        return policy


class ProbabilisticEliminateAllPolicy:
    """
    Represents a probabilistic policy for eliminate-all voting.
    
    This policy determines the probability of voting to eliminate all 
    tied players versus keeping them in the game.
    """
    
    def __init__(self):
        """Initialize an eliminate-all voting policy with default 50/50 probability"""
        self.true_prob = 0.5  # Default 50% chance of voting to eliminate
    
    def set_true_probability(self, prob: float):
        """
        Set the probability of voting to eliminate all tied players
        
        Args:
            prob: Probability between 0 and 1 of voting True
        """
        if prob < 0 or prob > 1:
            raise ValueError("Probability must be between 0 and 1")
        self.true_prob = prob
    
    def sample_vote(self) -> bool:
        """
        Sample from the policy to get a concrete vote
        
        Returns:
            Boolean indicating whether to eliminate all tied players
        """
        return random.random() < self.true_prob
    
    @classmethod
    def create_random_policy(cls) -> 'ProbabilisticEliminateAllPolicy':
        """
        Create a random eliminate-all voting policy
        
        Returns:
            A random eliminate-all voting policy
        """
        policy = cls()
        policy.set_true_probability(random.random())  # Random probability between 0 and 1
        return policy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the policy to a dictionary for serialization"""
        return {
            "true_prob": self.true_prob
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProbabilisticEliminateAllPolicy':
        """Create a policy from a dictionary"""
        policy = cls()
        policy.true_prob = data["true_prob"]
        return policy


# Example usage
if __name__ == "__main__":
    # Create a random sheriff policy
    sheriff_policy = SheriffPolicy.create_random_policy(0, 3, list(range(10)))
    
    # Sample sheriff claims from the policy
    claims_matrix = sheriff_policy.sample_sheriff_claims()
    
    # Print the claims
    for i, row in enumerate(claims_matrix):
        if any(row):
            print(f"Day {i} checks: {row}")
