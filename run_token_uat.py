#!/usr/bin/env python3
"""
Simple runner for the Token System UAT.
Run this to execute a full UAT test of the token system.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mafia_transformer.uat_test import main

if __name__ == "__main__":
    print("🚀 Starting Token System User Acceptance Test...")
    print("This will run a complete Mafia game using the token system.")
    print("All interactions will be logged to /home/zedmor/mafia_modeling/test/logs/")
    print()
    
    try:
        log_dir = main()
        print(f"\n✅ UAT completed successfully!")
        print(f"📁 Check the logs in: {log_dir}")
        
    except Exception as e:
        print(f"\n❌ UAT failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
