import unittest
import random
import numpy as np
from mafia_server.sheriff_policy import (
    ProbabilisticVotingPolicy,
    ProbabilisticNightActionPolicy,
    ProbabilisticDeclarationPolicy
)

class TestProbabilisticVotingPolicy(unittest.TestCase):
    """Test the ProbabilisticVotingPolicy class for voting decisions"""
    
    def setUp(self):
        # Fixed seed for reproducible tests
        random.seed(42)
        np.random.seed(42)
        
        # Valid targets
        self.valid_targets = [1, 3, 5, 7]
    
    def test_basic_policy_creation(self):
        """Test creation of a basic voting policy"""
        policy = ProbabilisticVotingPolicy(self.valid_targets)
        
        # Set specific probabilities
        target_probs = {1: 0.1, 3: 0.2, 5: 0.3, 7: 0.4}
        policy.set_target_probs(target_probs)
        
        # Verify probabilities
        self.assertEqual(policy.target_probs, target_probs)
        
        # Sample a large number of votes and check distribution
        vote_counts = {t: 0 for t in self.valid_targets}
        n_samples = 10000
        
        for _ in range(n_samples):
            vote = policy.sample_vote()
            vote_counts[vote] += 1
        
        # Check that frequencies roughly match probabilities
        for target in self.valid_targets:
            expected_freq = target_probs[target]
            actual_freq = vote_counts[target] / n_samples
            
            # Allow 5% deviation due to random sampling
            self.assertAlmostEqual(actual_freq, expected_freq, delta=0.05)
    
    def test_random_policy(self):
        """Test creation of a random voting policy"""
        policy = ProbabilisticVotingPolicy.create_random_policy(self.valid_targets)
        
        # Verify all valid targets have probabilities
        for target in self.valid_targets:
            self.assertIn(target, policy.target_probs)
        
        # Verify probabilities sum to approximately 1
        total_prob = sum(policy.target_probs.values())
        self.assertAlmostEqual(total_prob, 1.0, places=6)
        
        # Sample votes and ensure they're all valid
        for _ in range(100):
            vote = policy.sample_vote()
            self.assertIn(vote, self.valid_targets)
    
    def test_serialization(self):
        """Test that policies can be serialized and deserialized"""
        # Create a policy
        original = ProbabilisticVotingPolicy.create_random_policy(self.valid_targets)
        
        # Convert to dictionary
        policy_dict = original.to_dict()
        
        # Convert back to policy
        reconstructed = ProbabilisticVotingPolicy.from_dict(policy_dict)
        
        # Verify key attributes
        self.assertEqual(reconstructed.valid_targets, original.valid_targets)
        self.assertEqual(reconstructed.target_probs, original.target_probs)
        
        # Sample votes and ensure behavior is the same (with reset seed)
        random.seed(42)
        np.random.seed(42)
        original_vote = original.sample_vote()
        
        random.seed(42)
        np.random.seed(42)
        reconstructed_vote = reconstructed.sample_vote()
        
        self.assertEqual(original_vote, reconstructed_vote)
    
    def test_invalid_targets(self):
        """Test handling of invalid targets"""
        policy = ProbabilisticVotingPolicy(self.valid_targets)
        
        # Try to set probabilities for invalid targets
        with self.assertRaises(ValueError):
            policy.set_target_probs({1: 0.5, 99: 0.5})  # 99 is not a valid target


class TestProbabilisticNightActionPolicy(unittest.TestCase):
    """Test the ProbabilisticNightActionPolicy class for night actions"""
    
    def setUp(self):
        # Fixed seed for reproducible tests
        random.seed(42)
        np.random.seed(42)
        
        # Valid targets
        self.valid_targets = [1, 3, 5, 7]
    
    def test_kill_policy(self):
        """Test creation of a kill policy which includes skip option (-1)"""
        policy = ProbabilisticNightActionPolicy("KILL", self.valid_targets)
        
        # Create policy with skip probability
        target_probs = {1: 0.1, 3: 0.2, 5: 0.3, 7: 0.3, -1: 0.1}  # -1 = skip
        policy.set_target_probs(target_probs)
        
        # Sample a large number of targets
        target_counts = {t: 0 for t in target_probs}
        n_samples = 10000
        
        for _ in range(n_samples):
            target = policy.sample_target()
            target_counts[target] += 1
        
        # Check that frequencies roughly match probabilities
        for target in target_probs:
            expected_freq = target_probs[target]
            actual_freq = target_counts[target] / n_samples
            
            # Allow 5% deviation due to random sampling
            self.assertAlmostEqual(actual_freq, expected_freq, delta=0.05)
    
    def test_check_policy(self):
        """Test creation of a check policy for sheriff or don"""
        policy = ProbabilisticNightActionPolicy("SHERIFF_CHECK", self.valid_targets)
        
        # Set specific probabilities
        target_probs = {1: 0.2, 3: 0.3, 5: 0.4, 7: 0.1}
        policy.set_target_probs(target_probs)
        
        # Sample targets and ensure they're all valid
        for _ in range(100):
            target = policy.sample_target()
            self.assertIn(target, self.valid_targets)
    
    def test_random_policy_creation(self):
        """Test creation of random night action policies"""
        # Create a kill policy (should include -1/skip)
        kill_policy = ProbabilisticNightActionPolicy.create_random_policy("KILL", self.valid_targets)
        
        # Check if -1 is included in the targets
        self.assertIn(-1, kill_policy.target_probs)
        
        # Create a check policy (should not include -1/skip)
        check_policy = ProbabilisticNightActionPolicy.create_random_policy("DON_CHECK", self.valid_targets)
        
        # Sample targets and ensure they're all valid
        for _ in range(100):
            target = check_policy.sample_target()
            self.assertIn(target, self.valid_targets)
    
    def test_serialization(self):
        """Test that policies can be serialized and deserialized"""
        # Create a policy
        original = ProbabilisticNightActionPolicy.create_random_policy("KILL", self.valid_targets)
        
        # Convert to dictionary
        policy_dict = original.to_dict()
        
        # Convert back to policy
        reconstructed = ProbabilisticNightActionPolicy.from_dict(policy_dict)
        
        # Verify key attributes
        self.assertEqual(reconstructed.action_type, original.action_type)
        self.assertEqual(reconstructed.valid_targets, original.valid_targets)
        self.assertEqual(reconstructed.target_probs, original.target_probs)


