# Mafia Token Game Server Specification

**Version:** 1.0  
**Date:** 2025-01-26  
**Purpose:** Complete specification for token-based Mafia game server implementing all game rules and client communication protocols.

## Table of Contents

1. [Overview](#overview)
2. [Server Architecture](#server-architecture)
3. [Client-Server Protocol](#client-server-protocol)
4. [Legal Action System](#legal-action-system)
5. [Token Communication](#token-communication)
6. [Game State Management](#game-state-management)
7. [Multi-Action Sequences](#multi-action-sequences)
8. [Phase-Specific Rules](#phase-specific-rules)
9. [Error Handling](#error-handling)
10. [Implementation Examples](#implementation-examples)

---

## Overview

The Mafia Token Game Server implements a complete client-server architecture where:

- **Server** manages all game state and enforces Mafia game rules
- **Clients** communicate exclusively through token sequences
- **Legal actions** are computed and provided by server to prevent clients from needing game logic
- **Deterministic seeding** enables reproducible training scenarios

### Key Design Principles

1. **Stateless Clients**: Clients store no game state, only request when needed
2. **Server Authority**: All game rules, validation, and state transitions on server
3. **Token-Only Communication**: All information exchanged as discrete token sequences
4. **Legal Action Provision**: Server computes and provides all valid actions to requesting clients

---

## Server Architecture

### Core Components

```python
class TokenGameServer:
    """Central game server managing state and client communication."""
    
    def __init__(self, seed: int, log_file: str = None, traffic_log_dir: str = None):
        self.interface = TokenGameInterface()      # Game engine interface
        self.current_state: TokenGameState         # Current game state
        self.seed = seed                          # Deterministic role arrangement
        
    # Core API Methods
    def start_game(self) -> bool
    def get_player_state(self, player_id: int) -> ServerResponse
    def apply_player_action(self, player_id: int, action_tokens: List[int]) -> ServerResponse
    def get_game_stats(self) -> Dict
```

### Data Structures

```python
@dataclass
class ServerResponse:
    """Complete server response to client request."""
    success: bool                           # Request processed successfully
    player_state: Optional[PlayerStateTokens]  # Game state if player's turn
    legal_actions: List[List[int]]         # All valid action sequences
    game_finished: bool                    # Game completion status
    winner: Optional[str]                  # Winner if game finished
    error_message: Optional[str]           # Error details if failed

@dataclass
class PlayerStateTokens:
    """Player-specific view of game state as tokens."""
    player_id: int                         # Requesting player's ID
    chronological_history: List[int]       # Complete game history sequence
    private_state: List[int]               # Player's private information
    active_player: int                     # Currently acting player
    is_active: bool                       # True if this player should act
```

---

## Client-Server Protocol

### Communication Flow

```
1. Client Request:    get_player_state(player_id) 
2. Server Response:   ServerResponse with state + legal_actions
3. Client Action:     apply_player_action(player_id, chosen_action_tokens)
4. Server Update:     Apply action, advance game state
5. Repeat:           Next player requests state
```

### Protocol Rules

1. **Turn-Based Access**: Only active player receives state and legal actions
2. **Atomic Actions**: Each client action is atomic - either succeeds or fails completely  
3. **State Consistency**: Server maintains authoritative game state
4. **Error Recovery**: Invalid actions rejected with descriptive error messages

### Example Communication Sequence

```python
# 1. Client requests state (Player 0's turn in day phase)
response = server.get_player_state(player_id=0)

# 2. Server responds with:
# response.success = True
# response.player_state.chronological_history = [GAME_START, PLAYER_0, YOUR_ROLE, DON, ...]
# response.legal_actions = [
#     [END_TURN],
#     [NOMINATE, PLAYER_1, END_TURN], 
#     [NOMINATE, PLAYER_2, END_TURN],
#     [SAY, PLAYER_1, RED, END_TURN],
#     [CLAIM_SHERIFF, END_TURN],
#     [SAY, PLAYER_3, BLACK, NOMINATE, PLAYER_1, END_TURN],  # Multi-action
#     ...  # 70+ total legal sequences
# ]

# 3. Client chooses action and sends
chosen_action = [SAY, PLAYER_1, RED, NOMINATE, PLAYER_2, END_TURN]
response = server.apply_player_action(player_id=0, action_tokens=chosen_action)

# 4. Server validates, applies action, advances to next player
# response.success = True
# Game state updated, next player (Player 1) becomes active
```

---

## Legal Action System

### **Solution to Agent Action Selection**

**Problem**: How do agents choose valid actions without implementing game logic?

**Solution**: Server computes and provides complete list of legal action sequences.

### Legal Action Generation

The server generates all legal actions for the requesting player by:

1. **Phase Detection**: Determine current game phase (Day, Voting, Night)
2. **Role Validation**: Check player's role and status (alive/dead)  
3. **Target Enumeration**: Find all valid targets for each action type
4. **Sequence Construction**: Build complete action sequences including multi-actions
5. **Rule Enforcement**: Apply game-specific constraints (nomination limits, etc.)

### Legal Action Response Format

```python
# Server provides complete legal action sequences
legal_actions = [
    # Single actions + END_TURN
    [END_TURN],                                    # Do nothing
    [NOMINATE, PLAYER_1, END_TURN],               # Nominate Player 1
    [SAY, PLAYER_2, RED, END_TURN],               # Declare Player 2 is red
    [CLAIM_SHERIFF, END_TURN],                    # Claim to be sheriff
    
    # Multi-action sequences (Day phase only)  
    [SAY, PLAYER_1, BLACK, CLAIM_SHERIFF, END_TURN],           # 2 actions + END_TURN
    [NOMINATE, PLAYER_3, SAY, PLAYER_2, RED, END_TURN],       # Nominate + declare
    [CLAIM_SHERIFF_CHECK, PLAYER_1, BLACK, SAY, PLAYER_2, RED, 
     NOMINATE, PLAYER_1, END_TURN],                           # 3 actions + END_TURN
    
    # ... up to 70+ legal sequences for day phases
]
```

### Agent Action Selection

```python
class SimpleRandomAgent:
    """Agent that selects randomly from server-provided legal actions."""
    
    def choose_action(self, legal_actions: List[List[int]]) -> List[int]:
        """No game logic needed - just choose from provided options."""
        import random
        return random.choice(legal_actions)
```

### Phase-Specific Legal Actions

#### Day Phase (70+ legal actions)
- All alive players can: `NOMINATE`, `SAY`, `CLAIM_SHERIFF`, `CLAIM_SHERIFF_CHECK`, `DENY_SHERIFF`
- Multi-action sequences: 0-7 actions + `END_TURN`
- Constraints: Max 1 nomination per sequence, no duplicate actions

#### Voting Phase (2-10 legal actions)  
- All alive players must: `VOTE` for nominated/tied players
- Single action only: `[VOTE, PLAYER_X]` (no END_TURN in voting)
- No abstention allowed (except dead players giving speeches)

#### Night Kill Phase (0-10 legal actions)
- Only Mafia/Don can: `KILL` alive players or `END_TURN`
- Single action: `[KILL, PLAYER_X, END_TURN]` or `[END_TURN]`

#### Night Don Phase (0-10 legal actions)
- Only Don can: `DON_CHECK` alive players or `END_TURN`  
- Single action: `[DON_CHECK, PLAYER_X, END_TURN]` or `[END_TURN]`

#### Night Sheriff Phase (0-10 legal actions)
- Only Sheriff can: `SHERIFF_CHECK` alive players or `END_TURN`
- Single action: `[SHERIFF_CHECK, PLAYER_X, END_TURN]` or `[END_TURN]`

---

## Token Communication

### Observation Token Sequence

The server provides each player with a complete chronological view of the game:

```python
# Example Player 0 observation tokens (Don role, seed 42)
observation_tokens = [
    # Game Setup
    GAME_START, PLAYER_0,                   # Playing as Player 0
    YOUR_ROLE, DON,                         # Private role information
    MAFIA_TEAM, PLAYER_1, PLAYER_8,        # Private team information
    
    # Game Progression  
    DAY_1, DAY_PHASE_START,                 # Phase markers
    PLAYER_0, SAY, PLAYER_2, RED, END_TURN, # Player 0's action
    PLAYER_1, NOMINATE, PLAYER_3, END_TURN, # Player 1's action
    # ... more player actions ...
    
    VOTING_PHASE_START,                     # Phase transition
    PLAYER_0, VOTE, PLAYER_3,               # Voting actions (no END_TURN)
    # ... more votes ...
    
    NIGHT_1, NIGHT_PHASE_START,             # Night phase
    PLAYER_0, KILL, PLAYER_3, END_TURN,     # Don kills (private to mafia)
    PLAYER_0, DON_CHECK, PLAYER_5, NOT_SHERIFF, END_TURN,  # Don check result
    
    # Current turn signaling (ephemeral)
    YOUR_TURN, NEXT_TURN                    # Signals it's this player's turn
]
```

### Private vs Public Information

#### Private Information (visible only to specific players)
- **Role Assignment**: `[YOUR_ROLE, ROLE_TOKEN]`
- **Team Information**: `[MAFIA_TEAM, PLAYER_X, PLAYER_Y, ...]` (for Mafia/Don only)
- **Check Results**: `[SHERIFF_CHECK, PLAYER_X, COLOR_RESULT]` (for Sheriff only)
- **Night Actions**: `[KILL, PLAYER_X]` (visible to Mafia team only)

#### Public Information (visible to all players)
- **Phase Transitions**: `[DAY_1, DAY_PHASE_START]`, `[VOTING_PHASE_START]`
- **Day Actions**: `[PLAYER_X, SAY, PLAYER_Y, RED]`, `[PLAYER_X, NOMINATE, PLAYER_Y]`
- **Eliminations**: `[PLAYER_X, ELIMINATED]`, `[PLAYER_X, KILLED]`
- **Game Results**: `[RED_TEAM_WON]`, `[BLACK_TEAM_WON]`

### Ephemeral Tokens

Special tokens added only during observation, not stored in permanent game history:

- **`YOUR_TURN`**: Added only for active player's observation
- **`NEXT_TURN`**: Training signal for transformer models (indicates response expected)

---

## Game State Management

### State Representation

```python
class TokenGameState:
    """Complete game state maintained by server."""
    
    # Per-player chronological sequences
    player_chronological_sequences: List[List[int]]  # [player_id][token_sequence]
    
    # Game control
    active_player: int              # Currently acting player (0-9)
    seed: int                      # Deterministic role arrangement (0-2519)
    
    # Internal game engine state
    _internal_state: CompleteGameState  # Full mafia game state object
```

### State Updates

1. **Action Application**: Server applies action to internal game state
2. **Sequence Updates**: All relevant player sequences updated with new information
3. **Turn Advancement**: Active player updated based on game rules
4. **Phase Transitions**: Automatic progression through game phases

### Deterministic Seeding

```python
# 2,520 unique role arrangements (mathematical maximum)
# Seed 0:   Don=P0, Mafia=P1,P2, Sheriff=P3, Citizens=P4-9
# Seed 42:  Don=P0, Mafia=P1,P8, Sheriff=P2, Citizens=P3-7,P9
# Seed 2519: Last valid arrangement

def initialize_game(seed: int) -> TokenGameState:
    """Create deterministic game state from seed."""
    arrangement = get_role_arrangement(seed)  # Maps seed to specific roles
    return create_game_with_roles(arrangement)
```

---

## Multi-Action Sequences

### Day Phase Multi-Actions

Day phases uniquely support multi-action sequences where players perform 0-7 actions before ending their turn:

```python
# Valid day phase sequences
[END_TURN]                                           # 0 actions
[NOMINATE, PLAYER_3, END_TURN]                      # 1 action  
[SAY, PLAYER_1, RED, CLAIM_SHERIFF, END_TURN]       # 2 actions
[NOMINATE, PLAYER_2, SAY, PLAYER_3, BLACK, 
 CLAIM_SHERIFF_CHECK, PLAYER_1, RED, END_TURN]      # 3 actions
# ... up to 7 actions + END_TURN
```

### Multi-Action Rules

1. **Maximum Actions**: 7 actions before `END_TURN`
2. **Nomination Limit**: Maximum 1 `NOMINATE` action per sequence
3. **No Duplicates**: Cannot repeat identical actions within sequence  
4. **Must End**: All sequences must end with `END_TURN`
5. **Day Phase Only**: Multi-actions only allowed during day phases

### Server Implementation

```python
def generate_multi_action_sequences(available_actions: List[Action]) -> List[List[int]]:
    """Generate all valid multi-action sequences for day phase."""
    
    sequences = []
    
    # Single END_TURN option
    sequences.append([END_TURN])
    
    # Single action + END_TURN options
    for action in available_actions:
        action_tokens = encode_action(action)
        sequences.append(action_tokens + [END_TURN])
    
    # Multi-action sequences (2-7 actions + END_TURN)
    for length in range(2, 8):
        # Generate valid combinations respecting nomination limit
        valid_combinations = generate_valid_combinations(available_actions, length)
        for combination in valid_combinations:
            sequence = []
            for action in combination:
                sequence.extend(encode_action(action))
            sequence.append(END_TURN)
            sequences.append(sequence)
    
    return sequences
```

---

## Phase-Specific Rules

### Day Phase Rules

**Objective**: Discussion and nomination of players for elimination

**Participants**: All alive players take turns
**Turn Order**: Round-robin (Player 0 → 1 → 2 → ... → 9, skipping dead)
**Actions Per Turn**: 0-7 actions + `END_TURN`

**Available Actions**:
- `NOMINATE PLAYER_X`: Nominate player for elimination (max 1 per turn)
- `SAY PLAYER_X COLOR`: Declare player's team affiliation  
- `CLAIM_SHERIFF`: Declare being the Sheriff
- `DENY_SHERIFF`: Deny being the Sheriff
- `CLAIM_SHERIFF_CHECK PLAYER_X COLOR`: Claim result of Sheriff check

**Constraints**:
- Cannot nominate self or dead players
- Cannot target self with `SAY` actions
- Maximum 1 nomination per multi-action sequence
- All sequences must end with `END_TURN`

### Voting Phase Rules

**Objective**: Vote to eliminate nominated players

**Participants**: All alive players must vote
**Turn Order**: Player 0 → 1 → 2 → ... → 9 (skipping dead)
**Actions Per Turn**: 1 vote action (no `END_TURN`)

**Available Actions**:
- `VOTE PLAYER_X`: Vote against nominated player
- `VOTE_ELIMINATE_ALL`: Vote to eliminate all tied players (3rd round only)
- `VOTE_KEEP_ALL`: Vote to keep all tied players (3rd round only)

**Constraints**:
- Must vote for nominated/tied players only
- Cannot abstain (except dead players giving final speeches)
- No `END_TURN` token in voting actions

**Voting Rounds**:
1. **First Round**: Vote for any nominated player
2. **Second Round**: Vote for tied players from first round  
3. **Third Round**: Vote to eliminate all tied players or not

### Night Phase Rules

**Objective**: Role-specific secret actions

**Participants**: Specific roles only
**Turn Order**: Kill → Don Check → Sheriff Check
**Actions Per Turn**: 1 action + `END_TURN`

#### Night Kill Phase
- **Active Player**: Highest-ranking Mafia (Don > Mafia)
- **Actions**: `KILL PLAYER_X` or `END_TURN`
- **Effect**: Target player eliminated from game

#### Night Don Phase  
- **Active Player**: Don only (if alive)
- **Actions**: `DON_CHECK PLAYER_X` or `END_TURN`
- **Effect**: Learn if target is Sheriff (private result)

#### Night Sheriff Phase
- **Active Player**: Sheriff only (if alive)  
- **Actions**: `SHERIFF_CHECK PLAYER_X` or `END_TURN`
- **Effect**: Learn target's team affiliation (private result)

---

## Error Handling

### Validation Hierarchy

1. **Authentication**: Is it the correct player's turn?
2. **Format Validation**: Are action tokens well-formed?
3. **Legal Action Check**: Is action in server-provided legal actions?
4. **Game Rule Validation**: Does action respect game constraints?
5. **State Consistency**: Can action be applied to current state?

### Error Response Format

```python
ServerResponse(
    success=False,
    player_state=None,
    legal_actions=[],
    game_finished=False, 
    winner=None,
    error_message="Specific error description"
)
```

### Common Error Cases

```python
# Wrong player attempting action
"Not player 3's turn (active: 1)"

# Invalid token sequence
"Action tokens [5, 99, 13] are not well-formed"

# Action not in legal actions list
"Action [VOTE, PLAYER_5] not in provided legal actions"

# Game rule violation  
"Cannot nominate dead player 7"

# Multi-action constraint violation
"Multiple nominations not allowed in single sequence"
```

---

## Implementation Examples

### Complete Server Setup

```python
# Initialize server
server = TokenGameServer(
    seed=42,                                    # Deterministic roles
    log_file="server.log",                     # Server logging
    traffic_log_dir="token_traffic/",          # Client communication logs
    console_quiet=True                         # Reduce console output
)

# Start game
success = server.start_game()
assert success, "Game initialization failed"

# Server ready for client connections
print(f"Server ready - Active player: {server.current_state.active_player}")
```

### Agent Integration Example

```python
class TransformerAgent:
    """Transformer-based agent using server-provided legal actions."""
    
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
    
    def get_action(self, observation_tokens: List[int], legal_actions: List[List[int]]) -> List[int]:
        """
        Generate action using transformer model.
        No game logic needed - just choose from legal actions.
        """
        # Convert tokens to model input
        input_sequence = self.prepare_input(observation_tokens)
        
        # Generate response tokens
        output_tokens = self.model.generate(input_sequence)
        
        # Find closest legal action
        chosen_action = self.find_closest_legal_action(output_tokens, legal_actions)
        
        return chosen_action
    
    def find_closest_legal_action(self, generated_tokens: List[int], 
                                 legal_actions: List[List[int]]) -> List[int]:
        """Match generated tokens to nearest legal action."""
        # Implementation would use similarity metrics to find best match
        # Ensures only legal actions are returned
        return legal_actions[0]  # Simplified for example
```

### Multi-Client Game Loop

```python
def run_game_with_agents(server: TokenGameServer, agents: List[Agent]) -> str:
    """Run complete game with multiple agents."""
    
    while True:
        # Get current active player
        active_player = server.current_state.active_player
        
        # Request state for active player
        response = server.get_player_state(active_player)
        
        if response.game_finished:
            return response.winner
        
        if not response.success or not response.player_state.is_active:
            continue  # Wait for correct player
        
        # Agent chooses action from legal options
        agent = agents[active_player]
        chosen_action = agent.choose_action(response.legal_actions)
        
        # Apply action to server
        action_response = server.apply_player_action(active_player, chosen_action)
        
        if not action_response.success:
            print(f"Action failed: {action_response.error_message}")
            # Agent could retry with different action
```

### Training Data Generation

```python
def generate_training_data(num_games: int = 1000) -> List[Dict]:
    """Generate training data from multiple games."""
    
    training_data = []
    
    for game_id in range(num_games):
        # Use different seeds for variety
        seed = game_id % 2520
        
        server = TokenGameServer(seed=seed)
        server.start_game()
        
        # Run game with random agents
        agents = [RandomAgent() for _ in range(10)]
        winner = run_game_with_agents(server, agents)
        
        # Extract training sequences for each player
        for player_id in range(10):
            final_tokens = server.interface.get_observation_tokens(
                server.current_state, player_id
            )
            
            training_data.append({
                "game_id": game_id,
                "player_id": player_id, 
                "seed": seed,
                "token_sequence": final_tokens,
                "winner": winner,
                "player_role": extract_player_role(final_tokens)
            })
    
    return training_data
```

---

## Conclusion

This specification defines a complete token-based Mafia game server that:

✅ **Implements all Mafia game rules** with proper phase transitions and constraints  
✅ **Provides legal actions to clients** eliminating need for game logic in agents  
✅ **Supports multi-action sequences** for complex day phase gameplay  
✅ **Maintains deterministic seeding** for reproducible training scenarios  
✅ **Enables pure token communication** suitable for transformer model training  
✅ **Handles all error cases** with detailed validation and recovery  

The server-provided legal action system solves the core problem: **agents can focus on strategy selection rather than rule implementation**. This enables rapid development of AI players and supports large-scale transformer training on social deduction gameplay.
