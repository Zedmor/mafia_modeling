#!/usr/bin/env python3
"""
Demo script for deterministic seeding functionality.

This script generates initial game states for all possible seeds (0-2519)
and writes the role arrangements to a log file in single-line format.
"""

import sys
import argparse
from typing import List
from datetime import datetime

from mafia_transformer.token_game_interface import create_token_game
from mafia_game.common import Role


def role_to_short_name(role: Role) -> str:
    """Convert role to short name for compact logging."""
    mapping = {
        Role.DON: "D",
        Role.MAFIA: "M", 
        Role.SHERIFF: "S",
        Role.CITIZEN: "C"
    }
    return mapping[role]


def validate_seed(seed: int) -> bool:
    """Validate that seed is in valid range (0-2519)."""
    return 0 <= seed <= 2519


def generate_single_arrangement(seed: int) -> str:
    """
    Generate a single role arrangement for the given seed.
    
    Args:
        seed: Seed value (must be 0-2519)
        
    Returns:
        Single line string representation of the arrangement
        
    Raises:
        ValueError: If seed is outside valid range
    """
    if not validate_seed(seed):
        raise ValueError(f"Seed {seed} is outside valid range [0, 2519]")
    
    interface = create_token_game()
    state = interface.initialize_game(seed=seed)
    
    # Extract roles from the game state
    roles = [player.private_data.role for player in state._internal_state.game_states]
    
    # Convert to short format: seed:DMMSCCCCC (D=Don, M=Mafia, S=Sheriff, C=Citizen)
    role_string = "".join(role_to_short_name(role) for role in roles)
    
    return f"{seed:04d}:{role_string}"


def generate_all_arrangements(output_file: str = "deterministic_seeding_log.txt") -> None:
    """
    Generate all possible role arrangements and write to log file.
    
    Args:
        output_file: Path to output log file
    """
    interface = create_token_game()
    total_arrangements = interface.get_total_arrangements()
    
    print(f"Generating {total_arrangements} deterministic role arrangements...")
    print(f"Valid seed range: 0 - {total_arrangements - 1}")
    print(f"Output file: {output_file}")
    
    start_time = datetime.now()
    
    with open(output_file, 'w') as f:
        # Write header
        f.write(f"# Deterministic Mafia Game Role Arrangements\n")
        f.write(f"# Generated: {start_time.isoformat()}\n")
        f.write(f"# Total arrangements: {total_arrangements}\n")
        f.write(f"# Format: SEED:ROLE_ARRANGEMENT (D=Don, M=Mafia, S=Sheriff, C=Citizen)\n")
        f.write(f"# Example: 0000:DMMSCCCCC means seed 0 -> Player0=Don, Player1=Mafia, Player2=Mafia, Player3=Sheriff, Player4-9=Citizens\n")
        f.write(f"#\n")
        
        # Generate all arrangements
        for seed in range(total_arrangements):
            try:
                arrangement = generate_single_arrangement(seed)
                f.write(f"{arrangement}\n")
                
                # Progress indicator
                if (seed + 1) % 100 == 0:
                    progress = (seed + 1) / total_arrangements * 100
                    print(f"Progress: {seed + 1}/{total_arrangements} ({progress:.1f}%)")
                    
            except Exception as e:
                print(f"Error generating arrangement for seed {seed}: {e}")
                f.write(f"# ERROR seed {seed}: {e}\n")
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"Completed in {duration.total_seconds():.2f} seconds")
    print(f"All arrangements written to {output_file}")


