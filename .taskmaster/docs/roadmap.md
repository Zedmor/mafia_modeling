# Mafia AI Training System Roadmap

## Overview

This roadmap describes the step-by-step progression from our current Python Mafia game implementation to a full transformer-based agent training system capable of achieving near-GTO (Game Theory Optimal) performance and defeating human players.

## Current State Analysis

### Existing Python Implementation
- **Game Engine**: Complete game state management in `src/mafia_game/game_state.py`
- **Action System**: Rich action classes (NominationAction, VoteAction, KillAction, etc.) in `src/mafia_game/actions.py`
- **Phase Management**: Turn-based phase system (Day, Voting, Night phases)
- **Agent Framework**: Basic Human and LLM agent implementations
- **Game Logic**: Full Mafia rules with 10 players, roles (Citizen, Sheriff, Mafia, Don)

### Target Architecture
```
Current Python Game → Token-Based Gym Env → Transformer Policy → Self-Play Training → Human-Level AI
```

---

## Phase 1: Token Grammar and Encoding System
**Goal**: Bridge existing Action classes with transformer-compatible 50-token vocabulary

### Phase 1.1: Complete Token Vocabulary (✅ DONE)
- **Status**: Completed - 50-token vocabulary defined in `.taskmaster/docs/token_grammar_specification.md`
- **Tokens**: 13 verbs, 10 player references, color/role tokens, system tokens, phase tokens

### Phase 1.2: Implement Token Encoding/Decoding Utilities (✅ DONE)
**Status**: Completed - Full implementation with comprehensive tests
**Files Completed**:
- `src/mafia_transformer/token_encoder.py` - TokenEncoder class with encode/decode methods ✅
- `test/mafia_transformer/test_token_encoder.py` - Comprehensive test suite ✅

**Implemented Functions**:
```python
def encode_action(action: Action) -> List[int]:          # ✅ DONE
def decode_action(token_ids: List[int], player_index: int) -> Action:  # ✅ DONE  
def encode_sequence(actions: List[Action]) -> List[int]: # ✅ DONE
def decode_sequence(token_ids: List[int], player_indices: List[int]) -> List[Action]:  # ✅ DONE
def validate_action_tokens(token_ids: List[int]) -> bool:  # ✅ DONE
```

**Round-trip Test Results**: All Action classes encode/decode perfectly ✅

**Still Needed**:
```python
def encode_game_state(game_state: CompleteGameState, player_index: int) -> Dict:
    """Convert game state to {public_tokens, private_tokens, legal_mask}"""
    # TODO: Implement in Phase 1.3 alongside legal masking
```

### Phase 1.3: Legal Action Masking Logic
**Definition of Done**: Legal masks always contain at least one valid action, never all-zero
**Integration**: Use existing `get_available_actions()` from `CompleteGameState`

```python
def generate_legal_mask(game_state: CompleteGameState, player_index: int) -> np.ndarray:
    """
    Generate 2D mask [num_verbs, num_targets] where:
    - 1 = legal action combination
    - 0 = illegal action combination
    - Always includes <END_TURN> as fallback
    """
```

---

## Phase 2: Token-Based Gym Wrapper
**Goal**: Create high-performance environment interface for RL training

### Phase 2.1: TokenMafiaEnv Wrapper Class
**Definition of Done**: Gym-compatible interface wrapping CompleteGameState with token observations
**Performance Target**: 10k random games in <30 seconds

```python
class TokenMafiaEnv(gym.Env):
    def __init__(self, seat_rotation=True):
        """
        Args:
            seat_rotation: Always make current speaker PLAYER_0 for permutation invariance
        """
    
    def step(self, action: Tuple[int, int]) -> Tuple[Dict, float, bool, Dict]:
        """
        Args:
            action: (verb_id, target_id) tuple
        Returns:
            observation: {public_tokens, private_tokens, legal_mask}
            reward: +1 win, -1 loss, 0 ongoing
            done: game terminated
            info: debug information
        """
    
    def reset(self) -> Dict:
        """Reset to new game, return initial observation"""
```

