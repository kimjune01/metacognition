# Round 2 Results

## Setup

- **Task**: Constraint satisfaction (assign unique values 1..n to slots with lt/diff/adj constraints)
- **Models**: GPT-5.4 (codex), Claude Sonnet 4.5
- **Conditions**: bare, metacognitive prompt, framework document, length-matched filler
- **Trials**: 8 per codex arm, 3 per sonnet arm

## Results: GPT-5.4 (codex)

| Condition | Avg Score | Per-trial scores |
|-----------|----------|------------------|
| bare | 0.76 | 1.0 1.0 0.0 1.0 1.0 1.0 1.0 0.1 |
| prompt | 0.78 | 0.0 1.0 0.2 1.0 1.0 1.0 1.0 1.0 |
| filler | 0.65 | 1.0 1.0 0.1 0.1 1.0 0.0 1.0 1.0 |
| framework | **0.30** | 0.0 1.0 0.1 0.1 1.0 0.1 0.1 0.0 |

## Results: Claude Sonnet 4.5

All conditions: 1.00 (3/3 trials each). Problem is below Sonnet's frontier.

## Key findings

### 1. Framework actively misleads (not just token displacement)

framework (0.30) << filler (0.65). Both consume ~25k chars of context.
If the harm were purely from token displacement, framework ≈ filler.
Instead, the framework is **twice as bad as random text** of the same length.

The framework document primes the model to think about information
pipelines, filtering, attention — concepts irrelevant to constraint
satisfaction. It directs attention away from the algorithmic thinking
(backtracking, constraint propagation) that the task actually needs.

### 2. Metacognitive prompt is a wash

prompt (0.78) ≈ bare (0.76). "Think through your approach, check edge
cases, trace through examples" neither helps nor hurts. The model
already does this when it reasons well; prompting it doesn't add signal.

### 3. Any long context hurts somewhat

filler (0.65) < bare (0.76). Even irrelevant text at 25k chars degrades
performance by ~14%. This is the token displacement effect — real but
not the whole story.

### 4. Sonnet is more robust

Sonnet aces all conditions 10/10. Either the problem is below its
frontier, or Sonnet's architecture handles context noise better.
Cannot distinguish without a harder problem.

## Prior updates

| Belief | Prior | Posterior | Evidence |
|--------|-------|-----------|----------|
| Framework displaces context | 0.70 | 0.90 | filler < bare |
| Framework actively misleads | 0.30 | 0.85 | framework << filler |
| Metacognitive prompt helps | 0.40 | 0.15 | prompt ≈ bare |
| Token budget explains gains | 0.65 | 0.50 | Displacement is real but insufficient to explain framework's harm |
| Model difference exists | 0.50 | 0.90 | Sonnet unaffected, codex fragile |

## What to do next

1. **Find Sonnet's frontier**: Need a harder problem where Sonnet fails ~30-50% of the time
2. **Test external feedback loop**: Current experiment is single-shot. Reflexion showed gains with multi-turn + test feedback. Does the framework help *interpret* test failures?
3. **More codex trials**: 8 trials is still low. Framework at 0.30 has high variance (some 1.0 runs, many near 0). Need ~15-20 trials for significance.
