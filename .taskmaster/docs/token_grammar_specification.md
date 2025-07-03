# Mafia Game Token Grammar and System Specification

## Overview

This document defines the complete token grammar system for the transformer-based Mafia game AI, as specified in the PRD. The system uses a fixed vocabulary of ≤40 verb tokens, 10 player argument tokens, and phase tokens to represent all possible game actions and states.

## Token Vocabulary

### Verb Tokens (Action Types)

| Token ID | Token Name | Description | Valid Phases | Team Restriction |
|----------|------------|-------------|--------------|------------------|
| 0 | `<END_TURN>` | End player's turn / pass | All | Both |
| 1 | `<NOMINATE>` | Nominate player for elimination | Day | Both |
| 2 | `<CLAIM_SHERIFF>` | Declare you are the sheriff | Day | Both |
| 3 | `<CLAIM_SHERIFF_CHECK>` | Claim sheriff check result | Day | Both |
| 4 | `<DENY_SHERIFF>` | Declare you are not sheriff | Day | Both |
| 5 | `<SAY>` | Declare player's team affiliation | Day | Both |
| 6 | `<VOTE>` | Vote against nominated player | Voting | Both |
| 7 | `<VOTE_ELIMINATE_ALL>` | Vote to eliminate all tied players | Voting | Both |
| 8 | `<VOTE_KEEP_ALL>` | Vote against eliminating tied players | Voting | Both |
| 9 | `<KILL>` | Eliminate player during night | Night_Kill | Black only |
| 10 | `<SHERIFF_CHECK>` | Check player's team (night action) | Night_Sheriff | Red only |
| 11 | `<DON_CHECK>` | Check if player is sheriff | Night_Don | Black only |
| 12 | `<YOUR_POSITION>` | System declares your table position | Setup | Both |

### Argument Tokens (Player References)

| Token ID | Token Name | Description |
|----------|------------|-------------|
| 13 | `<PLAYER_0>` | Reference to player 0 |
| 14 | `<PLAYER_1>` | Reference to player 1 |
| 15 | `<PLAYER_2>` | Reference to player 2 |
| 16 | `<PLAYER_3>` | Reference to player 3 |
| 17 | `<PLAYER_4>` | Reference to player 4 |
| 18 | `<PLAYER_5>` | Reference to player 5 |
| 19 | `<PLAYER_6>` | Reference to player 6 |
| 20 | `<PLAYER_7>` | Reference to player 7 |
| 21 | `<PLAYER_8>` | Reference to player 8 |
| 22 | `<PLAYER_9>` | Reference to player 9 |

### Color Tokens

| Token ID | Token Name | Description |
|----------|------------|-------------|
| 23 | `<RED>` | Red team / innocent |
| 24 | `<BLACK>` | Black team / mafia |

### Role Tokens

| Token ID | Token Name | Description |
|----------|------------|-------------|
| 25 | `<CITIZEN>` | Citizen role (innocent team) |
| 26 | `<SHERIFF>` | Sheriff role (innocent team) |
| 27 | `<MAFIA>` | Mafia role (mafia team) |
| 28 | `<DON>` | Don role (mafia team) |

### System/Environment Tokens (Read-Only)

| Token ID | Token Name | Description |
|----------|------------|-------------|
| 29 | `<CHECK_RESULT>` | System token indicating check result follows |
| 30 | `<NOT_SHERIFF>` | Target player is not sheriff (Don check result) |
| 31 | `<MAFIA_TEAM>` | System token indicating mafia team member follows |
| 32 | `<YOUR_ROLE>` | System declares your role |
| 33 | `<NOMINATED_LIST>` | System announces nominated players for voting |
| 34 | `<VOTE_REVEALED>` | System reveals vote results (who voted for whom) |
| 35 | `<ELIMINATED>` | System announces player elimination |
| 36 | `<TIE_RESULT>` | System announces tie in voting |
| 37 | `<STARTING_PLAYER>` | System announces who starts the day |
| 38 | `<GAME_START>` | System announces game beginning |
| 39 | `<RED_TEAM_WON>` | System announces red team victory |
| 40 | `<BLACK_TEAM_WON>` | System announces black team victory |

