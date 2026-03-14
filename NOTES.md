# Metacognition in LLM Agents

## Core Question

Does explicit self-evaluation during agentic tool use improve performance?

## Hypothesis (draft)

Adding metacognitive checkpoints — self-monitoring prompts inserted between
tool calls — reduces steps to task completion and/or increases success rate
on multi-step agent benchmarks, compared to a matched chain-of-thought baseline.

### What needs pinning down

1. **Operationalization of "metacognition"**
   - Self-monitoring: "Did this result move me toward the goal?"
   - Strategy evaluation: "Should I change approach?"
   - Error anticipation: "What could go wrong next?"
   - Confidence calibration: "How certain am I about this step?"

2. **Task domain**
   - Coding (SWE-bench, HumanEval)
   - Multi-step tool use (agent benchmarks)
   - Reasoning (MATH, GPQA)
   - Open-ended agent tasks (harder to measure)

3. **Metrics**
   - Efficiency: tool calls to completion
   - Accuracy: task success rate
   - Robustness: catastrophic failure rate
   - Calibration: does stated confidence predict actual success?

4. **Control condition**
   - CoT baseline (think step-by-step, no self-eval)
   - Same token budget? Or allow metacognitive overhead?

## Key distinction

"Metacognition" in humans = monitoring + control of your own cognitive processes.
For LLMs, the question is whether *prompting* this behavior produces genuine
performance gains or just extra tokens that look reflective.

The null hypothesis: metacognitive prompts are just verbose CoT —
any gains come from more reasoning tokens, not from self-monitoring *per se*.

To falsify the alternative, you'd need to show that matched-length CoT
(without self-eval structure) performs equally well.

## Open questions

- Is this about in-context learning specifically, or agent performance generally?
- Are we testing prompt engineering, or a deeper claim about attention patterns?
- Does the effect depend on model scale? (Might only help weaker models.)
- Does it help more on tasks where the model is near its capability frontier?