def verify_arrangements(log_file: str = "deterministic_seeding_log.txt") -> bool:
    """
    Verify that all arrangements in the log file are correct.
    
    Args:
        log_file: Path to log file to verify
        
    Returns:
        True if all arrangements are valid, False otherwise
    """
    print(f"Verifying arrangements in {log_file}...")
    
    interface = create_token_game()
    total_expected = interface.get_total_arrangements()
    
    arrangements_found = 0
    errors = []
    
    with open(log_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip comments and empty lines
            if line.startswith('#') or not line:
                continue
            
            try:
                # Parse line: "SEED:ARRANGEMENT"
                parts = line.split(':')
                if len(parts) != 2:
                    errors.append(f"Line {line_num}: Invalid format")
                    continue
                
                seed_str, arrangement = parts
                seed = int(seed_str)
                
                # Verify seed is in valid range
                if not validate_seed(seed):
                    errors.append(f"Line {line_num}: Seed {seed} out of range")
                    continue
                
                # Verify arrangement format
                if len(arrangement) != 10:
                    errors.append(f"Line {line_num}: Arrangement length {len(arrangement)} != 10")
                    continue
                
                # Verify role distribution
                role_counts = {
                    'D': arrangement.count('D'),
                    'M': arrangement.count('M'),
                    'S': arrangement.count('S'),
                    'C': arrangement.count('C')
                }
                
                if (role_counts['D'] != 1 or role_counts['M'] != 2 or 
                    role_counts['S'] != 1 or role_counts['C'] != 6):
                    errors.append(f"Line {line_num}: Invalid role distribution {role_counts}")
                    continue
                
                # Verify against actual generation
                expected_arrangement = generate_single_arrangement(seed)
                if line != expected_arrangement:
                    errors.append(f"Line {line_num}: Mismatch with generated arrangement")
                    continue
                
                arrangements_found += 1
                
            except Exception as e:
                errors.append(f"Line {line_num}: {e}")
    
    # Report results
    print(f"Arrangements found: {arrangements_found}")
    print(f"Expected: {total_expected}")
    print(f"Errors: {len(errors)}")
    
    if errors:
        print("\nFirst 10 errors:")
        for error in errors[:10]:
            print(f"  {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
    
    success = (arrangements_found == total_expected and len(errors) == 0)
    print(f"Verification: {'PASSED' if success else 'FAILED'}")
    
    return success


def demo_specific_seeds(seeds: List[int]) -> None:
    """
    Demo specific seeds and their arrangements.
    
    Args:
        seeds: List of seed values to demonstrate
    """
    print("=== Demonstrating Specific Seeds ===")
    
    for seed in seeds:
        try:
            if not validate_seed(seed):
                print(f"Seed {seed}: INVALID (outside range [0, 2519])")
                continue
                
            arrangement = generate_single_arrangement(seed)
            print(f"Seed {seed:4d}: {arrangement}")
            
            # Show detailed breakdown for first few seeds
            if seed < 5:
                interface = create_token_game()
                state = interface.initialize_game(seed=seed)
                roles = [player.private_data.role for player in state._internal_state.game_states]
                
                print(f"           Detailed: ", end="")
                for i, role in enumerate(roles):
                    print(f"P{i}={role.name[:3]}", end=" ")
                print()
                
        except Exception as e:
            print(f"Seed {seed}: ERROR - {e}")
    
    print()


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(
        description="Demo deterministic seeding for Mafia game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all arrangements to log file
  python demo_deterministic_seeding.py --generate-all
  
  # Demo specific seeds
  python demo_deterministic_seeding.py --demo-seeds 0 1 42 100 2519
  
  # Verify existing log file
  python demo_deterministic_seeding.py --verify
  
  # Test invalid seeds
  python demo_deterministic_seeding.py --demo-seeds -1 2520 9999
        """
    )
    
    parser.add_argument(
        '--generate-all', 
        action='store_true',
        help='Generate all 2520 arrangements to log file'
    )
    
    parser.add_argument(
        '--demo-seeds', 
        type=int, 
        nargs='+',
        help='Demo specific seed values'
    )
    
    parser.add_argument(
        '--verify', 
        action='store_true',
        help='Verify existing log file'
    )
    
    parser.add_argument(
        '--output', 
        type=str, 
        default='deterministic_seeding_log.txt',
        help='Output log file path (default: deterministic_seeding_log.txt)'
    )
    
    args = parser.parse_args()
    
    # If no arguments, show basic demo
    if not any([args.generate_all, args.demo_seeds, args.verify]):
        print("=== Deterministic Seeding Demo ===")
        interface = create_token_game()
        total = interface.get_total_arrangements()
        print(f"Total possible arrangements: {total}")
        print(f"Valid seed range: 0 - {total - 1}")
        print()
        
        # Demo first few seeds and some interesting ones
        demo_seeds = [0, 1, 2, 42, 100, 1000, 2519]
        demo_specific_seeds(demo_seeds)
        
        # Test invalid seeds
        print("=== Testing Invalid Seeds ===")
        invalid_seeds = [-1, 2520, 9999]
        demo_specific_seeds(invalid_seeds)
        
        print("Use --help for more options")
        return
    
    # Execute requested actions
    if args.demo_seeds:
        demo_specific_seeds(args.demo_seeds)
    
    if args.generate_all:
        generate_all_arrangements(args.output)
    
    if args.verify:
        verify_arrangements(args.output)


if __name__ == "__main__":
    main()