### Phase Tokens (Game State)

| Token ID | Token Name | Description |
|----------|------------|-------------|
| 41 | `<DAY_1>` | Day phase, turn 1 |
| 42 | `<DAY_2>` | Day phase, turn 2 |
| 43 | `<DAY_3>` | Day phase, turn 3 |
| 44 | `<DAY_4>` | Day phase, turn 4 |
| 45 | `<DAY_5>` | Day phase, turn 5 |
| 46 | `<NIGHT_1>` | Night phase, turn 1 |
| 47 | `<NIGHT_2>` | Night phase, turn 2 |
| 48 | `<NIGHT_3>` | Night phase, turn 3 |
| 49 | `<NIGHT_4>` | Night phase, turn 4 |

## Grammar Structure

### Sequence Format

Each game turn is represented as a token sequence:
```
<PHASE_TOKEN> <SPEAKER_TOKEN> <ACTION_TOKENS> <END_TURN>
```

### Action Grammar Rules

1. **Verb-Argument Structure**: Most actions follow the pattern `<VERB> <TARGET>`
   - Example: `<NOMINATE> <PLAYER_5>` (nominate player 5)
   - Example: `<VOTE> <PLAYER_3>` (vote against player 3)

2. **Complex Actions**: Some actions require additional context
   - `<CLAIM_SHERIFF_CHECK> <PLAYER_X> <RED>` (claim you checked player X as innocent)
   - `<CLAIM_SHERIFF_CHECK> <PLAYER_X> <BLACK>` (claim you checked player X as mafia)
   - `<SAY> <PLAYER_X> <RED>` (declare player X is innocent)
   - `<SAY> <PLAYER_X> <BLACK>` (declare player X is mafia)

3. **No-Argument Actions**: Some verbs require no target
   - `<END_TURN>` (end turn/pass)
   - `<DENY_SHERIFF>` (deny being sheriff)
   - `<VOTE_ELIMINATE_ALL>` (vote to eliminate all tied players)
   - `<VOTE_KEEP_ALL>` (vote to keep all tied players)

4. **System Tokens**: Environment-provided information (read-only)
   - `<YOUR_POSITION> <PLAYER_3>` (you are sitting at position 3)
   - `<YOUR_ROLE> <SHERIFF>` (your role is sheriff)
   - `<MAFIA_TEAM> <PLAYER_2> <PLAYER_7>` (your mafia teammates are players 2 and 7)
   - `<STARTING_PLAYER> <PLAYER_1>` (player 1 starts this day phase)
   - `<CHECK_RESULT> <PLAYER_X> <RED>` (sheriff check result: player X is innocent)
   - `<CHECK_RESULT> <PLAYER_X> <BLACK>` (sheriff check result: player X is mafia)
   - `<CHECK_RESULT> <PLAYER_X> <SHERIFF>` (don check result: player X is sheriff)
   - `<CHECK_RESULT> <PLAYER_X> <NOT_SHERIFF>` (don check result: player X is not sheriff)
   - `<NOMINATED_LIST> <PLAYER_1> <PLAYER_5> <PLAYER_7>` (players 1, 5, 7 are nominated for voting)
   - `<VOTE_REVEALED> <PLAYER_2> <VOTE> <PLAYER_1>` (player 2 voted for player 1)
   - `<ELIMINATED> <PLAYER_5>` (player 5 has been eliminated)
   - `<TIE_RESULT> <PLAYER_1> <PLAYER_7>` (tie between players 1 and 7, proceeding to revote)

### Observation Encoding

The transformer receives observations in this format:
```
obs = {
    "public_tokens": [<DAY_2>, <PLAYER_1>, <NOMINATE>, <PLAYER_5>, <END_TURN>, ...],
    "private_tokens": [<YOUR_ROLE>, <SHERIFF>, <MAFIA_TEAM>, <PLAYER_2>, <PLAYER_7>, ...],
    "legal_mask": [[1,0,1,1,0,0,0,1,0,0], [1,1,0,0,0,1,1,1,1,1], ...]  # [verbs x targets]
}
```

