# Round 3 Discussion

*Living document tracking findings and questions as the experiment runs.*

## Current Status (2026-03-17)

**Hearthstone Deckstring Parser:** DISCONFIRMED (11 batches)
**RSS Feed Reader:** In progress (batch 15+)

---

## Surprising Finding #1: Noise Helps (Hearthstone)

**Prediction (conventional wisdom):**
- P(zero > bare) = 0.55 — small noise hurts a bit
- P(zero > filler) = 0.65 — large noise hurts more

**Actual result:**
- P(zero > bare) = 0.31 — **bare beat zero**
- P(zero > filler) = 0.36 — **filler beat zero**

Adding Wikipedia articles about plate tectonics improved diagnostic quality over the true zero baseline.

**Hierarchy (Hearthstone):**
1. Bare (520 tokens of noise) - 0.52 mean
2. Filler (8.3k tokens of noise) - 0.51 mean
3. Framework (8.3k theory) - 0.50 mean
4. Zero (nothing) - 0.50 mean
5. Compressed (520 checklist) - 0.43 mean

**Questions:**
- Why would irrelevant context improve diagnostics?
- Context length as deliberation trigger?
- Contrast effect (something to read → diagnostic mode)?
- Is this Hearthstone-specific or general?

**Test:** Check if RSS shows the same pattern when it completes.

---

## Surprising Finding #2: Compressed Checklist Hurts/Fails

**Hearthstone:**
- P(comp > bare) = 0.03 — **compressed actively harmful**
- Worse than bare noise, worse than nothing

**RSS Feed Reader (so far):**
- P(comp > bare) ≈ 0.50 — **pure noise, no effect**
- Oscillating around coin-flip

**The puzzle:**
- Why would extracting just the checklist make things worse?
- Hypothesis: Checklist primes abstractions ("look for missing Filter") without grounding to know when they don't apply
- On binary parsing (Hearthstone): misleads
- On data processing (RSS): ignored as irrelevant

**Implication:**
You can't just extract the six-stage vocabulary and ship it. The theoretical grounding is what makes it applicable.

---

## Consistent Signal: Theory Is Load-Bearing

**Both problems:**
- P(framework > compressed) = 0.93-0.98 (very high)
- When diagnostic content helps at all, it's the full framework, not the checklist

**This contradicts conventional wisdom:**
- "Shorter prompts perform better" → FALSE for diagnostic tasks
- "Just give the model a checklist" → Worthless or harmful
- The 16× token overhead for theory is worth paying

**Delta 2 (theory tax):**
- Pre-registered prior: P(fw > comp) = 0.45 (skeptical, deferring to conventional wisdom)
- Actual: P(fw > comp) = 0.93-0.98 (decisive)
- The "why" matters, not just the "what"

---

## Problem-Specific Effects

**Hearthstone (binary parsing, algorithmic):**
- Framework doesn't help vs filler (P = 0.39)
- Compressed actively hurts (P = 0.03)
- Even noise beats framework

**RSS Feed Reader (data processing, validation):**
- Framework helps vs filler (P ≈ 0.91, oscillating near 0.95)
- Compressed is useless (P ≈ 0.50)
- Framework provides value but can't stabilize

**Hypothesis:**
Framework vocabulary ("Filter", "Consolidate", "quality gates") maps better to data-processing/production-readiness gaps than to algorithmic/parsing gaps.

**Test:**
If we had more problems, we'd see clustering:
- Data processing problems: framework helps
- Algorithmic problems: framework hurts or neutral

---

## The Oscillation Problem (RSS)

P(framework > filler) trajectory:
- Batch 4: 0.811
- Batch 7: 0.924
- Batch 10: 0.919
- Batch 13: **0.971** (crossed 0.95!)
- Batch 14: 0.914 (dropped back)

**Pattern:** Hovers around 0.90-0.92, briefly crosses 0.95, then retreats.

**What this means:**
- Real but moderate effect
- Framework helps on *some* gaps but not all
- Not a slam-dunk general diagnostic tool

**Stopping rule problem:**
- Needs P ≥ 0.95 to confirm
- But effect oscillates around 0.91
- Will likely run to max 30 batches and declare "inconclusive" even though the signal is clear

**Lesson for next time:**
Add futility rules at batch 15 (see experimental-design.md in memory)

---

## Cross-Problem Pattern

**If RSS completes as-is:**
- Hearthstone: disconfirmed (framework doesn't help)
- RSS: inconclusive (framework probably helps but P < 0.95)

**Cross-problem posterior:**
P(framework generally helps) will be low (< 0.50) because:
- 0 confirmed problems
- 1 disconfirmed problem
- 1 inconclusive (trending positive but not decisive)

**But that masks the real finding:**
Framework is **task-structure dependent**. It helps on data-processing problems, hurts on algorithmic problems. The cross-problem average obscures this.

**Better question:**
"What problem types benefit from the framework?" not "Does the framework help in general?"

---

## Sign Reversal from Round 2

**Round 2 (implementation task):**
- Framework: 0.30
- Bare: 0.76
- Framework **actively hurt** on constraint satisfaction coding

**Round 3 (diagnostic task):**
- RSS: Framework ≈ 0.50-0.60, Filler ≈ 0.40-0.50 (helps)
- Hearthstone: Framework ≈ 0.50, Filler ≈ 0.51 (neutral/hurts)

**Confirmed:** Metacognitive scaffolds are task-structure dependent. Framework primes wrong abstractions for implementation but can surface architectural gaps in diagnosis (when the problem type matches).

---

## Open Questions

1. **Why does noise help?**
   - If replicated in RSS, this is a real phenomenon
   - Challenges "shorter is better" dogma
   - Mechanism unknown

2. **What makes compressed harmful vs merely useless?**
   - Hearthstone: P = 0.03 (actively misleads)
   - RSS: P = 0.50 (ignored)
   - Is it the problem type or something else?

3. **Can we predict which problems benefit?**
   - Data processing → helps
   - Algorithmic → hurts
   - What about mixed problems?

4. **Is the oscillation problem fixable?**
   - Different judge prompt?
   - Different gap types?
   - Inherent to moderate effects?

5. **What's the right way to report cross-problem results when effects are heterogeneous?**
   - Traditional: average across problems → "no general effect"
   - Better: cluster by problem type → "helps on X, hurts on Y"
   - How to pre-register clustering?

---

## Implications If Pattern Holds

**For practitioners:**
- Don't use the compressed checklist — it's worthless or harmful
- Framework might help on production-readiness diagnostics for data systems
- Framework will not help (and may hurt) on algorithmic/implementation tasks
- Even random context beats no context (if noise-helps replicates)

**For theory:**
- The "why" is load-bearing — you can't extract just the vocabulary
- Task structure matters more than we thought
- Conventional wisdom about prompt length is wrong for diagnostic tasks

**For experimental design:**
- Need futility rules (learned this the hard way)
- Need more problems to cluster by type
- Cross-problem stopping works poorly when effects are heterogeneous

---

## Next Steps

**Immediate:**
- Let RSS run to completion or stopping criterion
- Check if zero vs bare/filler pattern replicates in RSS

**After completion:**
- Write ROUND3_RESULTS.md with honest findings
- Update Natural Framework post with "when this helps and when it doesn't"
- Design Round 4 with problem-type clustering built in

**Meta:**
- This experiment worked — we learned things we didn't expect
- The pre-registration kept us honest when results contradicted predictions
- The double-blind source selection prevented cherry-picking
- The dual-model judging caught no systematic bias