### Phase 2.2: Canonical Observation Encoding
**Critical Feature**: Consistent player indexing with relative position information
**Solution**: Use canonical seat ordering (seat 0 → PLAYER_0, seat 1 → PLAYER_1, etc.) but add relative position tokens

**Implementation**:
```python
def encode_observation(game_state: CompleteGameState, observer_seat: int) -> Dict:
    """
    Encode observation with canonical player mapping + relative positions
    """
    obs = {
        "public_tokens": [...],
        "private_tokens": [
            CURRENT_SPEAKER, PLAYER_X,  # Who is speaking now
            YOUR_POSITION, PLAYER_Y,    # Observer's position  
            YOUR_ROLE, SHERIFF,         # Observer's role
            ...
        ],
        "legal_mask": generate_legal_mask(game_state, observer_seat)
    }
    return obs
```

**Benefits**:
- No negative indices - all players stay PLAYER_0 through PLAYER_9
- Transformer learns both relative relationships AND absolute seat strategies
- Can handle "player 3 accuses player 7" regardless of observer position
- **Seat affinity preserved**: Agent learns different strategies for seat 0 vs seat 9
- **Position advantage modeling**: Like poker, late-position players have information advantage
- **Turn order strategy**: Who starts each day phase affects optimal play

**Key Strategic Elements Preserved**:
- Seat 0 speaks first Day 1, Seat 1 starts Day 2, etc. (rotating start)
- Information flow order during day discussion
- Late speakers can react to early accusations/claims
- Mafia coordination depends on speaking order
- Sheriff timing of reveals affected by seat position

### Phase 2.3: Performance Optimization
**Targets**:
- Token encoding/decoding: <1ms per action
- Game simulation: 10k complete games in <30 seconds
- Memory efficiency: Support 1000+ parallel environments

---

## Phase 3: Baseline Agents and Evaluation
**Goal**: Create diverse opponents and measurement frameworks

### Phase 3.1: Token-Based Random and Scripted Agents
```python
class RandomTokenAgent:
    def act(self, obs: Dict) -> Tuple[int, int]:
        """Sample uniformly from legal_mask"""

class AlwaysNominateDay2Agent:
    def act(self, obs: Dict) -> Tuple[int, int]:
        """Strategic scripted behavior using token interface"""
```

### Phase 3.2: Evaluation Framework
**Metrics**:
- Win rate by role (Mafia vs. Red team)
- Elo ratings between agents
- Game length statistics
- Action frequency analysis

---

## Phase 4: Transformer Policy Network
**Goal**: Build the core neural architecture

### Phase 4.1: Transformer Architecture
**Specifications**:
- 6 layers × 256 hidden dimensions × 8 attention heads
- Input: Token sequences up to 100 tokens (full game history)
- Factorized action space: separate verb and target heads
- Parameter count: ~10-50M parameters

```python
class MafiaTransformerPolicy(nn.Module):
    def forward(self, obs_tokens, legal_mask):
        # Process token sequence
        hidden = self.transformer(obs_tokens)
        
        # Factorized policy heads
        verb_logits = self.verb_head(hidden[:, -1])      # [batch, num_verbs]
        target_logits = self.target_head(hidden[:, -1])   # [batch, num_players]
        
        # Apply legal action masking
        verb_logits = verb_logits.masked_fill(~legal_mask.any(dim=1), -1e9)
        target_logits = target_logits + (legal_mask.float() - 1) * 1e9
        
        return verb_logits, target_logits
    
    def get_value(self, obs_tokens):
        """Value head for actor-critic training"""
        hidden = self.transformer(obs_tokens)
        return self.value_head(hidden[:, -1])
```

### Phase 4.2: Legal Action Masking Integration
- Mask illegal actions to -inf before softmax
- Ensure gradients never flow to impossible moves
- Maintain exploration over valid action space

---

## Phase 5: PPO Training Loop
**Goal**: Train agents to beat random opponents (≥80% win rate)

