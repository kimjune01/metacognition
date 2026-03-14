# Research: Metacognition in LLMs — Literature Review

## The critical finding

**Self-correction only works with external feedback.** Without it, LLMs second-guess correct answers into wrong ones.

- [Huang et al., ICLR 2024](https://arxiv.org/abs/2310.01798): "LLMs Cannot Self-Correct Reasoning Yet." Intrinsic self-correction (no external feedback) degrades performance. Models change correct answers to incorrect ones when asked to reconsider.
- [Kamoi et al., TACL 2024](https://aclanthology.org/2024.tacl-1.78/): "No prior work demonstrates successful self-correction with feedback from prompted LLMs, except for tasks exceptionally suited for self-correction." Self-correction works only when reliable external feedback is available (test cases, tool outputs, retrieval).

This explains our arithmetic experiment: the "verify each step" prompt gave GPT-5.4 no external signal — it could only second-guess itself. No wonder it hurt.

## When metacognition helps

### Reflexion (Shinn et al., NeurIPS 2023)
[Paper](https://arxiv.org/abs/2303.11366)
- **AlfWorld** (interactive agent tasks): +22%, GPT-4 from 73% → 97%
- **HotPotQA** (multi-hop QA): +20%, GPT-4 from 34% → 54%
- **HumanEval** (coding): +11%, GPT-4 from 67% → 88%
- **Key**: verbal reflection + episodic memory across multiple attempts. External feedback (task completion signals, test results) drives improvement.

### Metacognitive Prompting (Wang & Zhao, NAACL 2024)
[Paper](https://arxiv.org/abs/2308.05342)
Five-stage prompt: understand → judge → critically evaluate → decide → assess confidence.
- General NLU: +1.4% to +2.7% over CoT (QQP, QNLI, BoolQ, WiC)
- Legal tasks: +3.3% to +7.0% (EUR-LEX, LEDGAR, UNFAIR-ToS)
- Largest gains on domain-specific tasks where critical self-evaluation catches domain errors

### Multi-Agent Reflexion (MAR, 2025)
[Paper](https://arxiv.org/html/2512.20845)
Single-agent self-reflection falls into confirmation bias. Using diverse critic personas breaks the cycle and outperforms single-agent Reflexion.

## When metacognition hurts

### Mind Your Step (by Step) — Liu et al., ICML 2025
[Paper](https://arxiv.org/abs/2410.21333)
CoT hurts on 3 of 6 tasks from cognitive psychology:

| Task | Model | Without CoT | With CoT | Drop |
|------|-------|-------------|----------|------|
| Implicit statistical learning | GPT-4o | 87.5% | 64.4% | **-23.1%** |
| Implicit statistical learning | o1-preview | — | 57.7% | **-36.3% vs GPT-4o** |
| Facial recognition | GPT-4o | 64.0% | 51.2% | **-12.8%** |
| Facial recognition | Claude 3 Opus | 44.0% | 29.6% | **-14.4%** |
| Classification with exceptions | GPT-4o | 2.9 rounds | 12.5 rounds | **4.3× slower** |

**Pattern**: CoT hurts when (i) overthinking hurts humans on the same task, (ii) the task requires implicit/gestalt processing, not explicit rule-following.

### The Illusion of Thinking — Apple Research, 2025
[Paper](https://machinelearning.apple.com/research/illusion-of-thinking)
Three regimes:
1. **Low complexity**: standard LLMs > reasoning models. Extra thinking is wasted.
2. **Medium complexity**: reasoning models show genuine advantage. The sweet spot.
3. **High complexity**: both collapse. More tokens don't help.

Reasoning effort increases with complexity, then **declines** despite remaining token budget. Models give up.

### Decreasing value of CoT — Meincke, Mollick et al., Wharton, 2025
[Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5285532)
- For reasoning models (already doing internal CoT), adding explicit CoT gives near-zero benefit
- CoT's marginal value is **decreasing over time** as models improve

## The token budget confound

### Let's Think Dot by Dot — Pfau et al., 2024
[Paper](https://arxiv.org/abs/2404.15758)
Extra intermediate tokens help, **even when semantically empty** (literally "......" as filler). This means any experiment must control for token budget, not just presence/absence of metacognitive content.

**Implication for our experiment**: three conditions aren't enough. We need:
- A: bare (direct answer)
- B: metacognitive prompt ("reflect / verify")
- C: same token budget with non-metacognitive filler (control for "more thinking tokens = better")

## What this means for our experiment

1. **Arithmetic chains were the wrong task** — no external feedback, no strategy selection
2. **The right task needs external feedback** — coding with tests, interactive environments
3. **Medium complexity is the sweet spot** — too easy = ceiling, too hard = both fail
4. **Must control for token budget** — the "dot by dot" finding means any gain from metacognition could be just "more tokens"
5. **Best candidates** (per GPT-5.4): SWE-bench-style coding, OSWorld-style agent tasks
6. **Single-agent self-reflection is weak** — MAR shows multi-agent critic breaks confirmation bias

## Sources

- [Reflexion (NeurIPS 2023)](https://arxiv.org/abs/2303.11366)
- [LLMs Cannot Self-Correct Reasoning Yet (ICLR 2024)](https://arxiv.org/abs/2310.01798)
- [When Can LLMs Actually Correct Their Own Mistakes? (TACL 2024)](https://aclanthology.org/2024.tacl-1.78/)
- [Metacognitive Prompting (NAACL 2024)](https://arxiv.org/abs/2308.05342)
- [Let's Think Dot by Dot (2024)](https://arxiv.org/abs/2404.15758)
- [Mind Your Step (by Step) (ICML 2025)](https://arxiv.org/abs/2410.21333)
- [The Illusion of Thinking (Apple, 2025)](https://machinelearning.apple.com/research/illusion-of-thinking)
- [Decreasing Value of CoT (Wharton, 2025)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5285532)
- [Multi-Agent Reflexion (2025)](https://arxiv.org/html/2512.20845)
- [Decoupling Metacognition from Cognition (AAAI 2025)](https://ojs.aaai.org/index.php/AAAI/article/view/34723)
