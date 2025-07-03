"""
Deterministic Grounding Tests for Mafia Token Game.

These tests ensure that given the same seed and random_seed, 
the game produces exactly the same output every time.
This prevents regressions and validates deterministic behavior.
"""

import json
import os
import pytest
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from mafia_transformer.token_client_server_uat import TokenClientServerUAT


class TestDeterministicGrounding:
    """
    Grounding tests that validate deterministic game behavior.
    
    These tests create 'golden master' reference data for specific seed combinations
    and ensure all future runs produce identical results.
    """
    
    @pytest.fixture
    def test_data_dir(self):
        """Directory for storing golden master test data."""
        data_dir = Path("/home/zedmor/mafia_modeling/test/golden_master_data")
        data_dir.mkdir(exist_ok=True)
        return data_dir
    
    def get_control_file_path(self, test_data_dir: Path, seed: int, random_seed: int) -> Path:
        """Get the path to the control/golden master file for given seeds."""
        return test_data_dir / f"all_players_seed_{seed}_random_{random_seed}.json"
    
    def get_control_dir_path(self, test_data_dir: Path, seed: int, random_seed: int) -> Path:
        """Get the path to the control/golden master directory for given seeds."""
        return test_data_dir / f"seed_{seed}_random_{random_seed}"
    
    def get_test_data_dir_path(self, test_data_dir: Path, seed: int, random_seed: int) -> Path:
        """Get the path to the failing test data directory for given seeds."""
        return test_data_dir / f"test_data_seed_{seed}_random_{random_seed}"
    
    def run_uat_and_extract_data(self, seed: int, random_seed: int, test_data_dir: Path = None) -> Dict[str, Any]:
        """
        Run UAT with given seeds and extract the training data.
        
        Also copies complete UAT output to golden master directory for debugging.
        Returns the all_players data structure for comparison.
        """
        # Create temporary directory for UAT output
        with tempfile.TemporaryDirectory() as temp_dir:
            # Run UAT with specified seeds
            uat = TokenClientServerUAT(seed=seed, random_seed=random_seed, log_base_dir=temp_dir)
            log_dir = uat.run_complete_uat()
            
            # Extract training data
            training_data_dir = Path(log_dir) / "training_data"
            all_players_file = training_data_dir / f"all_players_seed_{seed}.json"
            
            if not all_players_file.exists():
                raise FileNotFoundError(f"Training data not generated: {all_players_file}")
            
            with open(all_players_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Copy complete UAT output to golden master directory if provided
            if test_data_dir:
                control_dir = self.get_control_dir_path(test_data_dir, seed, random_seed)
                self.copy_complete_uat_data(Path(log_dir), control_dir)
            
            return data
    
    def copy_complete_uat_data(self, source_dir: Path, dest_dir: Path):
        """Copy complete UAT output directory for debugging purposes."""
        # Remove existing directory if it exists
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        
        # Copy the entire UAT output directory
        shutil.copytree(source_dir, dest_dir)
        print(f"📁 Complete UAT data copied to: {dest_dir}")
        
        # List key files for verification
        key_files = [
            "CLIENT_SERVER_UAT_REPORT.md",
            "server.log", 
            "master_uat.log",
            "training_data/all_players_seed_*.json"
        ]
        
        print("📋 Available debug files:")
        for pattern in key_files:
            if '*' in pattern:
                # Handle glob patterns
                files = list(dest_dir.glob(pattern))
                for file in files:
                    print(f"   - {file.relative_to(dest_dir)}")
            else:
                file_path = dest_dir / pattern
                if file_path.exists():
                    print(f"   - {pattern}")
    
    def save_control_data(self, test_data_dir: Path, seed: int, random_seed: int, data: Dict[str, Any]):
        """Save control/golden master data for future comparisons."""
        control_file = self.get_control_file_path(test_data_dir, seed, random_seed)
        
        with open(control_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ Golden master data saved: {control_file}")
    
    def load_control_data(self, test_data_dir: Path, seed: int, random_seed: int) -> Dict[str, Any]:
        """Load control/golden master data for comparison."""
        control_file = self.get_control_file_path(test_data_dir, seed, random_seed)
        
        if not control_file.exists():
            return None
        
        with open(control_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def compare_game_data(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
        """
        Compare two game data structures and return list of differences.
        
        Returns empty list if identical, or list of difference descriptions.
        """
        differences = []
        
        # Compare metadata
        expected_meta = expected.get('metadata', {})
        actual_meta = actual.get('metadata', {})
        
        for key in ['seed', 'total_actions', 'num_players']:
            if expected_meta.get(key) != actual_meta.get(key):
                differences.append(f"Metadata {key}: expected {expected_meta.get(key)}, got {actual_meta.get(key)}")
        
        # Game result should be deterministic
        if expected_meta.get('game_result') != actual_meta.get('game_result'):
            differences.append(f"Game result: expected {expected_meta.get('game_result')}, got {actual_meta.get('game_result')}")
        
        # Compare player data
        expected_players = expected.get('players', {})
        actual_players = actual.get('players', {})
        
        if set(expected_players.keys()) != set(actual_players.keys()):
            differences.append(f"Player IDs differ: expected {sorted(expected_players.keys())}, got {sorted(actual_players.keys())}")
            return differences  # Can't continue comparison if player sets differ
        
        # Compare each player's token sequence
        for player_id in expected_players.keys():
            expected_player = expected_players[player_id]
            actual_player = actual_players[player_id]
            
            expected_sequence = expected_player.get('token_sequence', [])
            actual_sequence = actual_player.get('token_sequence', [])
            
            if expected_sequence != actual_sequence:
                differences.append(
                    f"Player {player_id} token sequence differs:\n"
                    f"  Expected length: {len(expected_sequence)}\n"
                    f"  Actual length: {len(actual_sequence)}\n"
                    f"  Expected: {expected_sequence[:20]}{'...' if len(expected_sequence) > 20 else ''}\n"
                    f"  Actual:   {actual_sequence[:20]}{'...' if len(actual_sequence) > 20 else ''}"
                )
                
                # Find first difference
                for i, (exp_token, act_token) in enumerate(zip(expected_sequence, actual_sequence)):
                    if exp_token != act_token:
                        differences.append(f"  First difference at index {i}: expected {exp_token}, got {act_token}")
                        break
        
        return differences
    
    def run_uat_for_regression_analysis(self, seed: int, random_seed: int, test_data_dir: Path) -> Dict[str, Any]:
        """
        Run UAT specifically for regression analysis, saving complete test data.
        
        Returns the test data and saves it to test_data_seed_X_random_Y directory.
        """
        # Create temporary directory for UAT output
        with tempfile.TemporaryDirectory() as temp_dir:
            # Run UAT with specified seeds
            uat = TokenClientServerUAT(seed=seed, random_seed=random_seed, log_base_dir=temp_dir)
            log_dir = uat.run_complete_uat()
            
            # Extract training data
            training_data_dir = Path(log_dir) / "training_data"
            all_players_file = training_data_dir / f"all_players_seed_{seed}.json"
            
            if not all_players_file.exists():
                raise FileNotFoundError(f"Training data not generated: {all_players_file}")
            
            with open(all_players_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Copy complete UAT output to test data directory for debugging
            test_data_dir_path = self.get_test_data_dir_path(test_data_dir, seed, random_seed)
            self.copy_complete_uat_data(Path(log_dir), test_data_dir_path)
            
            return data
    
    def generate_regression_diff_report(self, test_data_dir: Path, seed: int, random_seed: int, 
                                       control_data: Dict[str, Any], test_data: Dict[str, Any], 
                                       differences: List[str]):
        """
        Generate a comprehensive diff report for regression analysis.
        """
        test_data_dir_path = self.get_test_data_dir_path(test_data_dir, seed, random_seed)
        control_dir_path = self.get_control_dir_path(test_data_dir, seed, random_seed)
        
        # Create regression analysis report
        diff_report_path = test_data_dir_path / "REGRESSION_ANALYSIS.md"
        
        with open(diff_report_path, 'w', encoding='utf-8') as f:
            f.write("# 🚨 REGRESSION ANALYSIS REPORT\n\n")
            f.write(f"**Detected:** {datetime.now()}\n")
            f.write(f"**Seed:** {seed}\n")
            f.write(f"**Random Seed:** {random_seed}\n")
            f.write(f"**Total Differences:** {len(differences)}\n\n")
            
            f.write("## 📋 Summary\n\n")
            f.write("Deterministic behavior violation detected! The current implementation produces different\n")
            f.write("output compared to the golden master data, indicating a regression in game logic.\n\n")
            
            f.write("## 🔍 Detected Differences\n\n")
            for i, diff in enumerate(differences, 1):
                f.write(f"### {i}. {diff.split(':')[0] if ':' in diff else f'Difference {i}'}\n\n")
                f.write("```\n")
                f.write(diff)
                f.write("\n```\n\n")
            
            f.write("## 📁 Debug Data Locations\n\n")
            f.write(f"- **Golden Master Data:** `{control_dir_path.relative_to(test_data_dir)}/`\n")
            f.write(f"- **Failing Test Data:** `{test_data_dir_path.relative_to(test_data_dir)}/`\n")
            f.write(f"- **Golden Master Control File:** `all_players_seed_{seed}_random_{random_seed}.json`\n\n")
            
            f.write("## 🔧 Debug Process\n\n")
            f.write("1. **Compare Token Sequences:**\n")
            f.write("   ```bash\n")
            f.write(f"   diff {control_dir_path.relative_to(test_data_dir)}/training_data/all_players_seed_{seed}.json \\\n")
            f.write(f"        {test_data_dir_path.relative_to(test_data_dir)}/training_data/all_players_seed_{seed}.json\n")
            f.write("   ```\n\n")
            
            f.write("2. **Compare Server Logs:**\n")
            f.write("   ```bash\n")
            f.write(f"   diff {control_dir_path.relative_to(test_data_dir)}/server.log \\\n")
            f.write(f"        {test_data_dir_path.relative_to(test_data_dir)}/server.log\n")
            f.write("   ```\n\n")
            
            f.write("3. **Compare Player Token Traffic:**\n")
            f.write("   ```bash\n")
            f.write(f"   # Compare specific player's token sequences\n")
            f.write(f"   diff {control_dir_path.relative_to(test_data_dir)}/token_traffic_player_0.log \\\n")
            f.write(f"        {test_data_dir_path.relative_to(test_data_dir)}/token_traffic_player_0.log\n")
            f.write("   ```\n\n")
            
            f.write("## 🎯 Metadata Comparison\n\n")
            f.write("### Golden Master Metadata\n")
            f.write("```json\n")
            f.write(json.dumps(control_data.get('metadata', {}), indent=2))
            f.write("\n```\n\n")
            
            f.write("### Test Data Metadata\n")
            f.write("```json\n")
            f.write(json.dumps(test_data.get('metadata', {}), indent=2))
            f.write("\n```\n\n")
            
            f.write("## 🧪 Next Steps\n\n")
            f.write("1. **Identify Root Cause:** Review the differences to understand what changed\n")
            f.write("2. **Code Review:** Check recent changes that might affect game determinism\n")
            f.write("3. **Fix Implementation:** Update code to restore deterministic behavior\n")
            f.write("4. **Regenerate Golden Master:** After fixing, regenerate control data\n")
            f.write("5. **Verify Fix:** Run grounding tests to ensure regression is resolved\n\n")
            
            f.write("## 📊 Token Sequence Analysis\n\n")
            
            # Analyze token sequence differences for each player
            control_players = control_data.get('players', {})
            test_players = test_data.get('players', {})
            
            for player_id in control_players.keys():
                if player_id in test_players:
                    control_seq = control_players[player_id].get('token_sequence', [])
                    test_seq = test_players[player_id].get('token_sequence', [])
                    
                    if control_seq != test_seq:
                        f.write(f"### Player {player_id} Token Sequence Diff\n\n")
                        f.write(f"- **Expected Length:** {len(control_seq)}\n")
                        f.write(f"- **Actual Length:** {len(test_seq)}\n")
                        
                        # Find first difference
                        first_diff_index = None
                        for i, (exp_token, act_token) in enumerate(zip(control_seq, test_seq)):
                            if exp_token != act_token:
                                first_diff_index = i
                                break
                        
                        if first_diff_index is not None:
                            f.write(f"- **First Difference:** Index {first_diff_index}\n")
                            f.write(f"  - Expected: `{control_seq[first_diff_index]}`\n")
                            f.write(f"  - Actual: `{test_seq[first_diff_index]}`\n")
                        
                        # Show context around first difference
                        if first_diff_index is not None:
                            start_idx = max(0, first_diff_index - 5)
                            end_idx = min(len(control_seq), first_diff_index + 6)
                            
                            f.write(f"\n**Context (tokens {start_idx}-{end_idx-1}):**\n")
                            f.write("```\n")
                            f.write("Expected: ")
                            for i in range(start_idx, end_idx):
                                if i < len(control_seq):
                                    marker = " <<<" if i == first_diff_index else ""
                                    f.write(f"{control_seq[i]}{marker} ")
                            f.write("\nActual:   ")
                            for i in range(start_idx, end_idx):
                                if i < len(test_seq):
                                    marker = " <<<" if i == first_diff_index else ""
                                    f.write(f"{test_seq[i]}{marker} ")
                            f.write("\n```\n\n")
        
        print(f"📋 Regression analysis report generated: {diff_report_path}")
        return diff_report_path
    
    def assert_deterministic_behavior(self, test_data_dir: Path, seed: int, random_seed: int):
        """
        Core grounding test: ensure deterministic behavior for given seeds.
        
        If control data doesn't exist, generate it.
        If control data exists, compare current run against it.
        On regression, saves complete debug data and generates diff analysis.
        """
        control_data = self.load_control_data(test_data_dir, seed, random_seed)
        
        if control_data is None:
            # No control data exists - generate golden master
            print(f"🔄 Generating golden master data for seed={seed}, random_seed={random_seed}")
            actual_data = self.run_uat_and_extract_data(seed, random_seed, test_data_dir)
            self.save_control_data(test_data_dir, seed, random_seed, actual_data)
            print(f"✅ Golden master created - run test again to validate deterministic behavior")
            return  # First run just creates the golden master
        
        # Control data exists - run test and compare
        print(f"🧪 Validating deterministic behavior for seed={seed}, random_seed={random_seed}")
        actual_data = self.run_uat_and_extract_data(seed, random_seed, test_data_dir)
        
        differences = self.compare_game_data(control_data, actual_data)
        
        if differences:
            # REGRESSION DETECTED - Save complete debug data and generate analysis
            print(f"🚨 REGRESSION DETECTED! Saving debug data...")
            
            # Run UAT again to get complete test data for debugging
            print(f"🔄 Running UAT for regression analysis...")
            test_data = self.run_uat_for_regression_analysis(seed, random_seed, test_data_dir)
            
            # Generate comprehensive diff analysis report
            diff_report_path = self.generate_regression_diff_report(
                test_data_dir, seed, random_seed, control_data, test_data, differences
            )
            
            # Enhanced error message with debugging paths
            test_data_dir_path = self.get_test_data_dir_path(test_data_dir, seed, random_seed)
            control_dir_path = self.get_control_dir_path(test_data_dir, seed, random_seed)
            
            error_msg = f"🚨 DETERMINISTIC BEHAVIOR VIOLATION!\n"
            error_msg += f"Game output changed for seed={seed}, random_seed={random_seed}\n"
            error_msg += f"Expected output to match golden master, but found {len(differences)} difference(s):\n\n"
            for i, diff in enumerate(differences, 1):
                error_msg += f"{i}. {diff}\n"
            error_msg += f"\n📁 COMPLETE DEBUG DATA SAVED:\n"
            error_msg += f"   - Golden Master: {control_dir_path}\n"
            error_msg += f"   - Failing Test:  {test_data_dir_path}\n"
            error_msg += f"   - Diff Analysis: {diff_report_path}\n\n"
            error_msg += f"🔧 Debug with: diff {control_dir_path}/training_data/all_players_seed_{seed}.json {test_data_dir_path}/training_data/all_players_seed_{seed}.json\n"
            error_msg += f"This indicates a regression in deterministic behavior!"
            
            pytest.fail(error_msg)
        
        print(f"✅ Deterministic behavior validated - output matches golden master")
    
    # Standard test scenarios
    
    def test_seed_42_random_557(self, test_data_dir):
        """Test the standard scenario used in development and debugging."""
        self.assert_deterministic_behavior(test_data_dir, seed=42, random_seed=557)
    
    def test_seed_0_random_1234(self, test_data_dir):
        """Test the default UAT scenario.""" 
        self.assert_deterministic_behavior(test_data_dir, seed=0, random_seed=1234)
    
    def test_seed_100_random_999(self, test_data_dir):
        """Test a different role arrangement scenario."""
        self.assert_deterministic_behavior(test_data_dir, seed=100, random_seed=999)
    
    # Edge case scenarios
    
    def test_boundary_seed_2519_random_1(self, test_data_dir):
        """Test the highest valid seed value."""
        self.assert_deterministic_behavior(test_data_dir, seed=2519, random_seed=1)
    
    def test_minimal_seed_0_random_0(self, test_data_dir):
        """Test minimal seed values."""
        self.assert_deterministic_behavior(test_data_dir, seed=0, random_seed=0)
    
    # Cross-validation scenarios
    
    def test_same_seed_different_random(self, test_data_dir):
        """
        Test that same game seed with different random seeds produces different outcomes.
        This validates that random_seed actually affects the game.
        """
        # Both should complete successfully but produce different agent actions
        data1 = self.run_uat_and_extract_data(seed=42, random_seed=100)
        data2 = self.run_uat_and_extract_data(seed=42, random_seed=200)
        
        # Should have same metadata (seed, num_players) but different sequences
        assert data1['metadata']['seed'] == data2['metadata']['seed'] == 42
        assert data1['metadata']['num_players'] == data2['metadata']['num_players'] == 10
        
        # But token sequences should be different (due to different agent choices)
        differences = self.compare_game_data(data1, data2)
        
        # We expect differences (this validates random_seed affects behavior)
        if not differences:
            pytest.fail("Same seed with different random_seed produced identical output - random_seed has no effect!")
        
        print(f"✅ Different random seeds produced different outcomes ({len(differences)} differences detected)")
    
    def test_deterministic_replay_multiple_runs(self, test_data_dir):
        """
        Test that the same seeds produce identical results across multiple runs.
        This is a more thorough deterministic validation.
        """
        seed, random_seed = 42, 557
        
        # Run same scenario 3 times
        runs = []
        for run_num in range(3):
            print(f"🔄 Run {run_num + 1}/3 with seed={seed}, random_seed={random_seed}")
            data = self.run_uat_and_extract_data(seed, random_seed)
            runs.append(data)
        
        # All runs should be identical
        for i in range(1, len(runs)):
            differences = self.compare_game_data(runs[0], runs[i])
            if differences:
                error_msg = f"🚨 NON-DETERMINISTIC BEHAVIOR DETECTED!\n"
                error_msg += f"Run 1 vs Run {i+1} produced different results:\n"
                for diff in differences:
                    error_msg += f"  - {diff}\n"
                pytest.fail(error_msg)
        
        print(f"✅ All 3 runs produced identical results - behavior is deterministic")


class TestGroundingUtilities:
    """Utility tests for grounding test infrastructure."""
    
    def test_control_data_file_paths(self):
        """Test that control file paths are generated correctly."""
        test_data_dir = Path("/tmp/test")
        grounding_test = TestDeterministicGrounding()
        
        path = grounding_test.get_control_file_path(test_data_dir, seed=42, random_seed=557)
        expected = test_data_dir / "all_players_seed_42_random_557.json"
        
        assert path == expected
    
    def test_game_data_comparison_identical(self):
        """Test that identical game data produces no differences."""
        grounding_test = TestDeterministicGrounding()
        
        data = {
            'metadata': {'seed': 42, 'total_actions': 50, 'num_players': 10, 'game_result': 'WIN'},
            'players': {
                '0': {'token_sequence': [1, 2, 3], 'sequence_length': 3},
                '1': {'token_sequence': [4, 5, 6], 'sequence_length': 3}
            }
        }
        
        differences = grounding_test.compare_game_data(data, data)
        assert differences == []
    
    def test_game_data_comparison_different(self):
        """Test that different game data produces expected differences."""
        grounding_test = TestDeterministicGrounding()
        
        data1 = {
            'metadata': {'seed': 42, 'total_actions': 50, 'num_players': 10},
            'players': {'0': {'token_sequence': [1, 2, 3]}}
        }
        
        data2 = {
            'metadata': {'seed': 42, 'total_actions': 51, 'num_players': 10},  # Different action count
            'players': {'0': {'token_sequence': [1, 2, 4]}}  # Different sequence
        }
        
        differences = grounding_test.compare_game_data(data1, data2)
        
        assert len(differences) == 3  # Should detect metadata and sequence differences with detailed breakdown
        assert any('total_actions' in diff for diff in differences)
        assert any('token sequence differs' in diff for diff in differences)


# CLI interface for manual grounding test execution
def main():
    """Command-line interface for running grounding tests manually."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Deterministic Grounding Tests for Mafia Token Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_deterministic_grounding.py --validate 42 557     # Validate existing golden master
  python test_deterministic_grounding.py --generate 42 557    # Generate new golden master
  python test_deterministic_grounding.py --compare 42 557 100 999  # Compare two scenarios
  
Grounding tests ensure that the same seed+random_seed always produces identical output.
This prevents regressions and validates deterministic behavior for ML training.
        """
    )
    
    parser.add_argument(
        '--validate', nargs=2, type=int, metavar=('SEED', 'RANDOM_SEED'),
        help='Validate deterministic behavior against existing golden master'
    )
    
    parser.add_argument(
        '--generate', nargs=2, type=int, metavar=('SEED', 'RANDOM_SEED'),
        help='Generate new golden master data for the specified seeds'
    )
    
    parser.add_argument(
        '--compare', nargs=4, type=int, metavar=('SEED1', 'RANDOM_SEED1', 'SEED2', 'RANDOM_SEED2'),
        help='Compare two different seed scenarios to ensure they differ'
    )
    
    parser.add_argument(
        '--data-dir', type=str, default="/home/zedmor/mafia_modeling/test/golden_master_data",
        help='Directory for storing golden master data'
    )
    
    args = parser.parse_args()
    
    if not any([args.validate, args.generate, args.compare]):
        parser.print_help()
        return
    
    test_data_dir = Path(args.data_dir)
    test_data_dir.mkdir(exist_ok=True)
    
    grounding_test = TestDeterministicGrounding()
    
    if args.validate:
        seed, random_seed = args.validate
        try:
            grounding_test.assert_deterministic_behavior(test_data_dir, seed, random_seed)
        except Exception as e:
            print(f"❌ Validation failed: {e}")
            exit(1)
    
    elif args.generate:
        seed, random_seed = args.generate
        # Force regeneration by removing existing file
        control_file = grounding_test.get_control_file_path(test_data_dir, seed, random_seed)
        if control_file.exists():
            print(f"🗑️  Removing existing golden master: {control_file}")
            control_file.unlink()
        
        grounding_test.assert_deterministic_behavior(test_data_dir, seed, random_seed)
    
    elif args.compare:
        seed1, random_seed1, seed2, random_seed2 = args.compare
        
        print(f"🔄 Running scenario 1: seed={seed1}, random_seed={random_seed1}")
        data1 = grounding_test.run_uat_and_extract_data(seed1, random_seed1)
        
        print(f"🔄 Running scenario 2: seed={seed2}, random_seed={random_seed2}")
        data2 = grounding_test.run_uat_and_extract_data(seed2, random_seed2)
        
        differences = grounding_test.compare_game_data(data1, data2)
        
        if differences:
            print(f"✅ Scenarios differ as expected ({len(differences)} differences)")
            for i, diff in enumerate(differences[:5], 1):  # Show first 5 differences
                print(f"  {i}. {diff}")
            if len(differences) > 5:
                print(f"  ... and {len(differences) - 5} more differences")
        else:
            print(f"⚠️  WARNING: Scenarios produced identical output!")
            print(f"   This might indicate insufficient randomness or identical seeds")


if __name__ == "__main__":
    main()
