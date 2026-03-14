# Experiment: Does the Natural Framework improve Codex performance?

## Subject
GPT-5.4 via `codex exec`

## Intervention
**Treatment**: Codex receives the Natural Framework document as context before the task.
**Control**: Codex receives the same task, no framework.

## Design
Find three zones on a task-difficulty spectrum:

1. **Floor**: Task easy enough that both conditions pass. Metacognition is overhead.
2. **Ceiling**: Task hard enough that both conditions fail. Beyond capability.
3. **Boundary**: Task where treatment and control diverge.

Binary search between floor and ceiling to find the boundary.
If no boundary exists (treatment never outperforms control), the framework
doesn't help — or actively hurts by consuming context with noise.

## What we're actually testing

The null hypothesis has two failure modes:
- **H0a**: Framework context has no effect (noise). Performance is identical.
- **H0b**: Framework context hurts. Treatment underperforms control.

The alternative:
- **H1**: Framework context improves performance in the boundary zone.

H0b is the interesting negative result. It would mean metacognitive framing
actively displaces useful reasoning tokens with structural overhead.

## Task requirements

The task must:
1. Be scoreable (pass/fail or numeric)
2. Be parameterizable in difficulty (a single dial)
3. Plausibly benefit from self-monitoring (multi-step, error-compounding)
4. Be runnable via `codex exec` (text in, text out, no tool use)

## Task candidates

### Option A: Chain-of-errors debugging
Give Codex a function with N bugs. Score = bugs found / bugs total.
Difficulty dial: N (number of bugs), and how subtle they are.
Why metacognition might help: catching your own blind spots, systematic search.
Why it might hurt: framework is about information pipelines, not debugging.

### Option B: Multi-step reasoning with intermediate verification
Give Codex a multi-step math/logic problem. At each step, the answer feeds
into the next. Score = final answer correct.
Difficulty dial: number of steps, complexity per step.
Why metacognition might help: "check your work" at each stage.
Why it might hurt: extra context crowds out working memory for actual math.

### Option C: Constrained generation with self-consistency
Ask Codex to generate something that must satisfy N constraints simultaneously.
Score = constraints satisfied / N.
Difficulty dial: N, and how much constraints conflict.
Why metacognition might help: tracking which constraints you've satisfied.
Why it might hurt: framework is about filtering, not constraint satisfaction.

### Option D: Planning under partial information
Give Codex a scenario with incomplete info and ask for a plan.
Reveal info iteratively (or all at once, with red herrings).
Score = plan quality on rubric.
Difficulty dial: ratio of relevant to irrelevant info, number of steps.
Why metacognition might help: filter/attend maps directly onto this.
Why it might hurt: framework is abstract, task needs concrete reasoning.

## Open questions

- How many trials per condition per difficulty level? (variance matters)
- Is `codex exec` deterministic enough, or do we need temperature=0?
- Should the intervention be the raw blog post, or a distilled prompt?
- Do we need a third condition: metacognitive prompt WITHOUT the framework?
  (To separate "think about your thinking" from "here's a specific framework")
