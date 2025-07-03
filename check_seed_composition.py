#!/usr/bin/env python3
"""
Check the role composition for specific seeds in the Mafia game.
"""

import sys
import itertools
from mafia_game.common import Role

def generate_all_role_arrangements():
    """Generate all possible role arrangements for deterministic seeding."""
    arrangements = []
    
    # Generate all combinations for placing roles
    positions = list(range(10))
    
    # Choose 1 position for Don
    for don_pos in itertools.combinations(positions, 1):
        remaining_after_don = [p for p in positions if p not in don_pos]
        
        # Choose 2 positions for Mafia
        for mafia_pos in itertools.combinations(remaining_after_don, 2):
            remaining_after_mafia = [p for p in remaining_after_don if p not in mafia_pos]
            
            # Choose 1 position for Sheriff
            for sheriff_pos in itertools.combinations(remaining_after_mafia, 1):
                remaining_after_sheriff = [p for p in remaining_after_mafia if p not in sheriff_pos]
                
                # Remaining 6 positions are Citizens
                citizen_pos = remaining_after_sheriff
                
                # Create role arrangement
                roles = [Role.CITIZEN] * 10  # Default all to citizens
                roles[don_pos[0]] = Role.DON
                roles[mafia_pos[0]] = Role.MAFIA
                roles[mafia_pos[1]] = Role.MAFIA
                roles[sheriff_pos[0]] = Role.SHERIFF
                
                arrangements.append(roles)
    
    return arrangements

def get_role_composition(seed: int):
    """Get the role composition for a specific seed."""
    arrangements = generate_all_role_arrangements()
    arrangement_index = seed % len(arrangements)
    role_arrangement = arrangements[arrangement_index]
    
    # Create a nice representation
    composition = {}
    for i, role in enumerate(role_arrangement):
        if role not in composition:
            composition[role] = []
        composition[role].append(i)
    
    return composition, role_arrangement

def format_composition(seed: int, composition: dict, role_arrangement: list):
    """Format the composition nicely."""
    print(f"🎯 SEED {seed} COMPOSITION:")
    print("=" * 50)
    
    # Show role summary
    for role in [Role.DON, Role.MAFIA, Role.SHERIFF, Role.CITIZEN]:
        if role in composition:
            players = composition[role]
            if role == Role.DON:
                print(f"🔴 Don: P{players[0]}")
            elif role == Role.MAFIA:
                print(f"⚫ Mafia: P{players[0]}, P{players[1]}")
            elif role == Role.SHERIFF:
                print(f"🔵 Sheriff: P{players[0]}")
            elif role == Role.CITIZEN:
                players_str = ", ".join([f"P{p}" for p in players])
                print(f"👥 Citizens: {players_str}")
    
    print()
    print("📋 DETAILED LAYOUT:")
    for i, role in enumerate(role_arrangement):
        role_symbol = {
            Role.DON: "🔴",
            Role.MAFIA: "⚫", 
            Role.SHERIFF: "🔵",
            Role.CITIZEN: "👤"
        }
        role_name = {
            Role.DON: "Don",
            Role.MAFIA: "Mafia", 
            Role.SHERIFF: "Sheriff",
            Role.CITIZEN: "Citizen"
        }
        print(f"  P{i}: {role_symbol[role]} {role_name[role]}")

if __name__ == "__main__":
    # Check seed 42 and a few others for comparison
    test_seeds = [42, 0, 1, 100, 420]
    
    arrangements = generate_all_role_arrangements()
    print(f"📊 Total possible arrangements: {len(arrangements)}")
    print()
    
    for seed in test_seeds:
        composition, role_arrangement = get_role_composition(seed)
        format_composition(seed, composition, role_arrangement)
        print()
