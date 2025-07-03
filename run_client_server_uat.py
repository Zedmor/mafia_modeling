#!/usr/bin/env python3
"""
Runner script for Token Client-Server UAT.
Tests complete token-only communication between server and clients.

Usage:
  python run_client_server_uat.py                                    # Use default seeds
  python run_client_server_uat.py --seed 42                          # Use role seed 42
  python run_client_server_uat.py --seed 42 --random-seed 999        # Use role seed 42, random seed 999
  python run_client_server_uat.py --random-seed 777                  # Use default role seed 0, random seed 777
  python run_client_server_uat.py --list-seeds                       # Show available seeds
"""

import sys
from pathlib import Path

# Add src to path so we can import our modules
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from mafia_transformer.token_client_server_uat import TokenClientServerUAT
from pathlib import Path
import random

def main():
    """Main function to run the UAT with command line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run Token Client-Server UAT for Mafia Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_client_server_uat.py                                      # Use default seeds
  python run_client_server_uat.py --seed 42                            # Use role seed 42
  python run_client_server_uat.py --seed 42 --random-seed 999          # Use role seed 42, random seed 999
  python run_client_server_uat.py --show-legal-actions                 # Enable legal actions in logs
  
Known Role Seeds:
  0:  Don=P0, Mafia=P1,P2, Sheriff=P3, Citizens=P4-9
  42: Don=P0, Mafia=P1,P8, Sheriff=P2, Citizens=P3-7,P9
  
Valid role seed range: 0-2519 (2,520 total unique arrangements)
Random seed: any integer (controls agent action choices)
        """
    )
    
    parser.add_argument(
        '--seed', '-s',
        type=int,
        default=42,  # Default to seed 42 for interesting game dynamics
        help='Game seed for deterministic role arrangement (0-2519). Default: 42'
    )
    
    parser.add_argument(
        '--random-seed', '-r',
        type=int,
        default=None,
        help='Random seed for agent action choices (any integer). Default: random'
    )
    
    parser.add_argument(
        '--show-legal-actions',
        action='store_true',
        help='Show legal action sequences in token traffic logs (makes logs verbose)'
    )
    
    args = parser.parse_args()
    
    # Generate random seed if not provided
    actual_random_seed = args.random_seed if args.random_seed is not None else random.randint(1, 9999)
    
    # Show configuration
    print(f"🎯 Running Client-Server UAT with role seed {args.seed}")
    print(f"🎲 Using random seed {actual_random_seed} for agent actions")
    if args.show_legal_actions:
        print("🔍 Legal actions will be shown in token traffic logs")
    
    # Show expected roles for known seeds
    if args.seed == 0:
        print("📋 Expected roles (seed 0): Don=P0, Mafia=P1,P2, Sheriff=P3, Citizens=P4-9")
    elif args.seed == 42:
        print("📋 Expected roles (seed 42): Don=P0, Mafia=P1,P8, Sheriff=P2, Citizens=P3-7,P9")
    
    # Run the UAT
    uat = TokenClientServerUAT(seed=args.seed, random_seed=actual_random_seed, show_legal_actions=args.show_legal_actions)
    log_dir = uat.run_complete_uat()
    
    # List generated files
    print("\n📋 Generated files:")
    for file_path in sorted(Path(log_dir).glob("*")):
        print(f"   - {file_path.name}")

if __name__ == "__main__":
    print("🚀 Running Token Client-Server UAT...")
    main()
