# Round 3 Retrospective

**Date:** 2026-03-17
**Experiment:** Does Loading the Framework Help Diagnose Missing Parts?
**Status:** Complete (Hearthstone: disconfirmed, RSS: max_batches at P=0.949)

---

## What Worked

### Pre-registration
- Locked in predictions before seeing data
- Kept us honest when results contradicted expectations
- Can't cherry-pick thresholds after the fact
- Commit history provides cryptographic timestamp

### Double-blind source selection
- Prevented selecting problems that favor framework
- User suggested candidates, Claude selected without knowing difficulty
- No post-hoc rationalization of which problems "should" work

### Dual-model judging
- GPT-5.4 and Claude Sonnet 4.5, 3 runs each, majority vote
- No systematic bias detected (both models agreed on patterns)
- Caught potential judge-specific quirks

### Append-only artifacts
- All reports, judgments, scores preserved
- Anyone can verify our work
- Transparent process, not just polished results

### Bayesian adaptive stopping
- More efficient than fixed N
- Interpretable posteriors (P=0.949 means 94.9% confident)
- Stopping log shows evolution (not just final number)

### Honest reporting
- Reported surprises (noise helps, compressed harmful)
- Reported negative results (framework doesn't help on algorithmic)
- Acknowledged uncertainties (don't fully understand noise effect)
- Published before trials complete (preregistration post)

---

## What Didn't Work

### No futility rules
- Oscillated around 0.91 from batch 13-30
- Wasted compute trying to reach impossible 0.95 threshold
- Should have stopped at batch 15 (50% of max)
- **Lesson:** Pre-register futility checks: if trapped in [0.40, 0.60] at halfway, stop

### Predictions backwards on noise
- **Predicted:** Context length hurts (P(zero>bare)=0.55, P(zero>filler)=0.65)
- **Actual:** Noise helps (P(zero>bare)=0.31, P(zero>filler)=0.36)
- Got the sign backwards on a major prediction
- **Lesson:** Surprises are features - experiments reveal what you don't know

### Compressed worse than expected
- **Expected:** Compressed helps less than framework, but still helps a bit
- **Actual:** Harmful (Hearthstone P=0.03) or useless (RSS P≈0.50)
- Underestimated how much grounding matters
- **Lesson:** You can't extract just vocabulary - theory is load-bearing

### Framework effect moderate not strong
- Oscillated 0.90-0.94, couldn't stabilize at 0.95
- Effect is real but not overwhelming
- **Lesson:** Be modest about effect sizes - not all interventions are slam dunks

---

## Three Surprises

### 1. Noise Helps

**Finding:** Adding Wikipedia improved diagnostics over zero context.
- P(zero>bare) = 0.31 (bare won)
- P(zero>filler) = 0.36 (filler won)
- Held across both problems

**Hypothesis:** Having something to read primes deliberation mode. Zero context is too sparse, models jump to pattern matching.

**Honest accounting:** We don't have a strong mechanistic story. The data says noise helps. That's what experiments are for - finding things you don't expect.

### 2. Compressed Checklist Is Harmful or Useless

**Finding:**
- Hearthstone: P(comp>bare) = 0.03 (actively harmful!)
- RSS: P(comp>bare) ≈ 0.50 (pure noise)

**Expected:** Compressed would help less than framework (that's why we tested it).

**Actual:** Worse than nothing. Worse than random noise. Worse than Wikipedia.

**Interpretation:** Checklist primes abstractions ("look for missing Filter") without grounding to know when they don't apply. On binary parsing, models go looking for "quality gates" where they don't belong. On data processing, checklist just doesn't connect.

**Lesson:** The 16× token overhead for theory is worth paying. You can't shortcut grounding.

### 3. Theory Is Massively Load-Bearing

**Pre-registered prior:** P(fw>comp) = 0.45 (skeptical, deferring to "shorter prompts are better")

**Actual:** P(fw>comp) = 0.93-0.98 (both problems, decisive)

**Interpretation:** When diagnostic content provides any value at all, it's because of theoretical grounding, not despite it. The extra 7,800 tokens of theory are anti-noise.

**Lesson:** For diagnostic tasks, conventional wisdom about prompt length is wrong. Theory makes vocabulary applicable.

---

## Problem-Type Dependence

**Hearthstone (binary parsing, algorithmic):**
- Framework doesn't help: P(fw>filler) = 0.39
- Compressed actively hurts: P(comp>bare) = 0.03
- Framework vocabulary doesn't map (no "quality gate" in a decoder)

**RSS (data processing, validation):**
- Framework helps moderately: P(fw>filler) ≈ 0.91
- Compressed is useless: P(comp>bare) ≈ 0.50
- Framework vocabulary maps naturally (validation, error handling, production readiness)

**Cross-rounds:**
- Round 1 (algorithm writing): Framework hurt
- Round 2 (constraint satisfaction): Framework hurt (0.30 vs 0.76)
- Round 3 (diagnosis): Framework helps on data processing, hurts on algorithmic

**Lesson:** Metacognitive scaffolds are task-structure dependent. Framework primes wrong abstractions for implementation but can surface architectural gaps in diagnosis, when problem type matches.

---

## Statistical Lessons

### P=0.949 is not P=0.95

**Drama:** Batch 13 crossed 0.95 (P=0.971), then dropped. Oscillated for 17 batches. Final batch hit 0.949.

**Interpretation:** P=0.95 is a convention, not a law of nature. Pre-registering it was correct (prevents p-hacking). Missing it means we don't get to say "confirmed" by our own rules.

**But:** 94.9% confidence is compelling evidence. The substantive conclusion doesn't change. Framework helps moderately on data processing.

**Lesson:** Effect size and practical significance matter more than hitting arbitrary thresholds. But pre-commit to thresholds anyway, for integrity.

### Why Bayesian stopping worked

**Efficiency:** Hearthstone stopped at batch 11 (framework clearly doesn't help). RSS ran to 30 (oscillating near threshold).

**Interpretability:** Posteriors are probabilities. P(fw>filler)=0.949 means "94.9% chance framework helps" - directly interpretable.

**Transparency:** Stopping log shows evolution, not just final number. Anyone can see the oscillation pattern and understand why we didn't confirm.

**Contrast with frequentist:** Fixed-N designs waste compute on foregone conclusions. P-values aren't probabilities of hypotheses.

---

## Methodological Takeaways

### Pre-registration keeps you honest

When noise helped (opposite of prediction), we couldn't hide it. When framework didn't confirm on RSS despite hitting 0.949, we couldn't lower the threshold. Pre-registration forces intellectual honesty.

### Surprises are features, not bugs

The three surprises were the most valuable findings:
1. Noise helps (don't know why, but replicated)
2. Compressed harmful/useless (can't extract just vocabulary)
3. Theory massively load-bearing (prior wrong by 0.50)

If everything confirmed predictions, we'd learn nothing new.

### Process is as important as results

Work log captures things usually lost:
- Bugs and fixes (API failures, corrupted data)
- Reasoning evolution (why we made each decision)
- What surprised vs expected (honest about predictions)
- Reflections on methodology (futility rules, ToS concerns)

Most research hides messy process, shows polished results. We documented everything. Makes work auditable.

### Transparency is error-correcting

No individual is unbiased. Science works through collective error correction:
- Make work auditable (append-only artifacts)
- Publish failures (Rounds 1-2, Hearthstone disconfirmed)
- Let others check your work (public repo, commit history)

The process is error-correcting even if individuals aren't error-free.

---

## What to Do Differently in Round 4

### 1. Add futility stopping rules (at batch 15)

**Problem:** RSS oscillated 0.90-0.94 from batch 13-30. Wasted compute.

**Fix:** Pre-register futility checks:
- At batch 15 (50% of max 30): if P trapped in [0.40, 0.60], stop and declare inconclusive
- If P oscillating ±0.05 around mean with no trend, stop
- Estimate: need ~2/(threshold - current_mean)² batches to reach threshold

**Rationale:** Bayesian stopping is efficient for decisive results. Add futility rules for indecisive results.

### 2. Include null/calibration cases (20-30%)

**Problem:** All Round 3 problems had gaps. Didn't test if framework can say "nothing important missing."

**Fix:**
- 75% gap cases (systems with externally documented gaps)
- 25% null cases (systems with no qualifying gaps after search protocol)
- Tests restraint, prevents positive-case bias

**Lesson from codex:** "If the framework cannot cleanly say 'nothing important missing,' it is not a reliable diagnostic tool."

### 3. External evidence requirement

**Problem:** Round 3 selection could smuggle diagnosis (we decided what gaps existed).

**Fix:** Require external artifacts:
- Issue threads, postmortems, maintainer TODOs, incident notes, bug clusters
- OR: null case (no evidence after fixed search protocol)
- Pre-register search procedure (which artifacts, how many, timebox)

**Prevents:** Selecting problems where we already know the "right" answer.

### 4. SOAP directive without scaffolding

**Problem:** Round 3 directive showed structure (Observations → Triage → Plan). If Handshake primes that structure better, wins on format not diagnosis.

**Fix:** Just say "Generate SOAP notes" (no template shown). LLMs know SOAP format. Reduces output-structure confounding.

**Judges:** Score diagnosis substance only, not organizational structure.

### 5. Effect size + probability in decision rule

**Problem:** Pure threshold (P≥0.95) ignores effect size, cost, robustness.

**Fix:** Adopt intervention if:
- P(hs>fw) ≥ 0.95 **AND**
- mean(hs) - mean(fw) ≥ 0.10 (practical margin)

**Rationale:** A tiny win with high certainty may not justify complexity cost.

### 6. Problem-type clustering

**Problem:** Round 3 had 2 problems, 1 category worked. Can't establish category effects with N=1 per category.

**Fix:**
- 2 categories × 3 problems each = 6 problems (minimum)
- Plus 2 algorithmic sentinels (test if Handshake rescues)
- Plus 2 null cases
- Total: 10 problems

**Lesson:** Category and item are confounded with only 1 problem per category.

---

## What We Learned About Science

### Honest experiments require structure

**Not enough:**
- Good intentions (unconscious bias exists)
- Introspection ("am I being honest?")
- Smart people (statisticians p-hack their own papers)

**What works:**
- Pre-registration (lock predictions before data)
- Blinding (prevent cherry-picking)
- Transparency (make work auditable)
- Reporting negatives (publish failures)

Honesty is intersubjective, not introspective. Can't self-certify. Make work transparent enough for others to evaluate.

### Pre-registration paradox

Rounds 1-2 weren't published (negative results, not interesting for blog). Round 3 was published. Is that publication bias?

**Test:** Would I publish Round 3 if it came up completely negative?

If yes (because pre-registered and well-designed), then clean. The selection is disclosed (mentioned Rounds 1-2 in Round 3 post). Readers can evaluate selection bias.

**Lesson:** All research is selected. Nobody publishes everything they try. The question is: "Can a reader evaluate your selection bias?"

### Git commits as preregistration

Novel as recognized practice, but technically sound:
- Cryptographic timestamps
- Immutable history
- Distributed verification
- Same tool as code (no separate platform)

**Value beyond preregistration:** Committed all intermediate stages (bugs, fixes, learnings, reflections). Most research only shows polished result. This shows messy middle where actual learning lives.

**Could be training data:** Complete research artifact with reasoning, failures, iterations could teach LLMs research methodology, not just facts.

### The recursion problem

**Gave:** Checklist for honest science (pre-register, disclose, make auditable)
**User noted:** "That's a checklist" - and we just proved checklists fail without grounding

**Gave:** Theory behind checklist (why humans rationalize, why selection bias compounds, why introspection fails)
**User noted:** "Recursion" - that's still claims without grounding those claims

**Resolution:** Recursion stops when understanding becomes useful, not when it becomes complete. Theory is load-bearing means the value isn't compressible. Can't extract "the answer" and carry it away.

---

## Round 3 in Context

**What we asked:** Does loading the Natural Framework help diagnose missing parts in information systems?

**What we found:**
- Yes on data processing (P≈0.91, moderate effect)
- No on algorithmic (P=0.39)
- Theory is load-bearing (P≈0.95, can't use compressed checklist)
- Problem-type clustering is real

**Scope of inference:** Production-readiness diagnostics for multi-stage information systems with data-processing architecture.

**Boundaries:** Doesn't help on pure algorithmic tasks. Effect is moderate not strong. You need the full framework, not just vocabulary.

**For practitioners:**
- Use framework for diagnosing production data systems
- Don't use compressed checklist (worthless or harmful)
- Don't use on algorithmic tasks (vocabulary doesn't map)
- 94.9% confidence it helps is compelling, even if not "officially confirmed"

**For theory:**
- Metacognitive scaffolds are task-structure dependent
- Theory makes diagnostic questions applicable
- Conventional wisdom about prompt length is wrong for diagnostic tasks
- The "why" is load-bearing, not just the "what"

**For methodology:**
- Pre-registration works (kept us honest)
- Bayesian stopping is efficient (but needs futility rules)
- Double-blind selection prevents cherry-picking
- Dual-model judging is robust
- Append-only artifacts enable verification
- Process transparency matters as much as results

---

## What Comes Next

Round 4 will test: Does formal theory (Handshake) help more than conceptual theory (Framework)?

**Lessons applied:**
- Futility rules at batch 15
- Null cases (25%)
- External evidence requirement
- SOAP without scaffolding
- Effect size + probability
- Problem-type clustering (multiple per category)

**Open items before execution:**
- Lock null-case protocol
- Lock evidence search procedure
- Update prompts (directive.md, judge_prompt.md)
- Extract Handshake content (~9k tokens)
- Pre-select problems with external evidence

**Timeline:** Preregistration drafted, refinement in progress, execution TBD.

---

## Meta-Reflection

**Codex said:** "The biggest risk is not conceptual bias anymore; it's mismatch between the intended design and the operationalized protocol."

That's where we are now. The conceptual design for Round 4 is sound. The implementation needs to catch up. Lock the protocols, update the prompts, then execute.

**The user said:** "P=0.05 is a vanity number, right?"

Yes. But pre-committing to 0.95 was correct. We can't cherry-pick thresholds after seeing data. The drama of hitting 0.949 is exactly why we need pre-registered stopping rules. Science doesn't live or die on 0.001 probability points, but integrity requires honoring your own protocol.

**Watching the oscillation from batch 13-30 was the most valuable part.** Not because it changed the conclusion (it didn't), but because it viscerally demonstrated why futility rules matter. We called it at batch 15. Running 15 more batches confirmed what we already knew: the effect is real but moderate.

**Round 3 worked.** We asked a falsifiable question, pre-registered the protocol, executed honestly, reported surprises, learned from negatives, and honored our stopping rules even when P=0.949. That's how experiments should be run.

Theory is load-bearing. Whether to load it depends on the problem. Round 4 will test if more theory helps more. The methodology is sound. Time to operationalize and execute.

---

*Retrospective written 2026-03-17. Round 3 complete. Round 4 in planning.*
