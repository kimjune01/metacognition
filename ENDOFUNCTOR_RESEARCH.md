# Endofunctor-Shaped Problems: Research

Source: GPT-5.4 analysis of which coding problems have endofunctor structure.

## Key insight

Our Round 2 negative result (constraint satisfaction) is exactly the kind
of problem GPT-5.4 identifies as a **false positive** — it looks like
`State → State` but the hard part is branching search, not pipeline
transformation. The framework primed pipeline thinking on a search problem.

## Genuinely endofunctor-shaped problem categories

All are `X → X → X → ... → X` where the intelligence is in repeated
suppression/selection within the same representation.

### 1. Token stream normalization
`List[Token] → List[Token]`
Pipeline of passes: annotate, drop, merge, rewrite, canonicalize.
Competitive inhibition appears in competing rewrites.

### 2. AST-to-AST desugaring
`AST → AST`
Cleanest positive class. Lower complex syntax to core primitives.
Hard part: hygiene, evaluation order, edge case interactions.

### 3. Compiler optimization passes
`IR → IR`
Constant fold, copy propagate, dead-eliminate, simplify phis.
Textbook endofunctor. Hard part: preserving side effects.

### 4. Grid state simulation
`Grid → Grid`
Match-3 board: detect runs, delete, apply gravity, repeat to stability.
Hard with blockers, wildcards, simultaneous updates.

### 5. Graph relabeling / pruning
`Graph → Graph`
Mark dead/live, delete isolated subgraphs, compress chains.
Competitive inhibition in mutually exclusive labels.

### 6. Abstract interpretation
`StateMap → StateMap`
Interval analysis: join, transfer, refine, widen. Fixed point.
Most literal "compress high-bandwidth input to durable signal."

### 7. Constraint propagation (no backtracking)
`BoardState → BoardState`
Killer Sudoku propagator: eliminate, prune, find singles/pairs.
Only the propagation part — explicitly forbid search.

## Negative controls (look like pipelines, aren't)

| Problem | Why it looks like X→X | Why it isn't |
|---------|----------------------|--------------|
| CSP/SAT with search | State updates | Hard part is branching, not transforming |
| Pathfinding | Repeated relaxation | Optimization over search frontier |
| Program synthesis | Iterative refinement | Generate-and-check, discontinuous |
| Parsing | Token stream processing | `Tokens → AST`, type changes |
| Transpilation | Code transformation | Domain change is the point |
| Combinatorial optimization | Local updates | Objective-driven search |

## Best candidates for experiment

Ranked by implementability + testability + frontier difficulty:

1. **Match-board stabilizer** (Grid → Grid)
   - Easy to specify, easy to test, many edge cases
   - Simultaneous detection, gravity, special tiles
   - Probably at frontier with enough special-tile rules

2. **Killer Sudoku propagator** (BoardState → BoardState)
   - Well-defined, deterministic, no search
   - Multiple interacting propagation rules
   - Can tune difficulty by which techniques are required

3. **Regex AST simplifier** (AST → AST)
   - Clean endofunctor, many equivalence-preserving rewrites
   - Edge cases in factoring, neutral elements, group semantics

4. **Automaton cleanup pipeline** (NFA → NFA)
   - Epsilon-closure, dead-state removal, compaction
   - Well-defined, testable, multiple interacting passes

## Experiment design

Same 4 conditions as Round 2:
- bare, prompt, framework, filler

Prediction:
- On endofunctor tasks: framework > filler (content helps)
- On search tasks: framework < filler (content misleads)
- If framework ≈ filler on both: framework has no practical value

This is the falsification test for "the framework is only useful for
endofunctor-shaped problems."