## Legal Action Masking

### Mask Structure

The legal_mask is a 2D array with shape `[num_verbs, num_targets]` where:
- `legal_mask[verb_id][target_id] = 1` if the action is legal
- `legal_mask[verb_id][target_id] = 0` if the action is illegal

### Masking Rules by Phase

#### Day Phase
- All players can use: `<NOMINATE>`, `<CLAIM_SHERIFF_CHECK>`, `<DENY_SHERIFF>`, `<SAY>`
- Cannot target self with: `<NOMINATE>`, `<SAY>`
- Cannot target dead players with any action
- Cannot use night-only actions: `<KILL>`, `<SHERIFF_CHECK>`, `<DON_CHECK>`
- `<CLAIM_SHERIFF_CHECK>` and `<SAY>` require both player target and color token

#### Voting Phase
- Only `<VOTE>` allowed for nominated players (first round) or tied players (second round)
- `<VOTE_ELIMINATE_ALL>` and `<VOTE_KEEP_ALL>` only in third round
- Cannot vote for non-nominated/non-tied players

#### Night Kill Phase
- Only mafia/don can use `<KILL>`
- Cannot kill dead players
- Cannot kill self

#### Night Don Phase
- Only don can use `<DON_CHECK>`
- Cannot check dead players
- Cannot check self

#### Night Sheriff Phase
- Only sheriff can use `<SHERIFF_CHECK>`
- Cannot check dead players
- Cannot check self

### Critical Constraint: Never All-Zero

**The legal_mask must never become all-zero.** This is enforced by:

1. **Always include `<END_TURN>`**: This action is always legal in every phase
2. **Fallback actions**: If no other actions are legal, `<END_TURN>` ensures at least one option
3. **Validation**: Before each turn, verify `legal_mask.sum() > 0`

## Token Encoding and Decoding

### Encoding Process

```python
def encode_action(verb: str, target: Optional[str] = None) -> List[int]:
    """Convert action to token IDs"""
    verb_id = VERB_TO_ID[verb]
    if target is None:
        return [verb_id]
    target_id = PLAYER_TO_ID[target]
    return [verb_id, target_id]

def encode_observation(public_history: List[Action], 
                      private_info: Dict, 
                      current_phase: str,
                      turn: int) -> Dict:
    """Convert game state to token sequence"""
    tokens = [PHASE_TO_ID[f"{current_phase}_{turn}"]]
    
    for action in public_history:
        tokens.extend(encode_action(action.verb, action.target))
        tokens.append(END_TURN_TOKEN)
    
    return {
        "public_tokens": tokens,
        "private_tokens": encode_private_info(private_info),
        "legal_mask": generate_legal_mask(current_phase, private_info)
    }
```

### Decoding Process

```python
def decode_action(token_ids: List[int]) -> Action:
    """Convert token IDs back to action"""
    verb_id = token_ids[0]
    verb = ID_TO_VERB[verb_id]
    
    if len(token_ids) > 1:
        target_id = token_ids[1]
        target = ID_TO_PLAYER[target_id]
        return Action(verb=verb, target=target)
    
    return Action(verb=verb)

def decode_sequence(token_sequence: List[int]) -> List[Action]:
    """Convert full token sequence to actions"""
    actions = []
    i = 1  # Skip phase token
    
    while i < len(token_sequence):
        if token_sequence[i] == END_TURN_TOKEN:
            i += 1
            continue
            
        # Read verb
        verb_id = token_sequence[i]
        i += 1
        
        # Check if verb requires target
        if verb_requires_target(verb_id) and i < len(token_sequence):
            target_id = token_sequence[i]
            i += 1
            actions.append(decode_action([verb_id, target_id]))
        else:
            actions.append(decode_action([verb_id]))
    
    return actions
```

## Integration with Current Implementation

### Mapping Current Actions to Tokens

