# Project PRD – Transformer-Based Self-Play AI for 10-Player Mafia

---

## 1 Why this document exists  
A single, authoritative description of **what we are building, why, how we know we’re done, and which milestones unlock the next engineering phase**.  
It merges:  
* the formal **game rules** (`docs/game_description.txt`)  
* the design dialogue with o3 (`docs/transformer_approach/dialogue_o3.txt`)  
* industry patterns distilled from AlphaStar, Libratus, DeepNash, Cicero, etc.

---

## 2 Problem statement  
We want an AI that can **play 10-seat, tournament-rule Mafia** (3 black / 7 red) at or above strong-human level without hand-crafted heuristics.  
Constraints & goals:  

| ID | Requirement | Notes |
|----|-------------|-------|
| R-G1 | Zero external data – start from scratch, learn via self-play | Mirrors AlphaGo Zero path |
| R-G2 | Must beat a random-legal agent ≥ 80 % both roles | “Beat-random” sanity gate |
| R-G3 | Long-term: exploitability proxy < 2 % | Near-GTO |
| R-G4 | Latency < 100 ms / decision (GPU inference allowed) | Online play |
| R-G5 | Modular natural language layer attachable later | Cicero-style roadmap |
| R-G6 | Reproducible from public repo + 1 GPU workstation | Open research ethos |

---

## 3 High-level solution  
1. **Fast game engine** (C++ EnvPool backend) exposing `observation={public_tokens, private_tokens, legal_mask}`.  
2. **Transformer policy+value net** (6 L × 256 H hidden, shared for both teams).  
3. **Self-play PPO to beat random**, then **mini-league PFSP** for diversity.  
4. Optional **NFSP / PSRO layer** to drive exploitability →0.  
5. Future: **NLU encoder + intent head + NLG LLM wrapper**.

---

## 4 Milestones & “Definition of Done”

| Phase | DoD checklist | Complexity (1-5) | Target date |
|-------|---------------|------------------|-------------|
| **0 Rules Freeze** | Signed markdown of final token grammar & game spec | 1 | **T0 + 0 w** |
| **1 Python proto (PettingZoo)** | 10 k random sims < 30 s, all unit tests pass | 2 | T0 + 1 w |
| **2 Random & scripted bots** | Random-legal agent, AlwaysAccuseDay2, etc. | 1 | T0 + 2 w |
| **3 Metrics harness** | `evaluate()` CLI, CI badge green | 1 | T0 + 2 w |
| **4 Baseline PPO** | ≥ 80 % win vs. random (both roles) in < 48 h on 1 GPU | 3 | T0 + 4 w |
| **5 Fast C++ engine (EnvPool)** | ≥ 200 k env-steps/s, regression suite green | 3 | T0 + 6 w |
| **6 Historical-opponent pool** | No regression vs. random, Elo > 1100 | 2 | T0 + 7 w |
| **7 Mini-league (4 learners)** | Elo curve plateaus; diversity KL > 0.3 | 3 | T0 + 9 w |
| **8 Equilibrium layer (NFSP/PSRO)** | Exploitability proxy < 2 % | 4 | T0 + 12 w |
| **9 Language ingestion** | Act-classification F1 ≥ 90 %; no perf drop | 2 | T0 + 14 w |
| **10 Intent + NLG** | 60 % humans fooled blind test, win +5 % | 4 | T0 + 18 w |
| **11 Deployment** | Docker < 2 GB, latency < 100 ms, safety pass | 2 | T0 + 20 w |
| **12 Publication** | ArXiv pre-print, reproducibility badge | 1 | T0 + 22 w |

**Exit criteria** for the whole project: requirements R-G1…R-G6 satisfied.

---

## 5 Detailed execution path

### 5.1 Token grammar  
* **Verb tokens** (≤ 40): ACCUSE, PUT_TO_VOTE, CLAIM_SHERIFF, DENY_SHERIFF, SAY_RED, SAY_BLACK, SHERIFF_CHECK (night), DON_CHECK, KILL, PASS, …  
* **Argument tokens**: `PLAYER_0 … PLAYER_9`  
* **Phase tokens**: `<DAY_n>`, `<NIGHT_n>`  
* Always include `<NO_OP>` so legal_mask never all-zero.

### 5.2 Observation encoding  
```
[CLS] <DAY_1> <ROLE_MAFIA?> <PLAYER_0> ... turn-action tokens ... </TURN>
```
Rotate seats so the **current speaker is always PLAYER_0** (permutation invariance).

### 5.3 Engine API (C++)  
```cpp
struct Obs {
  std::array<int, MAX_SEQ> tokens;   // padded with 0
  Mask mask;                         // 2-D verb×target
};
step(Action a) -> {Obs, reward, done, info}
```

### 5.4 Learning loop  
```python
while not converged:
    traj = collect_env_steps(N=8k, opponents=PFSP_pool)
    mask_logits(policy, traj.legal_mask)
    loss = PPO(policy, value, traj)          # clip=0.2, ent=0.01
    if step % 1e6 == 0:
        freeze_checkpoint_into_pool()
```

### 5.5 Exploitability estimate  
* Train a high-entropy DQN exploiter for 0.5 M steps vs. frozen average policy.  
* If exploiter win > 52 % ⇒ resume NFSP/PSRO iteration.

---

## 6 Risks & mitigations  

| Risk | Impact | Mitigation |
|------|--------|------------|
| Transformer unstable in RL | Divergence | Use GTrXL gates & GRU init; LR warm-up  |
| League cycling | No convergence | PFSP prioritised sampling, R-NaD KL regulariser |
| Sparse reward stall | Slow learning | Entropy bonus, scripted explorers, random pre-train |
| NLG incoherence | Humans detect bot | Grounding filter + RLHF pass |

---

## 7 Open questions  
* Exact hyper-params for PFSP (temperature, history length).  
* Whether to expose Don’s sheriff-check info as private token or separate channel.  
* Size of future NLG LLM (7 B vs. 3 B) vs. latency budget.

---

## 8 Appendices  

### 8.1 Glossary  
* **PFSP** – Prioritised Fictitious Self-Play.  
* **Exploitability** – Expected gain of a perfect best-response vs. current strategy.  
* **R-NaD** – Regularised Nash Dynamics (DeepNash, Stratego 2022).  

### 8.2 Reference docs  
* Game rules – [`docs/game_description.txt`](mdc:docs/game_description.txt)  
* Dialogue rationale – [`docs/transformer_approach/dialogue_o3.txt`](mdc:docs/transformer_approach/dialogue_o3.txt)

---

*Last updated: 2025-06-22*
