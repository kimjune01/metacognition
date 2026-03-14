# Does Metacognition Improve LLM Performance?

**No.** Prepending a metacognitive framework to an LLM's context actively degrades performance on coding tasks — worse than random text of the same length.

## The Experiment

We tested whether giving an LLM a structural framework about information processing ([The Natural Framework](https://june.kim/the-natural-framework)) improves its coding performance. Four conditions, two models, two task types.

### Conditions

| Condition | What the model sees |
|-----------|-------------------|
| **bare** | Just the task |
| **prompt** | "Think through your approach, check edge cases, verify" + task |
| **framework** | The Natural Framework (~25k chars) + task |
| **filler** | Random text of equal length (~25k chars) + task |

The **filler** condition is the key control. It isolates whether the framework's *content* helps, or whether any effect is just from consuming context window tokens.

### Models

- **GPT-5.4** via [Codex CLI](https://github.com/openai/codex)
- **Claude Sonnet 4.5** via [Anthropic API](https://docs.anthropic.com/)

### Tasks

- **Constraint satisfaction** (search problem — assign unique values to slots with ordering/distance constraints)
- **Match-board stabilizer** (pipeline problem — detect runs, delete, apply gravity, repeat to stability)

## Results

### Constraint satisfaction (GPT-5.4, 8 trials/condition)

| Condition | Score |
|-----------|-------|
| prompt | 0.78 |
| bare | 0.76 |
| filler | 0.65 |
| **framework** | **0.30** |

**Framework is worse than random text.** It doesn't just displace context — it actively misdirects. The model thinks about information pipelines when it should think about backtracking.

### Match-board stabilizer (both models, 8 trials/condition)

All conditions scored 0.94–1.00 on both models. The pipeline task was near ceiling — no room for any condition to help or hurt.

## Key Findings

1. **The framework actively misleads (not just token displacement).** Framework (0.30) vs filler (0.65) — the content itself is harmful, not just the space it occupies.

2. **Simple metacognitive prompting is a wash.** "Check your work" (0.78) ≈ bare (0.76). The model already reasons when it can.

3. **Any long context hurts somewhat.** Filler (0.65) < bare (0.76). Token displacement is real — ~14% degradation from 25k chars of noise.

4. **The framework primes wrong abstractions.** It makes the model frame a search problem as an information pipeline, directing attention away from the algorithm actually needed.

## Consistency with Literature

- [Huang et al. (ICLR 2024)](https://arxiv.org/abs/2310.01798): LLMs cannot self-correct reasoning without external feedback.
- [Kamoi et al. (TACL 2024)](https://aclanthology.org/2024.tacl-1.78/): Self-correction only works with reliable external signals (test cases, tool outputs).
- [Liu et al. (ICML 2025)](https://arxiv.org/abs/2410.21333): Chain-of-thought hurts when it directs attention to verbalizable-but-wrong heuristics.
- [Pfau et al. (2024)](https://arxiv.org/abs/2404.15758): Even meaningless filler tokens can help — must control for token budget.

## Repo Structure

```
NOTES.md              # Initial hypothesis
EXPERIMENT.md         # Round 1 design (arithmetic chains)
RESEARCH.md           # Literature review
FINDINGS.md           # Round 1 results (arithmetic — wrong task)
ROUND2.md             # Round 2 design (Bayesian adaptive)
ROUND2_RESULTS.md     # Round 2 results (constraint satisfaction)
ENDOFUNCTOR_RESEARCH.md  # Research on pipeline-shaped problems
CONCLUSION.md         # Final analysis
experiment.py         # Round 1 harness (arithmetic chains)
harness.py            # Round 2 harness (coding tasks with tests)
problems.py           # Problem definitions and test suites
results/              # Raw trial data (JSON + generated code)
```

## The Falsifiable Claim

> Prepending a domain-irrelevant structural framework to an LLM's context degrades performance more than prepending random text of equal length, because the framework primes wrong abstractions that compete with task-relevant reasoning.

**Confirmed** on GPT-5.4, constraint satisfaction, 8 trials (framework 0.30 vs filler 0.65).

## What We Didn't Test

- **External feedback loops.** [Reflexion](https://arxiv.org/abs/2303.11366) showed self-reflection helps with test feedback between attempts. We tested single-shot only.
- **Domain-matched framing.** The framework might help on tasks that *are* information pipelines (e.g., building a search engine). Our pipeline task was too easy to tell.
- **Harder pipeline problems.** SSA optimization, hygienic desugaring, interval analysis — genuinely hard `X → X` problems that might hit the frontier.

## Running

```bash
# Install dependencies
pip install anthropic

# Run Round 2 experiment (requires Codex CLI + Anthropic API key)
python3 harness.py frontier 8    # constraint satisfaction
python3 harness.py pipeline 8    # match-board stabilizer

# Run specific model
python3 experiment.py --model sonnet 10 20  # arithmetic chains
python3 experiment.py --model codex 10 20
```

---

*Experiment designed and run with [Claude Code](https://claude.ai/claude-code) (Claude Opus 4.6). GPT-5.4 via [Codex CLI](https://github.com/openai/codex) served as both research partner and experimental subject.*