| Current Action Class | Token Equivalent | Example |
|---------------------|------------------|---------|
| `NominationAction(player_index, target)` | `<NOMINATE> <PLAYER_X>` | `<NOMINATE> <PLAYER_5>` |
| `VoteAction(player_index, target)` | `<VOTE> <PLAYER_X>` | `<VOTE> <PLAYER_3>` |
| `KillAction(player_index, target)` | `<KILL> <PLAYER_X>` | `<KILL> <PLAYER_7>` |
| `SheriffCheckAction(player_index, target)` | `<SHERIFF_CHECK> <PLAYER_X>` | `<SHERIFF_CHECK> <PLAYER_2>` |
| `DonCheckAction(player_index, target)` | `<DON_CHECK> <PLAYER_X>` | `<DON_CHECK> <PLAYER_4>` |
| `SheriffDeclarationAction(player_index, True)` | `<CLAIM_SHERIFF>` | `<CLAIM_SHERIFF>` |
| `SheriffDeclarationAction(player_index, False)` | `<DENY_SHERIFF>` | `<DENY_SHERIFF>` |
| `PublicSheriffDeclarationAction(player, target, RED)` | `<CLAIM_SHERIFF_CHECK> <PLAYER_X> <RED>` | `<CLAIM_SHERIFF_CHECK> <PLAYER_3> <RED>` |
| `PublicSheriffDeclarationAction(player, target, BLACK)` | `<CLAIM_SHERIFF_CHECK> <PLAYER_X> <BLACK>` | `<CLAIM_SHERIFF_CHECK> <PLAYER_3> <BLACK>` |
| `EliminateAllNominatedVoteAction(player, True)` | `<VOTE_ELIMINATE_ALL>` | `<VOTE_ELIMINATE_ALL>` |
| `EliminateAllNominatedVoteAction(player, False)` | `<VOTE_KEEP_ALL>` | `<VOTE_KEEP_ALL>` |
| `NullAction(player_index)` | `<END_TURN>` | `<END_TURN>` |

### Transformer Policy Head Structure

The policy network outputs two logit vectors:
1. **Verb logits**: `[num_verbs]` - probability distribution over action types
2. **Target logits**: `[num_players]` - probability distribution over player targets

```python
class MafiaTransformerPolicy(nn.Module):
    def forward(self, obs_tokens, legal_mask):
        # Transform input tokens
        hidden = self.transformer(obs_tokens)
        
        # Policy heads
        verb_logits = self.verb_head(hidden[:, -1])  # Last token
        target_logits = self.target_head(hidden[:, -1])
        
        # Apply legal action masking
        verb_logits = verb_logits.masked_fill(~legal_mask.any(dim=1), -1e9)
        target_logits = target_logits + (legal_mask.float() - 1) * 1e9
        
        return verb_logits, target_logits
```

## Extensibility and Future Enhancements

### Adding New Actions

To add new actions (e.g., `<INTERRUPT_CLAIM>`):
1. Add new verb token to vocabulary
2. Update legal masking rules
3. Extend encoding/decoding functions
4. No retraining required - just expand the verb head by one neuron

### Language Integration

The token system is designed to support future natural language integration:
- Tokens represent semantic actions, not surface forms
- NLU can map free text to token sequences
- NLG can render token sequences as natural language
- Core strategy remains unchanged

## Validation and Testing

### Unit Tests Required

1. **Token Encoding/Decoding**:
   - Round-trip encoding/decoding preserves action semantics
   - Invalid token combinations are rejected
   - All current actions can be represented

2. **Legal Masking**:
   - Mask never becomes all-zero
   - Illegal actions are properly masked in each phase
   - Role restrictions are enforced

3. **Sequence Processing**:
   - Multi-action turns are properly tokenized
   - Phase transitions update masks correctly
   - History context is preserved

### Integration Tests

1. **Backward Compatibility**:
   - All existing game scenarios can be tokenized
   - Random agents work with new token system
   - Game outcomes remain consistent

2. **Performance**:
   - Token encoding/decoding is fast (<1ms per action)
   - Legal mask generation is efficient
   - Memory usage remains reasonable

## Conclusion

This token grammar system provides a complete, extensible foundation for transformer-based Mafia game AI. The fixed vocabulary ensures efficient training, the factorized verb-target structure enables generalization, and the legal masking system guarantees valid gameplay. The design supports both current strategic AI development and future natural language integration.