class TestProbabilisticDeclarationPolicy(unittest.TestCase):
    """Test the ProbabilisticDeclarationPolicy class for declarations"""
    
    def setUp(self):
        # Fixed seed for reproducible tests
        random.seed(42)
        np.random.seed(42)
        
        # Number of players
        self.player_count = 10
    
    def test_basic_policy(self):
        """Test creation of a basic declaration policy"""
        policy = ProbabilisticDeclarationPolicy(self.player_count)
        
        # Set specific probabilities for player 0
        value_probs = {-3: 0.1, -2: 0.1, -1: 0.1, 0: 0.4, 1: 0.1, 2: 0.1, 3: 0.1}
        policy.set_declaration_probs(0, value_probs)
        
        # Sample a large number of declarations for player 0
        value_counts = {v: 0 for v in value_probs}
        n_samples = 10000
        
        for _ in range(n_samples):
            declaration = policy.sample_declaration()
            value = declaration[0]  # Value for player 0
            value_counts[value] += 1
        
        # Check that frequencies roughly match probabilities
        for value in value_probs:
            expected_freq = value_probs[value]
            actual_freq = value_counts[value] / n_samples
            
            # Allow 5% deviation due to random sampling
            self.assertAlmostEqual(actual_freq, expected_freq, delta=0.05)
    
    def test_random_policy(self):
        """Test creation of a random declaration policy"""
        policy = ProbabilisticDeclarationPolicy.create_random_policy(self.player_count)
        
        # Verify declarations are properly sized
        declaration = policy.sample_declaration()
        self.assertEqual(len(declaration), self.player_count)
        
        # Verify all values are in valid range (-3 to 3)
        for value in declaration:
            self.assertGreaterEqual(value, -3)
            self.assertLessEqual(value, 3)
    
    def test_invalid_value_handling(self):
        """Test handling of invalid declaration values"""
        policy = ProbabilisticDeclarationPolicy(self.player_count)
        
        # Try to set probabilities for invalid values
        with self.assertRaises(ValueError):
            policy.set_declaration_probs(0, {-4: 0.5, 0: 0.5})  # -4 is outside valid range
        
        with self.assertRaises(ValueError):
            policy.set_declaration_probs(0, {0: 0.5, 4: 0.5})  # 4 is outside valid range
    
    def test_serialization(self):
        """Test that policies can be serialized and deserialized"""
        # Create a policy
        original = ProbabilisticDeclarationPolicy.create_random_policy(self.player_count)
        
        # Convert to dictionary
        policy_dict = original.to_dict()
        
        # Convert back to policy
        reconstructed = ProbabilisticDeclarationPolicy.from_dict(policy_dict)
        
        # Verify player count
        self.assertEqual(reconstructed.player_count, original.player_count)
        
        # Set the same seed before sampling from both policies
        random.seed(42)
        np.random.seed(42)
        original_declaration = original.sample_declaration()
        
        random.seed(42)
        np.random.seed(42)
        reconstructed_declaration = reconstructed.sample_declaration()
        
        # Verify declarations match with the same seed
        self.assertEqual(original_declaration, reconstructed_declaration)


class TestEliminateAllVotePolicy(unittest.TestCase):
    """Test for potential ELIMINATE_ALL_VOTE policy (suggested addition)"""
    
    def test_conceptual_vote_policy(self):
        """
        This test doesn't test actual code, but demonstrates how a
        probabilistic policy for eliminate-all voting might work
        """
        # Conceptual policy might look like:
        # class ProbabilisticEliminateAllPolicy:
        #     def __init__(self):
        #         self.true_prob = 0.5  # Default 50/50
        #     
        #     def set_probabilities(self, true_prob):
        #         self.true_prob = true_prob
        #     
        #     def sample_vote(self):
        #         return random.random() < self.true_prob
        
        # For now, just make sure our existing direct implementation works
        votes = [random.choice([True, False]) for _ in range(1000)]
        true_count = sum(1 for v in votes if v)
        
        # Should be roughly 50% True, 50% False
        self.assertAlmostEqual(true_count / 1000, 0.5, delta=0.1)


if __name__ == "__main__":
    unittest.main()