### Phase 5.1: Single-Agent vs. Random Training
**Training Configuration**:
- Algorithm: Proximal Policy Optimization (PPO)
- Batch size: 8k timesteps per update
- Learning rate: 3e-5
- Entropy coefficient: 0.01 (maintain exploration)
- Clip ratio: 0.2

### Phase 5.2: Training Infrastructure
- Distributed environment simulation (64+ parallel games)
- GPU-accelerated policy updates
- Logging: win rates, entropy, value loss, policy loss
- Checkpointing: save models every 100k steps

**Success Criteria**: ≥80% win rate vs. random agent for both Mafia and Red team roles

---

## Phase 6: High-Performance Engine (C++ Migration)
**Goal**: Achieve 200k+ environment steps per second

### Phase 6.1: C++ Game Engine with EnvPool
- Port Python game logic to C++
- Maintain identical API to Python version
- Thread-pool architecture for vectorization
- Python bindings for seamless integration

### Phase 6.2: Performance Validation
- Benchmark: 200k+ steps/s on single workstation
- API compatibility: drop-in replacement for Python version
- Correctness: identical game outcomes for same seed

---

## Phase 7: Self-Play and Historical Opponents
**Goal**: Develop robust strategies through diverse training opponents

### Phase 7.1: Opponent Pool Management
- Freeze checkpoints every 1M training steps
- Maintain diversity: KL divergence > 0.3 between policies
- Prioritized Fictitious Self-Play (PFSP) sampling

### Phase 7.2: League Training Architecture
```
Main_Learner_A (35% of games)
Main_Learner_B (35% of games)  
Historical_Pool (20% of games)
Random_Agent (10% of games)
```

### Phase 7.3: Elo Tracking and Diversity Metrics
- Internal tournament every 100k steps
- Promote/demote based on performance
- Prevent strategy cycling through regularization

---

## Phase 8: Equilibrium Finding (Near-GTO)
**Goal**: Minimize exploitability below 2% threshold

### Phase 8.1: Exploitability Estimation
- Train high-entropy DQN exploiter against main policy
- Target: if exploiter achieves >52% win rate, trigger equilibrium iteration
- Measure distance from Nash equilibrium

### Phase 8.2: NFSP/PSRO Implementation
**Options**:
1. **Neural Fictitious Self-Play (NFSP)**:
   - Average strategy network + best response Q-network
   - Proven convergence in poker-style games

2. **Policy Space Response Oracles (PSRO)**:
   - Population of diverse policies
   - Meta-solver computes equilibrium mixture

3. **Regularized Nash Dynamics (R-NaD)**:
   - Modify PPO updates with uniform-policy regularization
   - Demonstrated success in Stratego (DeepNash)

### Phase 8.3: Convergence Validation
- Final exploitability < 2%
- Robust performance against various strategies
- No regression against random baseline

---

## Phase 9: Language Integration (Optional)
**Goal**: Handle natural language conversation in real games

### Phase 9.1: NLU (Natural Language Understanding)
- Fine-tune BERT/T5 on Mafia chat transcripts
- Classify utterances into dialogue acts: Accuse, Claim, Deny, etc.
- Output: structured tokens feeding into strategic core

### Phase 9.2: Strategic Core Integration
- Intent head on transformer: choose what to communicate
- Input: parsed conversation tokens + game state tokens
- Output: game moves + communication intents

### Phase 9.3: NLG (Natural Language Generation)
- LLM (1-7B parameters) conditioned on intent + game context
- Grounding filter ensures messages match strategy
- Human-like phrasing without strategic weaknesses

---

## Phase 10: Human Evaluation and Deployment
**Goal**: Deploy AI capable of defeating top human players

### Phase 10.1: Human Model Layer
- Lightweight opponent modeling (LSTM/Bayesian filter)
- Online adaptation to individual player tendencies
- Mix ε≈0.1 exploitation with equilibrium strategy

### Phase 10.2: Human Evaluation Metrics
- Win rate ≥70% vs. top-quartile human players
- Turing test: ≥60% of opponents can't identify AI
- No exploitability regression vs. baseline

