import unittest
import random
import numpy as np
from mafia_server.sheriff_policy import SheriffPolicy

class TestSheriffPolicy(unittest.TestCase):
    """Test the SheriffPolicy class for consistency and functionality"""
    
    def setUp(self):
        # Fixed seed for reproducible tests
        random.seed(42)
        np.random.seed(42)
        
        # Create a player as sheriff
        self.player_id = 0
        
        # Valid targets are all other players
        self.valid_targets = list(range(1, 10))
    
    def test_basic_policy_creation(self):
        """Test creation of a basic sheriff policy"""
        # Create a policy for day 1
        policy = SheriffPolicy(self.player_id, 1)
        
        # Set up simple probabilities
        policy.set_claim_sheriff_prob(1, 1.0)  # 100% chance to claim sheriff
        
        # Set up check reveal probabilities for day 0
        # Will reveal checks for players 1 and 2 with 100% probability
        policy.set_check_reveal_prob(1, 0, {1: 1.0, 2: 1.0})
        
        # Set check result probabilities
        # Always claim player 1 is RED team
        # Always claim player 2 is BLACK team
        policy.set_check_result_prob(0, 1, {"RED": 1.0, "BLACK": 0.0})
        policy.set_check_result_prob(0, 2, {"RED": 0.0, "BLACK": 1.0})
        
        # Sample claims
        claims_matrix = policy.sample_sheriff_claims()
        
        # Check that the claims match our expectations
        self.assertEqual(claims_matrix[0][1], 1)  # Player 1 claimed RED
        self.assertEqual(claims_matrix[0][2], -1)  # Player 2 claimed BLACK
    
    def test_claim_consistency_across_days(self):
        """Test that claims remain consistent across multiple days"""
        # Day 1 - First reveal some checks
        day1_policy = SheriffPolicy(self.player_id, 1)
        day1_policy.set_claim_sheriff_prob(1, 1.0)
        day1_policy.set_check_reveal_prob(1, 0, {1: 1.0, 3: 1.0})
        day1_policy.set_check_result_prob(0, 1, {"RED": 1.0, "BLACK": 0.0})
        day1_policy.set_check_result_prob(0, 3, {"RED": 0.0, "BLACK": 1.0})
        
        day1_claims = day1_policy.sample_sheriff_claims()
        
        # Verify day 1 claims
        self.assertEqual(day1_claims[0][1], 1)  # Player 1 claimed RED
        self.assertEqual(day1_claims[0][3], -1)  # Player 3 claimed BLACK
        
        # Extract past claims for continuity
        past_claims = day1_policy.past_claims
        
        # Day 2 - Add new checks while maintaining consistency with day 1
        day2_policy = SheriffPolicy(self.player_id, 2)
        day2_policy.set_claim_sheriff_prob(2, 1.0)
        
        # Set past claims from day 1 to maintain consistency
        day2_policy.past_claims = past_claims
        
        # In day 2, reveal the old checks again plus a new check for player 5
        day2_policy.set_check_reveal_prob(2, 0, {1: 1.0, 3: 1.0})  # Reveal day 0 checks again
        day2_policy.set_check_reveal_prob(2, 1, {5: 1.0})  # New check from day 1
        
        # Set result for the new check
        day2_policy.set_check_result_prob(1, 5, {"RED": 0.3, "BLACK": 0.7})  # Probably BLACK
        
        day2_claims = day2_policy.sample_sheriff_claims()
        
        # Verify day 2 claims
        # Check that day 0 results are consistent with day 1 claims
        self.assertEqual(day2_claims[0][1], 1)  # Player 1 still claimed RED 
        self.assertEqual(day2_claims[0][3], -1)  # Player 3 still claimed BLACK
        
        # Check that the new claim for day 1 was generated
        self.assertIn(day2_claims[1][5], [1, -1])  # Either RED or BLACK
        
        # Verify that the day 1 result for player 5 is now in past_claims
        self.assertIn(1, day2_policy.past_claims)
        self.assertIn(5, day2_policy.past_claims[1])
    
    def test_random_policy(self):
        """Test creation of random policies"""
        # Create random policies for several days 
        for day in range(1, 5):
            policy = SheriffPolicy.create_random_policy(self.player_id, day, list(range(10)))
            
            # Verify claim probability increases with day
            if day > 1:
                self.assertIn(day, policy.claim_sheriff_prob)
                self.assertLessEqual(policy.claim_sheriff_prob[day], 0.8)  # Max 80% as per implementation
            
            # Sample claims and verify structure
            claims = policy.sample_sheriff_claims()
            
            # Verify we get a 10x10 matrix
            self.assertEqual(len(claims), 10)
            for row in claims:
                self.assertEqual(len(row), 10)
                
                # Verify values are in {-1, 0, 1}
                for value in row:
                    self.assertIn(value, [-1, 0, 1])
    
    def test_serialization(self):
        """Test that policies can be serialized and deserialized"""
        # Create a policy
        original = SheriffPolicy.create_random_policy(self.player_id, 2, list(range(10)))
        
        # Add some past claims
        original.record_claim(0, 1, "RED")
        original.record_claim(0, 3, "BLACK")
        
        # Convert to dictionary
        policy_dict = original.to_dict()
        
        # Convert back to policy
        reconstructed = SheriffPolicy.from_dict(policy_dict)
        
        # Verify key attributes
        self.assertEqual(reconstructed.player_id, original.player_id)
        self.assertEqual(reconstructed.current_day, original.current_day)
        self.assertEqual(reconstructed.past_claims, original.past_claims)
        
        # Sample claims from both and compare structure
        original_claims = original.sample_sheriff_claims()
        reconstructed_claims = reconstructed.sample_sheriff_claims()
        
        # Same dimensions
        self.assertEqual(len(original_claims), len(reconstructed_claims))
        for i in range(len(original_claims)):
            self.assertEqual(len(original_claims[i]), len(reconstructed_claims[i]))


if __name__ == "__main__":
    unittest.main()
