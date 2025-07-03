#!/usr/bin/env python3
"""
Simple test runner to verify the converted pytest files work correctly.
"""
import sys
import subprocess
from pathlib import Path

def run_test(test_file):
    """Run a specific test file and return the result."""
    print(f"\n{'='*60}")
    print(f"Running: {test_file}")
    print(f"{'='*60}")
    
    try:
        # Try running with python3 -m pytest first
        cmd = [sys.executable, "-m", "pytest", str(test_file), "-v", "-s"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        print(f"Return code: {result.returncode}")
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("TEST TIMED OUT after 5 minutes")
        return False
    except FileNotFoundError:
        print("pytest not found, trying direct execution...")
        
        # Try running the file directly
        try:
            cmd = [sys.executable, str(test_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            print("STDOUT:")
            print(result.stdout)
            
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
                
            print(f"Return code: {result.returncode}")
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print("TEST TIMED OUT after 5 minutes")
            return False
        except Exception as e:
            print(f"Error running test: {e}")
            return False

def main():
    """Run the converted test files."""
    test_files = [
        Path("test/test_mafia_transformer/test_random_agent_end_turn_bug.py"),
        Path("test/test_mafia_transformer/test_seed_42_random_557_scenario.py")
    ]
    
    results = {}
    
    for test_file in test_files:
        if test_file.exists():
            results[test_file.name] = run_test(test_file)
        else:
            print(f"Test file not found: {test_file}")
            results[test_file.name] = False
    
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print(f"{'='*60}")
    
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    print(f"\nOverall: {'PASS' if all_passed else 'FAIL'}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
