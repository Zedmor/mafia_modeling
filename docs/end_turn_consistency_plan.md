# END_TURN Token Consistency Fix Plan

## Problem Analysis

The current implementation has inconsistent END_TURN token handling:

### Current Inconsistent Behavior:
1. **Day actions** (SAY, CLAIM_SHERIFF_CHECK, NOMINATE): Can chain multiple actions, require explicit `<END_TURN>`
2. **Night actions** (SHERIFF_CHECK, DON_CHECK, KILL): Single action, server auto-completes turn
3. **Voting actions** (VOTE): Single action, server auto-completes turn

### Training Impact:
- **Context-dependent learning**: Model must learn "sometimes I need END_TURN, sometimes I don't"
- **Inconsistent legal actions**: Some action lists include END_TURN variants, others don't
- **Confusion potential**: Model might add END_TURN when it shouldn't or miss it when needed

## Solution: Always Require END_TURN

### New Consistent Protocol:
**Every action sequence MUST end with `<END_TURN>`:**
- `<NOMINATE> <PLAYER_5> <END_TURN>`
- `<SHERIFF_CHECK> <PLAYER_3> <END_TURN>`  
- `<VOTE> <PLAYER_7> <END_TURN>`
- `<END_TURN>` (for passing without action)

### Benefits:
- **Complete consistency**: Every turn ends the same way
- **Clear boundaries**: Explicit turn completion for training
- **Simpler legal actions**: All action lists include END_TURN requirement
- **Transformer-friendly**: Model always knows to end with END_TURN

## Implementation Plan

### Phase 1: Update Token Encoder
- **File**: `src/mafia_transformer/token_encoder.py`
- **Change**: All `encode_action()` methods must return sequences ending with END_TURN
- **Impact**: Currently some actions (like SHERIFF_CHECK, VOTE) don't include END_TURN

### Phase 2: Update Token Game Interface
- **File**: `src/mafia_transformer/token_game_interface.py`
- **Change**: `get_legal_actions()` must always include END_TURN in action sequences
- **Change**: `apply_action()` must expect all client actions to end with END_TURN
- **Impact**: Legal action generation logic needs updating

### Phase 3: Update Server Implementation
- **File**: `src/mafia_transformer/token_game_server.py`
- **Change**: Server must expect all client actions to end with END_TURN
- **Change**: Validation should reject actions not ending with END_TURN
- **Impact**: Client-server protocol validation

### Phase 4: Update Tests
- **Files**: All test files using token actions
- **Change**: Update expected action sequences to include END_TURN
- **Impact**: Existing tests will need updating

## Detailed Implementation Steps

### Step 1: Fix Token Encoder
```python
# Current inconsistent behavior:
def encode_action(self, action: Action) -> List[int]:
    if isinstance(action, NullAction):
        return [TokenID.END_TURN]  # ✅ Already correct
    elif isinstance(action, NominationAction):
        return [TokenID.NOMINATE, player_index_to_token(action.target_player)]  # ❌ Missing END_TURN
    elif isinstance(action, VoteAction):
        return [TokenID.VOTE, player_index_to_token(action.target_player)]  # ❌ Missing END_TURN

# Fixed consistent behavior:
def encode_action(self, action: Action) -> List[int]:
    if isinstance(action, NullAction):
        return [TokenID.END_TURN]
    elif isinstance(action, NominationAction):
        return [TokenID.NOMINATE, player_index_to_token(action.target_player), TokenID.END_TURN]
    elif isinstance(action, VoteAction):
        return [TokenID.VOTE, player_index_to_token(action.target_player), TokenID.END_TURN]
    # ... Apply to all action types
```

### Step 2: Fix Legal Action Generation
```python
# Update get_legal_actions() to ensure all actions end with END_TURN
def get_legal_actions(self, token_state: TokenGameState) -> List[List[int]]:
    # Get actions from game engine
    available_actions = token_state._internal_state.get_available_actions()
    
    # Convert to token sequences - ALL must end with END_TURN
    legal_action_tokens = []
    for action in available_actions:
        action_tokens = encode_action(action)  # Now guaranteed to end with END_TURN
        # Additional validation to ensure consistency
        if action_tokens[-1] != TokenID.END_TURN.value:
            raise ValueError(f"Action {action_tokens} must end with END_TURN")
        legal_action_tokens.append(action_tokens)
    
    return legal_action_tokens
```

### Step 3: Fix Token Decoding
```python
# Update decode_action() to handle END_TURN in all sequences
def decode_action(self, token_ids: List[int], player_index: int) -> Action:
    if not token_ids:
        raise ValueError("Empty token sequence")
    
    # Expect all actions to end with END_TURN
    if token_ids[-1] != TokenID.END_TURN.value:
        raise ValueError(f"Action sequence must end with END_TURN: {token_ids}")
    
    # Remove END_TURN for processing
    action_tokens = token_ids[:-1]
    
    if not action_tokens:  # Just END_TURN
        return NullAction(player_index)
    
    verb_token = TokenID(action_tokens[0])
    
    if verb_token == TokenID.NOMINATE:
        if len(action_tokens) < 2:
            raise ValueError("NOMINATE requires target player")
        target_player = token_to_player_index(TokenID(action_tokens[1]))
        return NominationAction(player_index, target_player)
    # ... Handle all action types consistently
```

### Step 4: Update Validation
```python
# Update validate_action_tokens() to require END_TURN
def validate_action_tokens(self, token_ids: List[int]) -> bool:
    if not token_ids:
        return False
    
    # Must end with END_TURN
    if token_ids[-1] != TokenID.END_TURN.value:
        return False
    
    # Validate the action part (excluding END_TURN)
    action_tokens = token_ids[:-1]
    
    if not action_tokens:  # Just END_TURN is valid (pass turn)
        return True
    
    # Validate verb and arguments
    try:
        verb_token = TokenID(action_tokens[0])
    except ValueError:
        return False
    
    # ... Rest of validation logic
```

## Testing Strategy

### Phase 1: Unit Tests
- Test `TokenEncoder.encode_action()` for all action types
- Verify all encoded actions end with END_TURN
- Test `TokenEncoder.decode_action()` with new format

### Phase 2: Integration Tests
- Update existing token game interface tests
- Test legal action generation consistency
- Test client-server communication with new protocol

### Phase 3: UAT Validation
- Run client-server UAT with updated protocol
- Verify token traffic logs show consistent END_TURN usage
- Confirm game completion works correctly

## Migration Considerations

### Backward Compatibility
- **Breaking change**: Existing saved games/sequences may be incompatible
- **Test data**: Existing test sequences need updating
- **Documentation**: Update all examples to show new format

### Rollout Plan
1. Implement changes in development environment
2. Update all tests to use new format
3. Run comprehensive UAT to validate
4. Update documentation and examples
5. Deploy to production

## Expected Outcome

After implementation:
- **100% consistent END_TURN usage**: Every client action ends with END_TURN
- **Simplified transformer training**: Model always knows to end with END_TURN
- **Clear turn boundaries**: Explicit completion signal for all actions
- **Reduced confusion**: No context-dependent ending behavior

## Risk Mitigation

### Potential Issues
1. **Performance impact**: Slightly longer token sequences
2. **Migration effort**: All existing code needs updating
3. **Test maintenance**: Comprehensive test updates required

### Mitigation Strategies
1. **Performance**: Minimal impact (1 extra token per action)
2. **Migration**: Systematic file-by-file updates with validation
3. **Testing**: Automated test generation for new format
