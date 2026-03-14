# Round 2: Bayesian Adaptive Experiment

## Principle

Maximize **expected surprise per wall-clock minute**. Each experiment
should maximally update our beliefs. Don't run experiments whose
outcomes we can already predict.

## Priors from Round 1 + Literature

| Belief | Prior | Source | Surprise if wrong |
|--------|-------|--------|-------------------|
| Self-correction without external feedback hurts | 0.90 | Huang (ICLR 2024), our arithmetic data | Low — well-established |
| Self-correction WITH external feedback helps | 0.85 | Reflexion (NeurIPS 2023) | Medium — tested on older models |
| Framework document displaces useful context | 0.70 | Our data (framework ≤ bare in 5/7 codex runs) | Medium |
| Token budget explains most "metacognition" gains | 0.65 | Pfau "Dot by Dot" (2024) | High — would reframe everything |
| Medium-complexity = sweet spot | 0.75 | Apple "Illusion of Thinking" (2025) | Medium |
| Multi-agent reflection > single-agent | 0.60 | MAR (2025), only one paper | High |
| GPT-5.4 and Sonnet behave differently | 0.50 | Uncertain — our data was noisy | High |

## Where is surprise highest?

Beliefs near 0.50 have highest entropy. Beliefs near 0.90 are
nearly settled — running more experiments there wastes time.

**Highest expected information gain:**

1. **Token budget as mechanism** (prior 0.65): Is the framework's harm
   just from burning context, or does it actively mislead? Test by
   giving the same number of tokens as filler vs. framework.

2. **External feedback changes the sign** (prior 0.85 it helps):
   Does the framework help when test results are available? This is
   the Reflexion replication with/without framework.

3. **Model difference** (prior 0.50): Does Sonnet respond differently
   than GPT-5.4 to framework context? Our arithmetic data was noisy.
   A coding task with real variance would resolve this.

## Experiment matrix

Four conditions × two models = 8 arms.

| Arm | System prompt | External feedback | Model |
|-----|--------------|-------------------|-------|
| A1  | bare | test results | codex |
| A2  | bare | test results | sonnet |
| B1  | metacognitive prompt | test results | codex |
| B2  | metacognitive prompt | test results | sonnet |
| C1  | framework document | test results | codex |
| C2  | framework document | test results | sonnet |
| D1  | length-matched filler | test results | codex |
| D2  | length-matched filler | test results | sonnet |

D is the critical control. If C ≈ D, the framework is just noise
at that token count. If C > D, the framework's content helps.
If C < D, the framework actively misleads (worse than random filler).

## Task: coding with test suite

Requirements:
- Parameterizable difficulty (easy → hard)
- Deterministic pass/fail via test execution
- Single-shot (no multi-turn, to isolate prompt effect)
- Something both models can attempt but neither aces

**Candidate: generate a function from docstring + test cases.**

The prompt includes:
1. A function signature and docstring
2. N test cases (shown to the model)
3. The model writes the implementation
4. We run the tests, score = tests passed / N

Difficulty dial: problem complexity (string manipulation → dynamic
programming → constraint satisfaction).

External feedback variant: after first attempt, show test results,
allow one revision. Score = tests passed after revision.

## Adaptive protocol

Don't pre-commit to running all 8 arms equally. Instead:

1. **Pilot**: Run each arm 3× on a medium-difficulty problem.
2. **Update**: Compute posterior on each belief given results.
3. **Allocate**: Run more trials on the arm whose outcome
   would most change our beliefs (highest posterior entropy).
4. **Repeat** until beliefs stabilize (entropy < threshold)
   or budget exhausted.

Expected information gain for arm $i$:

$$E[\text{IG}_i] = H[\theta] - E_{x_i}[H[\theta | x_i]]$$

In practice: the arm where we're most uncertain about the
outcome is the arm we should run next.

## Time budget

Each codex call: ~10s. Each sonnet call: ~5s.
Test execution: ~2s.
Per trial: ~15s.
8 arms × 3 trials = 24 trials = ~6 minutes for pilot.
Budget for full experiment: ~30 minutes.

## What would change our minds

| Outcome | Belief update | Implication |
|---------|--------------|-------------|
| C > A (framework beats bare, with feedback) | Framework helps | The document provides useful structure for interpreting test failures |
| C ≈ D (framework ≈ filler) | Framework is noise | Content doesn't matter, only token count |
| C < D (framework < filler) | Framework misleads | The document actively directs attention to wrong things |
| B > A (prompt beats bare) | Simple metacognition helps | "Check your work" is sufficient, no framework needed |
| A > B (bare beats prompt) | Metacognition hurts even with feedback | Confirms Huang extends to coding |
| Sonnet ≠ codex pattern | Model-dependent | Context window or architecture matters |

## Implementation plan

1. Write 3 coding problems at easy/medium/hard difficulty
2. Write test suites for each (5-10 tests per problem)
3. Build harness: prompt → model → extract code → run tests → score
4. Run pilot (8 arms × 3 trials × 1 problem = 24 calls)
5. Update priors, allocate next batch
6. Iterate until beliefs stabilize