### Phase 10.3: Production Deployment
- Docker containerization
- API rate limiting and safety filters
- <100ms response time per move
- Compliance with platform terms of service

---

## Technical Architecture Summary

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Game Engine   │    │ Token Interface │    │ Transformer AI  │
│                 │    │                 │    │                 │
│ • C++ Core      │───▶│ • 50-token vocab│───▶│ • 6L×256H×8A    │
│ • 200k+ FPS     │    │ • Legal masking │    │ • Actor-Critic  │
│ • EnvPool       │    │ • Seat rotation │    │ • Factorized    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
┌─────────────────┐    ┌─────────────────┐           │
│ Language Layer  │    │ Training System │           │
│                 │    │                 │           │
│ • NLU Parser    │◀───│ • PPO/NFSP      │◀──────────┘
│ • Intent Head   │    │ • League        │
│ • NLG (LLM)     │    │ • Exploitability│
└─────────────────┘    └─────────────────┘
```

---

## Resource Requirements

### Computational Resources
- **Development**: 1 GPU (A100/H100) + 32-64 CPU cores
- **Training**: 2-4 GPUs for league training
- **Production**: 1 GPU for inference (can use smaller GPU or CPU)

### Timeline Estimates (3-person team)
- **Months 1-2**: Phases 1-4 (Token system + baseline transformer)
- **Months 3-4**: Phases 5-6 (PPO training + C++ optimization)  
- **Months 5-6**: Phases 7-8 (League training + equilibrium)
- **Months 7-8**: Phases 9-10 (Language + human evaluation)

### Storage Requirements
- Training data: ~100GB (millions of self-play games)
- Model checkpoints: ~10GB (historical opponent pool)
- Evaluation logs: ~1GB (Elo tracking, metrics)

---

## Success Milestones

### Phase-by-Phase Success Criteria
1. **Token System**: 100% round-trip accuracy for all Action classes
2. **Environment**: 10k games/30s, clean Gym interface
3. **Baseline**: ≥80% win rate vs. random agent
4. **C++ Engine**: 200k+ steps/s, API compatibility
5. **League**: ≥70% win rate vs. diverse opponent pool
6. **Equilibrium**: <2% exploitability, robust vs. specialists
7. **Language**: 60% human Turing test pass rate
8. **Production**: ≥70% win rate vs. top human players

### Final System Capabilities
- **Strategic**: Near-GTO play with <2% exploitability
- **Adaptive**: Online learning against human opponents
- **Conversational**: Natural language interaction
- **Scalable**: Handles multiple simultaneous games
- **Robust**: Maintains performance across rule variations

---

## Risk Mitigation

### Technical Risks
- **Slow Environment**: Implement C++ early if Python simulation <1k FPS
- **Training Instability**: Use proven hyperparameters from poker/Stratego AIs
- **Overfitting**: Maintain diverse opponent pool throughout training
- **Language Hallucination**: Implement grounding filters for generated text

### Research Risks
- **Strategy Cycling**: Apply R-NaD or maintain historical opponents
- **Exploitability**: Implement multiple equilibrium algorithms as backups
- **Human Evaluation**: Design blind studies with proper statistical analysis

---

## Future Extensions

### Advanced Features
- **Multi-Variant Support**: Different Mafia rule sets and player counts
- **Real-Time Adaptation**: Dynamic opponent modeling during games
- **Explainable AI**: Attention visualization and strategy explanation
- **Tournament Management**: Automated bracket generation and Elo tracking

### Research Directions
- **Transfer Learning**: Apply learned strategies to other social deduction games
- **Coalition Games**: Extend to games with explicit team formation
- **Psychological Modeling**: Incorporate human cognitive biases
- **Fairness**: Ensure AI doesn't exploit unintended human vulnerabilities

---

This roadmap provides a complete pathway from the current Python implementation to a state-of-the-art Mafia AI system. Each phase builds upon the previous ones while maintaining clear success criteria and fallback plans. The modular architecture allows for parallel development and iterative improvement throughout the process.
