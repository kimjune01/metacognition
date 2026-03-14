# Findings: Arithmetic Chain Experiment

## Summary table

### GPT-5.4 (via codex)

| Steps | Bare | Prompt | Framework |
|-------|------|--------|-----------|
| 10    | 5/5  | 5/5    | **3/5**   |
| 15    | 5/5  | 5/5    | **4/5**   |
| 20    | 5/5  | 4/5    | **1/5**   |
| 25    | 4/5  | 5/5    | 5/5       |
| 30    | 5/5  | 5/5    | 5/5       |
| 40    | 5/5  | 5/5    | **4/5**   |
| 60    | 5/5  | 5/5    | **4/5**   |

### Claude Sonnet 4.5

| Steps | Bare | Prompt | Framework |
|-------|------|--------|-----------|
| 10    | 5/5  | 5/5    | 5/5       |
| 15    | 5/5  | 5/5    | **4/5**   |
| 20    | 5/5  | 5/5    | 5/5       |
| 40    | 5/5  | 5/5    | 5/5       |

## What we learned

### 1. Arithmetic chains are the wrong task

Both models are at ceiling. 60 steps with 15-digit numbers and GPT-5.4
still gets 5/5 bare. We never found the "floor" → "ceiling" boundary
because the floor extends to at least 60 steps. The binary search
design requires a task with a reachable ceiling.

### 2. Framework document consistently hurts GPT-5.4

Across 7 step counts, framework underperformed bare in 5 of 7.
The effect is small (usually 1 trial lost out of 5) but directionally
consistent. The document is ~395 lines of markdown — it displaces
context that the model would otherwise use for computation.

### 3. Sonnet is more robust to context noise

Framework only hurt Sonnet in 1 of 4 tested step counts.
Possible explanations:
- Larger effective context window
- Sonnet naturally shows work (chain-of-thought by default)
- The framework text happens to be less disruptive to Sonnet's attention

### 4. The "prompt" condition is a wash

"Verify each step" didn't help or hurt in any consistent direction.
At this difficulty level, both models are already verifying by default.

## Conclusion

The experiment successfully falsified nothing — because the task is
below both models' capability frontier. We need a task where:
- Bare condition fails some of the time
- Errors are the kind metacognition should catch (wrong strategy,
  not wrong arithmetic)
- Difficulty is parameterizable

## Next: candidate tasks

Arithmetic chains test **computation accuracy**, not metacognition.
Metacognition should help with tasks requiring:
- Recognizing you're going down the wrong path
- Choosing between strategies
- Knowing when you don't have enough information
- Catching logical (not arithmetic) errors

Better candidates:
- **Logic puzzles with red herrings** (knights and knaves, river crossings)
- **Coding tasks with misleading variable names**
- **Multi-constraint satisfaction** (scheduling, packing)
- **Ambiguous word problems** (where the obvious reading is wrong)
