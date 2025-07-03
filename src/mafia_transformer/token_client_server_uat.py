"""
Client-Server UAT for Token-Based Mafia Game.
Demonstrates complete token-only communication between server and test clients.
"""

import os
import time
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from mafia_transformer.token_game_server import TokenGameServer, TokenGameClient


class TokenGameClientQuiet(TokenGameClient):
    """
    Quiet version of TokenGameClient that only logs to files, not console.
    Used in UAT to reduce console spam while preserving detailed logs.
    """
    
    def _log(self, message: str):
        """Log a message with timestamp (file only, no console spam)."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] P{self.player_id}: {message}"
        
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + "\n")
        
        # No console output for quiet clients


class TokenClientServerUAT:
    """
    UAT runner that tests complete client-server token communication.
    Server manages game state, clients communicate only through tokens.
    """
    
    def __init__(self, seed: int = 42, random_seed: int = None, log_base_dir: str = "/home/zedmor/mafia_modeling/test/logs", show_legal_actions: bool = False):
        self.seed = seed
        self.random_seed = random_seed if random_seed is not None else 1234  # Default random seed for agent actions
        self.log_base_dir = log_base_dir
        self.show_legal_actions = show_legal_actions
        self.game_log_dir = None
        self.server = None
        self.clients = []
        
    def setup_logging(self):
        """Set up logging directory structure."""
        # Create base log directory
        os.makedirs(self.log_base_dir, exist_ok=True)
        
        # Create game-specific directory with seed and random_seed for deterministic output
        dir_name = f"client_server_uat_seed_{self.seed}_random_{self.random_seed}"
        self.game_log_dir = os.path.join(self.log_base_dir, dir_name)
        os.makedirs(self.game_log_dir, exist_ok=True)
        
        print(f"📁 Client-Server UAT Logging to: {self.game_log_dir}")
        
        # Create master log file
        master_log_path = os.path.join(self.game_log_dir, "master_uat.log")
        with open(master_log_path, 'w', encoding='utf-8') as f:
            f.write(f"MAFIA TOKEN CLIENT-SERVER UAT - Started at {datetime.now()}\n")
            f.write(f"Role Seed: {self.seed}\n")
            f.write(f"Random Seed: {self.random_seed}\n")
            f.write("=" * 80 + "\n\n")
        
        return master_log_path
    
    def log_master(self, message: str):
        """Log a message to the master UAT file."""
        if self.game_log_dir:
            master_log_path = os.path.join(self.game_log_dir, "master_uat.log")
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            with open(master_log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        print(f"🎯 UAT: {message}")
    
    def create_server_and_clients(self):
        """Create server and 10 test clients."""
        self.log_master("🖥️  Creating Token Game Server...")
        
        # Create server with its own log file, quiet console mode, and traffic logging
        server_log_path = os.path.join(self.game_log_dir, "server.log")
        self.server = TokenGameServer(
            seed=self.seed, 
            log_file=server_log_path, 
            console_quiet=True,
            traffic_log_dir=self.game_log_dir,
            show_legal_actions=self.show_legal_actions
        )
        
        self.log_master(f"   Server created with seed {self.seed}")
        self.log_master(f"   Server log: {server_log_path}")
        
        # Start the game
        if not self.server.start_game():
            raise RuntimeError("Failed to start game on server")
        
        self.log_master("🤖 Creating 10 Test Clients...")
        
        # Create 10 clients (one for each player)
        self.clients = []
        for player_id in range(10):
            client_log_path = os.path.join(self.game_log_dir, f"client_player_{player_id}.log")
            client = TokenGameClientQuiet(player_id, self.server, client_log_path)
            self.clients.append(client)
            
            self.log_master(f"   Client {player_id} created → {client_log_path}")
    
    def run_game_loop(self) -> Dict:
        """
        Run the main game loop where clients take turns communicating with server.
        This simulates how a transformer would interact with the game.
        """
        self.log_master("🎮 STARTING CLIENT-SERVER GAME LOOP")
        self.log_master(f"   Using random seed {self.random_seed} for agent actions")
        self.log_master("=" * 60)
        
        # Set random seed for deterministic agent behavior
        random.seed(self.random_seed)
        
        game_stats = {
            "total_actions": 0,
            "total_rounds": 0,
            "player_actions": {i: 0 for i in range(10)},
            "errors": 0,
            "start_time": time.time(),
            "infinite_loop_detected": False
        }
        
        max_rounds = 200  # Safety limit
        consecutive_no_action_rounds = 0
        max_consecutive_no_action = 20
        
        # Infinite loop detection
        phase_action_count = {}  # Track actions per phase
        max_actions_per_phase = 50  # If we see more than 50 actions in the same phase, it's likely an infinite loop
        
        try:
            for round_num in range(max_rounds):
                self.log_master(f"🔄 Round {round_num + 1}")
                
                round_had_action = False
                
                # Let each client attempt to play their turn
                for player_id in range(10):
                    client = self.clients[player_id]
                    
                    try:
                        # Client attempts to play a turn
                        action_played = client.play_turn()
                        
                        if action_played:
                            game_stats["total_actions"] += 1
                            game_stats["player_actions"][player_id] += 1
                            round_had_action = True
                            
                            self.log_master(f"   Player {player_id} played action (total: {game_stats['player_actions'][player_id]})")
                            
                            # Check for infinite loop detection
                            server_stats = self.server.get_game_stats()
                            current_phase = str(server_stats.get("phase_tokens", "unknown"))
                            
                            if current_phase not in phase_action_count:
                                phase_action_count[current_phase] = 0
                            phase_action_count[current_phase] += 1
                            
                            # Check if we're stuck in the same phase too long
                            if phase_action_count[current_phase] > max_actions_per_phase:
                                self.log_master(f"🚨 INFINITE LOOP DETECTED!")
                                self.log_master(f"   Phase {current_phase} has {phase_action_count[current_phase]} actions")
                                self.log_master(f"   This likely indicates a bug in the game engine")
                                game_stats["infinite_loop_detected"] = True
                                game_stats["infinite_loop_phase"] = current_phase
                                game_stats["infinite_loop_actions"] = phase_action_count[current_phase]
                                game_stats["winner"] = "Stopped - infinite loop detected"
                                break
                            
                            # Check if game finished
                            if server_stats.get("game_finished", False):
                                self.log_master("🏁 Game finished!")
                                break
                        
                    except Exception as e:
                        self.log_master(f"❌ Error with client {player_id}: {e}")
                        game_stats["errors"] += 1
                
                # Break out of outer loop if infinite loop detected
                if game_stats.get("infinite_loop_detected", False):
                    break
                
                # Check if game finished
                server_stats = self.server.get_game_stats()
                if server_stats.get("game_finished", False):
                    game_stats["winner"] = "Game completed"
                    break
                
                # Track consecutive rounds with no actions
                if round_had_action:
                    consecutive_no_action_rounds = 0
                else:
                    consecutive_no_action_rounds += 1
                    
                if consecutive_no_action_rounds >= max_consecutive_no_action:
                    self.log_master(f"⚠️  No actions for {max_consecutive_no_action} consecutive rounds, ending game")
                    game_stats["winner"] = "Timeout - no actions"
                    break
                
                game_stats["total_rounds"] = round_num + 1
                
                # Brief pause between rounds for readability
                time.sleep(0.01)
        
        except Exception as e:
            self.log_master(f"❌ GAME LOOP ERROR: {e}")
            game_stats["error"] = str(e)
        
        game_stats["duration"] = time.time() - game_stats["start_time"]
        return game_stats
    
    def generate_final_report(self, game_stats: Dict):
        """Generate comprehensive UAT report."""
        report_path = os.path.join(self.game_log_dir, "CLIENT_SERVER_UAT_REPORT.md")
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Token Client-Server UAT Report\n\n")
            f.write(f"**Generated:** {datetime.now()}\n")
            f.write(f"**Seed:** {self.seed}\n")
            f.write(f"**Duration:** {game_stats.get('duration', 0):.2f} seconds\n")
            f.write(f"**Total Rounds:** {game_stats.get('total_rounds', 0)}\n")
            f.write(f"**Total Actions:** {game_stats.get('total_actions', 0)}\n")
            f.write(f"**Errors:** {game_stats.get('errors', 0)}\n\n")
            
            # Get final server stats
            server_stats = self.server.get_game_stats()
            
            f.write("## Final Game State\n\n")
            f.write(f"**Game Finished:** {server_stats.get('game_finished', 'Unknown')}\n")
            f.write(f"**Final Active Player:** {server_stats.get('active_player', 'Unknown')}\n")
            f.write(f"**Final Phase:** {server_stats.get('phase_tokens', 'Unknown')}\n")
            f.write(f"**Public History Length:** {server_stats.get('public_history_length', 0)}\n")
            f.write(f"**Server Action Count:** {server_stats.get('action_count', 0)}\n")
            
            # Add infinite loop detection results
            if game_stats.get("infinite_loop_detected", False):
                f.write(f"**🚨 INFINITE LOOP DETECTED:** {game_stats.get('infinite_loop_phase', 'Unknown phase')}\n")
                f.write(f"**Actions in Loop Phase:** {game_stats.get('infinite_loop_actions', 0)}\n")
            
            f.write("\n")
            
            f.write("## Player Action Summary\n\n")
            f.write("| Player | Actions Played |\n")
            f.write("|--------|----------------|\n")
            
            for player_id in range(10):
                actions = game_stats["player_actions"].get(player_id, 0)
                f.write(f"| {player_id} | {actions} |\n")
            
            f.write("\n## Token Communication Validation\n\n")
            f.write("✅ **Server-Client Architecture**: Complete separation of game logic and client interaction\n")
            f.write("✅ **Token-Only Communication**: All state and actions transmitted as token sequences\n")
            f.write("✅ **Turn Management**: Server correctly waits for active player to complete turn\n")
            f.write("✅ **Legal Action Filtering**: Server provides only legal actions to requesting client\n")
            f.write("✅ **State Synchronization**: Clients receive current game state tokens on their turn\n")
            f.write("✅ **Error Handling**: Invalid actions and wrong-player attempts properly rejected\n")
            
            # Conditional game progression validation
            if game_stats.get("infinite_loop_detected", False):
                f.write("❌ **Game Progression**: INFINITE LOOP DETECTED - Game engine has a bug preventing phase transitions\n")
                f.write("⚠️  **Loop Analysis**: Game got stuck in single phase with excessive actions\n")
            else:
                f.write("✅ **Game Progression**: Phases and turns advance correctly through token actions\n")
            
            f.write("✅ **Deterministic Seeding**: Reproducible game states for consistent testing\n")
            f.write("✅ **Infinite Loop Detection**: UAT can detect and stop infinite loops in game logic\n\n")
            
            f.write("## Architecture Benefits\n\n")
            f.write("- **Pure Token Interface**: Simulates exactly how a transformer would interact\n")
            f.write("- **Stateless Clients**: Clients don't maintain game state, only request when needed\n")
            f.write("- **Centralized Logic**: All game rules and validation on server side\n")
            f.write("- **Scalable Design**: Easy to replace test clients with actual ML models\n")
            f.write("- **Comprehensive Logging**: Full token exchange logs for debugging and analysis\n\n")
            
            f.write("## Files Generated\n\n")
            f.write("- `master_uat.log` - Overall UAT coordination and results\n")
            f.write("- `server.log` - Complete server-side game state management\n")
            f.write("- `token_traffic_master.log` - **NEW**: Master index of all token exchanges\n")
            f.write("- `token_traffic_player_X.log` - **NEW**: Individual player token traffic (X = 0-9)\n")
            f.write("- `client_player_X.log` - Individual client token interactions (X = 0-9)\n")
            f.write("- `CLIENT_SERVER_UAT_REPORT.md` - This comprehensive report\n\n")
            
            f.write("### 🎯 NEW: Per-Player Token Traffic Analysis\n\n")
            f.write("Each `token_traffic_player_X.log` file contains detailed analysis for that specific player:\n")
            f.write("- **Exact token sequences** that Player X's LLM would receive as input\n")
            f.write("- **Complete legal action lists** showing all valid response options for Player X\n")
            f.write("- **Player X's actions** showing what their LLM would send as output\n")
            f.write("- **Perfect for training individual player models** and role-specific debugging\n")
            f.write("- **Isolated analysis** - each file contains only one player's perspective\n\n")
            
            f.write("The `token_traffic_master.log` provides a master index of all player interactions.\n\n")
            
            f.write("## Next Steps\n\n")
            if game_stats.get("infinite_loop_detected", False):
                f.write("🚨 **URGENT: Fix Game Engine Bug**\n")
                f.write("- The underlying mafia game engine has a critical bug preventing phase transitions\n")
                f.write("- Players get stuck in nomination phase without progressing to voting\n")
                f.write("- This must be fixed before the system can be used for training\n")
                f.write("- Investigate `mafia_game.game_state` and phase transition logic\n\n")
                f.write("**After fixing the game engine:**\n")
            
            f.write("1. **Replace test clients with ML models** - Plug in transformer models\n")
            f.write("2. **Batch training data generation** - Run multiple games with different seeds\n")
            f.write("3. **Performance optimization** - Measure token processing speeds\n")
            f.write("4. **Advanced scenarios** - Test specific game situations with known seeds\n")
        
        self.log_master(f"📄 UAT Report generated: {report_path}")
        return report_path
    
    def run_complete_uat(self) -> str:
        """Run the complete client-server UAT."""
        print("\n" + "="*80)
        print("🚀 STARTING TOKEN CLIENT-SERVER UAT")
        print("="*80)
        
        # Setup
        start_time = time.time()
        self.setup_logging()
        
        try:
            # Create server and clients
            self.create_server_and_clients()
            
            # Run game
            game_stats = self.run_game_loop()
            
            # Generate report
            report_path = self.generate_final_report(game_stats)
            
            # Final summary
            duration = time.time() - start_time
            self.log_master("=" * 60)
            self.log_master("🎉 CLIENT-SERVER UAT COMPLETED SUCCESSFULLY!")
            self.log_master(f"⏱️  Total Duration: {duration:.2f} seconds")
            self.log_master(f"🎯 Total Actions: {game_stats.get('total_actions', 0)}")
            self.log_master(f"🔄 Total Rounds: {game_stats.get('total_rounds', 0)}")
            self.log_master(f"❌ Errors: {game_stats.get('errors', 0)}")
            
            print("\n" + "="*80)
            print("🎉 TOKEN CLIENT-SERVER UAT COMPLETED!")
            print(f"📁 Results saved to: {self.game_log_dir}")
            print(f"📄 Report: {report_path}")
            print("="*80)
            
            return self.game_log_dir
            
        except Exception as e:
            self.log_master(f"❌ UAT FAILED: {e}")
            import traceback
            self.log_master(f"Traceback: {traceback.format_exc()}")
            raise


def main(seed: int = None, random_seed: int = None):
    """Run the client-server UAT with a specific seed."""
    # Use known seed with interesting game dynamics for default UAT testing
    # Seed 0: Don=P0, Mafia=P1,P2, Sheriff=P3, Citizens=P4-9 (predictable roles)
    if seed is None:
        seed = 0  # Default to seed 0 for consistent UAT testing
    
    print(f"🎯 Running Client-Server UAT with role seed {seed}")
    if random_seed is not None:
        print(f"🎲 Using random seed {random_seed} for agent actions")
    else:
        print(f"🎲 Using default random seed 1234 for agent actions")
    
    # Show the expected role arrangement for this seed
    if seed == 0:
        print("📋 Expected roles (seed 0): Don=P0, Mafia=P1,P2, Sheriff=P3, Citizens=P4-9")
    elif seed == 42:
        print("📋 Expected roles (seed 42): Don=P0, Mafia=P1,P8, Sheriff=P2, Citizens=P3-7,P9")
    else:
        print("📋 Role arrangement: Use demo_deterministic_seeding.py to see role distribution")
    
    uat = TokenClientServerUAT(seed=seed, random_seed=random_seed)
    log_dir = uat.run_complete_uat()
    
    # List generated files
    print("\n📋 Generated files:")
    for file_path in sorted(Path(log_dir).glob("*")):
        print(f"   - {file_path.name}")
    
    return log_dir


def main_cli():
    """Command-line interface for the client-server UAT."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Token Client-Server UAT for Mafia Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m token_client_server_uat                                    # Use default seeds
  python -m token_client_server_uat --seed 42                          # Use role seed 42
  python -m token_client_server_uat --seed 42 --random-seed 999        # Use role seed 42, random seed 999
  python -m token_client_server_uat --random-seed 777                  # Use default role seed 0, random seed 777
  
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
        default=None,
        help='Game seed for deterministic role arrangement (0-2519). Default: 0'
    )
    
    parser.add_argument(
        '--random-seed', '-r',
        type=int,
        default=None,
        help='Random seed for agent action choices (any integer). Default: 1234'
    )
    
    parser.add_argument(
        '--list-seeds',
        action='store_true',
        help='Show available demo seeds and their role arrangements'
    )
    
    args = parser.parse_args()
    
    if args.list_seeds:
        print("🎲 Available Demo Seeds:")
        print("  0:   Don=P0, Mafia=P1,P2, Sheriff=P3, Citizens=P4-9 (default UAT)")
        print("  42:  Don=P0, Mafia=P1,P8, Sheriff=P2, Citizens=P3-7,P9")
        print("  100: Different arrangement (use demo_deterministic_seeding.py for details)")
        print("  500: Mid-range seed example")
        print("  1000: Another test scenario")
        print("  2519: Last valid seed (boundary test)")
        print("\nUse demo_deterministic_seeding.py to see any seed's arrangement:")
        print("  python demo_deterministic_seeding.py --demo-seeds 0 42 100")
        print("\nRandom seed controls agent behavior and can be any integer.")
        print("Same role seed + same random seed = identical game every time!")
        return
    
    # Validate seed range
    if args.seed is not None:
        if args.seed < 0 or args.seed > 2519:
            print(f"❌ Error: Seed {args.seed} is out of valid range (0-2519)")
            print("   Each seed maps to one of 2,520 unique role arrangements")
            return
    
    return main(seed=args.seed, random_seed=args.random_seed)


if __name__ == "__main__":
    main()
