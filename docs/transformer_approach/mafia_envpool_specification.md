# Mafia Game Environment Specification for C++ EnvPool

**Version:** 1.0  
**Date:** 2025-01-25  
**Purpose:** Complete specification for implementing a C++ EnvPool environment for the Mafia game based on the Python token interface.

## Table of Contents

1. [Overview](#overview)
2. [Token Vocabulary](#token-vocabulary)
3. [Environment Interface](#environment-interface)
4. [Game State Representation](#game-state-representation)
5. [Action Space](#action-space)
6. [Observation Space](#observation-space)
7. [Legal Action Masking](#legal-action-masking)
8. [Game Phases](#game-phases)
9. [Multi-Action Sequences](#multi-action-sequences)
10. [Deterministic Seeding](#deterministic-seeding)
11. [Implementation Details](#implementation-details)
12. [Example Sequences](#example-sequences)

---

## Overview

The Mafia game environment provides a token-based interface for training transformer models on multi-agent social deduction gameplay. The environment supports 10 players with 4 roles (Citizen, Sheriff, Mafia, Don) across multiple game phases (Day, Voting, Night).

### Key Features

- **Token-based observations**: All game information encoded as discrete tokens
- **Multi-action sequences**: Day phases support sequences of 0-7 actions ending with END_TURN
- **Deterministic seeding**: 2,520 unique role arrangements for reproducible training
- **Voting privacy**: Perfect simultaneous voting without information leakage
- **Chronological sequences**: Each player maintains a complete temporal view of events
- **Legal action masking**: Precise legal move generation for each game state

---

## Token Vocabulary

The environment uses a fixed vocabulary of 58 tokens (IDs 0-57):

### Verb Tokens (Action Types) - IDs 0-12
```cpp
enum TokenID {
    END_TURN = 0,                // End current turn/action sequence
    NOMINATE = 1,                // Nominate player for elimination
    CLAIM_SHERIFF = 2,           // Declare being the Sheriff
    CLAIM_SHERIFF_CHECK = 3,     // Claim result of Sheriff check
    DENY_SHERIFF = 4,            // Deny being the Sheriff
    SAY = 5,                     // Declare player's team affiliation
    VOTE = 6,                    // Vote against nominated player
    VOTE_ELIMINATE_ALL = 7,      // Vote to eliminate all tied players
    VOTE_KEEP_ALL = 8,           // Vote to keep all tied players
    KILL = 9,                    // Kill target player (Mafia action)
    SHERIFF_CHECK = 10,          // Check player's team (Sheriff action)
    DON_CHECK = 11,              // Check if player is Sheriff (Don action)
    YOUR_POSITION = 12           // System token for player position
};
```

### Player Tokens - IDs 13-22
```cpp
PLAYER_0 = 13, PLAYER_1 = 14, ..., PLAYER_9 = 22
```

### Color/Team Tokens - IDs 23-24
```cpp
RED = 23,     // Red team (Citizens/Sheriff)
BLACK = 24    // Black team (Mafia/Don)
```

### Role Tokens - IDs 25-28
```cpp
CITIZEN = 25, SHERIFF = 26, MAFIA = 27, DON = 28
```

### System Tokens - IDs 29-41
```cpp
CHECK_RESULT = 29,     NOMINATED_LIST = 33,    RED_TEAM_WON = 40,
NOT_SHERIFF = 30,      VOTE_REVEALED = 34,     BLACK_TEAM_WON = 41,
MAFIA_TEAM = 31,       ELIMINATED = 35,
YOUR_ROLE = 32,        KILLED = 36,
                       TIE_RESULT = 37,
                       STARTING_PLAYER = 38,
                       GAME_START = 39
```

### Phase Tokens - IDs 42-50
```cpp
DAY_1 = 42, DAY_2 = 43, DAY_3 = 44, DAY_4 = 45, DAY_5 = 46,
NIGHT_1 = 47, NIGHT_2 = 48, NIGHT_3 = 49, NIGHT_4 = 50
```

### Transition Tokens - IDs 51-57
```cpp
VOTING_PHASE_START = 51,   YOUR_TURN = 54,         ELIMINATE_ALL_VOTE = 57
NIGHT_PHASE_START = 52,    NEXT_TURN = 55,         // (Ephemeral - not stored)
DAY_PHASE_START = 53,      REVOTE_PHASE = 56
```

---

## Environment Interface

### Core Methods

```cpp
class MafiaEnvPool {
public:
    // Initialize environment with multiple parallel games
    MafiaEnvPool(int num_envs, int seed_base = 0);
    
    // Reset environments and return initial observations
    std::vector<Observation> reset(const std::vector<int>& env_ids);
    
    // Step environments with actions and return results
    StepResult step(const std::vector<int>& env_ids, 
                   const std::vector<ActionSequence>& actions);
    
    // Get legal action masks for each environment
    std::vector<LegalMask> get_legal_masks(const std::vector<int>& env_ids);
    
    // Check if environments are terminated
    std::vector<bool> is_done(const std::vector<int>& env_ids);
    
    // Get game results for terminated environments
    std::vector<GameResult> get_results(const std::vector<int>& env_ids);
};
```

### Data Structures

```cpp
struct Observation {
    std::vector<int> token_sequence;     // Complete chronological sequence
    int active_player;                   // Currently acting player
    int current_phase;                   // Current game phase ID
    int turn;                           // Game turn number
    bool your_turn;                     // True if this player is active
};

struct ActionSequence {
    std::vector<int> tokens;            // Token sequence (e.g., [NOMINATE, PLAYER_3, END_TURN])
    int player_id;                      // Player performing the action
};

struct LegalMask {
    std::vector<bool> token_mask;       // Mask of size VOCAB_SIZE (58)
    std::vector<std::vector<int>> legal_sequences; // Valid action sequences
};

struct GameResult {
    int winning_team;                   // 0=RED, 1=BLACK, -1=ongoing
    std::vector<float> rewards;        // Per-player rewards
    int final_turn;                     // Turn when game ended
};
```

---

## Game State Representation

### Internal State (per environment)

```cpp
struct GameState {
    // Player states
    std::array<PlayerState, 10> players;
    
    // Game control
    int active_player;          // Current acting player (0-9)
    int current_phase;          // Phase ID (0-5)
    int turn;                  // Game turn (0-10)
    int team_won;              // Winning team (-1=ongoing, 0=RED, 1=BLACK)
    
    // Phase tracking
    int phase_start_player;     // Player who started current phase
    int phase_actions_count;    // Actions taken in current phase
    int voting_round;          // Voting round (0=first, 1=second, 2=third)
    
    // Voting state
    std::vector<int> nominated_players;  // Players nominated for elimination
    std::vector<int> tied_players;       // Players tied in voting
    std::array<int, 10> eliminate_all_votes; // Votes for eliminating all tied players
    
    // Role arrangement seed
    int seed;                   // Deterministic seed (0-2519)
    
    // Chronological sequences (per player)
    std::array<std::vector<int>, 10> player_sequences;
};

struct PlayerState {
    // Public data
    bool alive;                 // Player alive status
    Role role;                 // Player role (CITIZEN, SHERIFF, MAFIA, DON)
    
    // Private data (only visible to this player)
    std::array<int, 10> mafia_team;        // Known mafia members
    std::array<std::array<int, 10>, 5> sheriff_checks;  // Sheriff check results
    std::array<std::array<int, 10>, 5> don_checks;      // Don check results
    
    // Action history
    std::array<std::array<bool, 10>, 5> votes;        // Voting history
    std::array<std::array<bool, 10>, 5> nominations;  // Nomination history
    std::array<std::array<bool, 10>, 5> kills;        // Kill history
};
```

---

## Action Space

### Action Encoding

Actions are represented as variable-length token sequences:

```cpp
// Single-token actions (no targets required)
[END_TURN]              // End turn/action sequence
[CLAIM_SHERIFF]         // Declare being Sheriff
[DENY_SHERIFF]          // Deny being Sheriff
[VOTE_ELIMINATE_ALL]    // Vote to eliminate all tied players
[VOTE_KEEP_ALL]         // Vote to keep all tied players

// Two-token actions (require player target)
[NOMINATE, PLAYER_X]         // Nominate player X
[VOTE, PLAYER_X]             // Vote against player X
[KILL, PLAYER_X]             // Kill player X (Mafia/Don only)
[SHERIFF_CHECK, PLAYER_X]    // Check player X's team (Sheriff only)
[DON_CHECK, PLAYER_X]        // Check if player X is Sheriff (Don only)

// Three-token actions (require player + color)
[CLAIM_SHERIFF_CHECK, PLAYER_X, RED]    // Claim Sheriff check result
[SAY, PLAYER_X, BLACK]                  // Declare player X is on black team
```

### Multi-Action Sequences (Day Phases Only)

Day phases support sequences of 0-7 actions ending with END_TURN:

```cpp
// Examples of valid day phase sequences:
[END_TURN]                                           // 0 actions + END_TURN
[NOMINATE, PLAYER_3, END_TURN]                      // 1 action + END_TURN
[SAY, PLAYER_1, RED, CLAIM_SHERIFF, END_TURN]       // 2 actions + END_TURN
[NOMINATE, PLAYER_4, SAY, PLAYER_2, BLACK, 
 CLAIM_SHERIFF_CHECK, PLAYER_5, RED, END_TURN]      // 3 actions + END_TURN

// Constraints for day phase sequences:
// - Maximum 7 actions before END_TURN
// - Maximum 1 nomination per sequence
// - No duplicate actions within sequence
// - Must end with END_TURN
```

---

## Observation Space

### Token Sequence Format

Each player observes a chronological sequence of tokens representing:

1. **Game initialization**
2. **Private role information** 
3. **Team information** (for Mafia/Don)
4. **Phase transitions**
5. **Public actions** by all players
6. **Private action results** (for acting player)
7. **Turn signaling** (YOUR_TURN, NEXT_TURN)

### Example Observation Sequence

```cpp
// Game start for Player 0 (Sheriff)
[GAME_START, PLAYER_0, YOUR_ROLE, SHERIFF, DAY_1, DAY_PHASE_START, YOUR_TURN, NEXT_TURN]

// After Player 0 nominates Player 3
[GAME_START, PLAYER_0, YOUR_ROLE, SHERIFF, DAY_1, DAY_PHASE_START, 
 PLAYER_0, NOMINATE, PLAYER_3, END_TURN, PLAYER_1, YOUR_TURN, NEXT_TURN]

// During night phase as Sheriff
[..., NIGHT_1, NIGHT_PHASE_START, PLAYER_0, SHERIFF_CHECK, PLAYER_2, RED, END_TURN, ...]
```

### Ephemeral Tokens

- **YOUR_TURN**: Added only for active player's observation
- **NEXT_TURN**: Added only for active player's observation (training signal)
- These tokens are NOT stored in chronological sequences

---

## Legal Action Masking

### Mask Generation

The environment provides two types of legal masks:

#### 1. Token-Level Mask (size 58)
```cpp
std::vector<bool> token_mask(58, false);
// Mark legal tokens as true based on:
// - Current game phase
// - Player role and status
// - Available targets
// - Game rules and constraints
```

#### 2. Sequence-Level Mask
```cpp
std::vector<std::vector<int>> legal_sequences;
// Complete valid action sequences, e.g.:
// [[END_TURN], [NOMINATE, PLAYER_1, END_TURN], [VOTE, PLAYER_3, END_TURN]]
```

### Phase-Specific Constraints

```cpp
// Day Phase
- All alive players can: NOMINATE, CLAIM_SHERIFF, DENY_SHERIFF, SAY, CLAIM_SHERIFF_CHECK
- Multi-action sequences allowed (0-7 actions + END_TURN)
- Maximum 1 nomination per sequence
- Cannot target self or dead players

// Voting Phase  
- All alive players must: VOTE (for nominated/tied players)
- Single action only: [VOTE, PLAYER_X] (no END_TURN in voting)
- No abstention allowed (except dead players giving speeches)

// Night Kill Phase
- Only Mafia/Don can: KILL
- Single action: [KILL, PLAYER_X, END_TURN] or [END_TURN]

// Night Don Phase
- Only Don can: DON_CHECK  
- Single action: [DON_CHECK, PLAYER_X, END_TURN] or [END_TURN]

// Night Sheriff Phase
- Only Sheriff can: SHERIFF_CHECK
- Single action: [SHERIFF_CHECK, PLAYER_X, END_TURN] or [END_TURN]
```

---

## Game Phases

### Phase Progression

```cpp
enum Phase {
    DAY_PHASE = 0,           // Discussion and nominations
    VOTING_PHASE = 1,        // Vote on nominated players
    NIGHT_KILL_PHASE = 2,    // Mafia kills
    NIGHT_DON_PHASE = 3,     // Don checks
    NIGHT_SHERIFF_PHASE = 4, // Sheriff checks
    END_PHASE = 5            // Process results, advance turn
};

// Phase transitions:
// DAY → VOTING → NIGHT_KILL → NIGHT_DON → NIGHT_SHERIFF → END → DAY (next turn)
```

### Turn Management

```cpp
// Day Phase: Round-robin through all alive players
// Each player gets one turn with 0-7 actions + END_TURN

// Voting Phase: All alive players vote simultaneously
// Players vote in order 0→1→2...→9, skipping dead players
// Voting privacy: no player sees others' votes until round completion

// Night Phases: Role-specific single actions
// Only the relevant role holder acts (Mafia/Don, Don, Sheriff)
```

---

## Multi-Action Sequences

### Day Phase Mechanics

Day phases uniquely support multi-action sequences where players can perform multiple actions before ending their turn:

#### Sequence Rules
```cpp
// Valid sequence patterns:
[END_TURN]                                    // End turn immediately
[ACTION1, END_TURN]                          // Single action + end
[ACTION1, ACTION2, END_TURN]                 // Two actions + end
[ACTION1, ACTION2, ACTION3, ..., END_TURN]   // Up to 7 actions + end

// Constraints:
- Maximum 7 actions before END_TURN
- Maximum 1 NOMINATE action per sequence  
- No duplicate actions within sequence
- All actions must be legal day phase actions
- Sequence must end with END_TURN
```

#### Implementation Considerations
```cpp
// For C++ implementation:
class ActionParser {
public:
    // Parse multi-action sequence into individual actions
    std::vector<Action> parseSequence(const std::vector<int>& tokens);
    
    // Validate multi-action sequence
    bool validateSequence(const std::vector<int>& tokens, 
                         const GameState& state, int player_id);
    
    // Count specific action types in sequence
    int countNominations(const std::vector<int>& tokens);
    int countActions(const std::vector<int>& tokens); // Excludes END_TURN
};
```

---

## Deterministic Seeding

### Role Arrangement System

The environment supports 2,520 unique role arrangements for deterministic training:

```cpp
// Role composition (fixed):
// 6 Citizens, 1 Sheriff, 2 Mafia, 1 Don = 10 total players

// Mathematical calculation:
// Choose positions for: 1 Don × 2 Mafia × 1 Sheriff from 10 positions
// = C(10,1) × C(9,2) × C(7,1) × C(6,6)
// = 10 × 36 × 7 × 1 = 2,520 arrangements

class RoleArrangementGenerator {
public:
    // Generate all 2,520 possible arrangements
    static std::vector<std::array<Role, 10>> generateAllArrangements();
    
    // Get specific arrangement by seed
    static std::array<Role, 10> getArrangement(int seed);
    
    // Validate seed range
    static bool isValidSeed(int seed) { return seed >= 0 && seed < 2520; }
};
```

### Seed Usage
```cpp
// Environment initialization:
MafiaEnvPool env(num_envs, seed_base);

// Each environment uses: seed = (seed_base + env_id) % 2520
// This ensures deterministic yet varied training scenarios
```

---

## Implementation Details

### Memory Layout

```cpp
// Efficient memory layout for parallel environments
struct EnvBatch {
    std::vector<GameState> states;           // Per-environment game states
    std::vector<std::vector<int>> observations; // Per-player observations
    std::vector<LegalMask> legal_masks;      // Per-environment legal masks
    std::vector<bool> done_flags;            // Per-environment termination
};
```

### Performance Optimizations

```cpp
// Token sequence management
class TokenSequencePool {
    // Pre-allocated memory pools for token sequences
    // Avoid dynamic allocation during gameplay
    
public:
    std::vector<int>& getSequence(int max_length);
    void returnSequence(std::vector<int>& sequence);
};

// Legal mask caching
class LegalMaskCache {
    // Cache legal masks by (phase, player_role, alive_players) state
    // Significant speedup for repeated game states
    
public:
    const LegalMask& getMask(const GameState& state, int player_id);
};
```

### Thread Safety

```cpp
// Environment isolation
// Each environment operates independently with no shared mutable state
// Safe for parallel execution across multiple threads

// Immutable data sharing
// Token vocabulary, role arrangements, and legal action templates
// can be shared across all environments safely
```

---

## Example Sequences

### Complete Game Flow Example

```cpp
// Game Initialization (Player 0 - Sheriff)
[GAME_START, PLAYER_0, YOUR_ROLE, SHERIFF, DAY_1, DAY_PHASE_START, YOUR_TURN, NEXT_TURN]

// Day Phase Actions
// Player 0 multi-action sequence:
[CLAIM_SHERIFF, SAY, PLAYER_3, BLACK, NOMINATE, PLAYER_3, END_TURN]

// Updated observation after Player 0's turn:
[GAME_START, PLAYER_0, YOUR_ROLE, SHERIFF, DAY_1, DAY_PHASE_START, 
 PLAYER_0, CLAIM_SHERIFF, SAY, PLAYER_3, BLACK, NOMINATE, PLAYER_3, END_TURN,
 PLAYER_1]  // Next player's turn

// Voting Phase Transition
[..., VOTING_PHASE_START, PLAYER_0, YOUR_TURN, NEXT_TURN]

// Voting Action (Player 0 votes for Player 3)
[VOTE, PLAYER_3]  // Note: No END_TURN in voting phase

// Night Phase (Sheriff Check)
[..., NIGHT_1, NIGHT_PHASE_START, PLAYER_0, SHERIFF_CHECK, PLAYER_2, RED, END_TURN, ...]

// Game End
[..., RED_TEAM_WON]
```

### Multi-Action Sequence Validation

```cpp
// Valid day phase sequences:
✅ [END_TURN]
✅ [NOMINATE, PLAYER_3, END_TURN]  
✅ [CLAIM_SHERIFF, SAY, PLAYER_1, RED, END_TURN]
✅ [SAY, PLAYER_2, BLACK, CLAIM_SHERIFF_CHECK, PLAYER_4, RED, NOMINATE, PLAYER_5, END_TURN]

// Invalid sequences:
❌ [NOMINATE, PLAYER_3]                    // Missing END_TURN
❌ [NOMINATE, PLAYER_1, NOMINATE, PLAYER_2, END_TURN]  // Multiple nominations
❌ [VOTE, PLAYER_3, END_TURN]              // VOTE not allowed in day phase
❌ [CLAIM_SHERIFF, CLAIM_SHERIFF, END_TURN] // Duplicate actions
❌ [SAY, PLAYER_1, RED, SAY, PLAYER_2, BLACK, SAY, PLAYER_3, RED, 
    SAY, PLAYER_4, BLACK, SAY, PLAYER_5, RED, SAY, PLAYER_6, BLACK,
    SAY, PLAYER_7, RED, SAY, PLAYER_8, BLACK, END_TURN]  // Too many actions (8 > 7)
```

---

## Integration Notes

### Transformer Training Considerations

1. **Sequence Length**: Token sequences can grow to 1000+ tokens per game
2. **Context Window**: Plan for sequences up to 2048 tokens for full games
3. **Action Prediction**: Model should predict complete action sequences for day phases
4. **Legal Masking**: Essential for preventing invalid actions during inference
5. **Multi-Agent Learning**: Each player has unique observations and rewards

### EnvPool Integration

```cpp
// Expected EnvPool interface compatibility
class MafiaEnvSpec {
public:
    static constexpr int kMaxPlayers = 10;
    static constexpr int kVocabSize = 58;
    static constexpr int kMaxSequenceLength = 2048;
    static constexpr int kMaxActionLength = 15;  // Max tokens per action sequence
    
    using ActionType = std::vector<int>;
    using ObservationType = std::vector<int>;
    using RewardType = float;
    using InfoType = std::map<std::string, std::variant<int, float, std::string>>;
};
```

This specification provides a complete foundation for implementing the Mafia game environment in C++ for EnvPool, maintaining full compatibility with the Python token interface while optimizing for parallel training performance.
