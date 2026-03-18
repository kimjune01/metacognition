# Round 4 Planning Notes

*Started: 2026-03-17*

## Motivation from Round 3

**Key finding:** Theory is load-bearing
- P(framework > compressed) = 0.93-0.98 (both problems)
- The 16× token overhead for theoretical grounding is worth paying
- Compressed checklist (just the vocabulary) is worthless or harmful

**Question:** If more theory helps more than less theory, does *even more* theory help even more?

## The Handshake Hypothesis

**What is The Handshake:**
- Formal categorical treatment of the Natural Framework
- ~4,500 words (vs ~2,800 for Natural Framework)
- Includes: contracts, data processing inequality, budget formalism, fractal tower, trace, falsification tests
- More dense, more rigorous, more detailed grounding

**Hypothesis:** For problems where framework helps (data processing, production readiness), The Handshake might help even more.

**Counter-hypothesis:** There's a saturation point — beyond which more theory doesn't help because models can't absorb/apply the additional detail in diagnostic context.

## Experimental Design Questions

### 1. What conditions to test?

**Option A: Replace framework with handshake**
- Zero, Bare, Compressed, Filler, **Handshake** (instead of framework)
- Tests if handshake beats filler (diagnostic value)
- Tests if handshake beats compressed (theory load-bearing)
- Missing: direct comparison to Natural Framework

**Option B: Add handshake as sixth condition**
- Zero, Bare, Compressed, Filler, Framework, **Handshake**
- Directly tests P(handshake > framework)
- More expensive (20% more trials per batch)
- Cleaner comparison

**Option C: Progressive theory gradient**
- Zero, Compressed (520 tokens), Framework (8.3k tokens), Handshake (~11k tokens?)
- Tests theory saturation curve
- Drop noise controls (bare, filler) since Round 3 already tested those
- Focused on theory question

### 2. What problems to test?

**Round 3 lesson:** Problem-type clustering matters
- Data processing → framework helps
- Algorithmic → framework hurts

**Strategy:**
- Pre-register problem categories
- Select multiple problems per category
- Test category × theory interaction

**Candidate categories:**
1. **Data processing/validation** (where framework helped)
   - API request handlers
   - Data transformation pipelines
   - Input validation systems

2. **Production infrastructure** (untested, framework vocabulary should map)
   - Monitoring/alerting systems
   - Error handling/retry logic
   - Deployment/rollback systems

3. **Algorithmic** (where framework hurt - control)
   - Parsers
   - Encoders/decoders
   - Search algorithms

### 3. Token budget for The Handshake

**The Handshake post:** ~4,500 words
- Full post is too long (would need ~12-14k tokens)
- Need to excerpt or compress for experimental condition
- Target: ~8-10k tokens to match framework token budget?
- Or: accept larger token count if testing "more theory helps"?

**Preprocessing needed:**
- Extract core sections (contracts, DPI, budget, tower)
- Remove "Objections" section (meta-discussion about the theory)
- Remove "Prior art" section (citations)
- Keep: contracts table, pipeline diagram, budget diagram, falsification table
- Estimated: ~8-9k tokens for diagnostic-focused excerpt

### 4. What's the comparison?

**Delta 1 (diagnostic value):** P(handshake > filler)
- Does detailed formalism help vs noise?

**Delta 2 (theory load-bearing):** P(handshake > compressed)
- Already know framework beats compressed (P~0.95)
- Is handshake even stronger?

**Delta 3 (saturation test):** P(handshake > framework)
- **Main question:** Does more formal theory help more?
- Or is Natural Framework sufficient and handshake is overkill?

**Delta 4 (problem-type interaction):** Does the theory gradient help differently across problem types?
- Maybe handshake helps on production infrastructure but not data processing?
- Or: handshake overcomplexifies even where framework worked?

## Open Questions

1. **Token matching:** If handshake is ~9k tokens, do we need a new filler condition at ~9k to control for length?
   - Or: accept that we're testing "more theory" which inherently means "more tokens"?

2. **Judge prompts:** Will judges penalize longer diagnostic reports that cite formal concepts?
   - Round 3: judges scored on gap coverage (5-point scale)
   - Same rubric should work, but watch for bias

3. **Sample size:** Round 3 ran 11-30 batches per problem
   - If testing P(handshake > framework), effect might be smaller (both are good)
   - Need higher power → more batches?

4. **Problem count:** Round 3 tested 2 problems (budget constraint)
   - For category clustering, need ≥3 problems per category
   - 3 categories × 3 problems = 9 problems (expensive)
   - Or: 3 categories × 2 problems = 6 problems (more feasible)

5. **Pre-register what exactly?**
   - Problem categories (define criteria before selecting)
   - Stopping rules (need futility rules this time!)
   - Priors on each delta
   - Cross-category analysis plan

## Recommendation-Driven Design

**Goal:** Clean, actionable recommendation backed by data

For practitioners to know "when to use what," we need:
1. Direct head-to-head comparison (framework vs handshake on same problems)
2. Problem-type clustering (which approach for which task type)
3. Enough power to detect real differences

**This requires:**
- All three theory levels: compressed, framework, handshake (direct comparison)
- Controls: zero, filler (replication + sanity check)
- Multiple problems per category (category effects are real, not noise)
- Pre-registered stopping with futility rules (learned from Round 3)

### Recommended Design: Option B+ (Modified)

**Six conditions:**
1. **Zero** — code + goal only
2. **Compressed** — 520-token checklist (replication: expect to fail)
3. **Framework** — 8.3k Natural Framework
4. **Handshake** — 9k categorical formalism
5. **Filler** — 9k Wikipedia (control for handshake length)
6. ~~Bare (520 wiki)~~ — DROP (Round 3 already tested, less informative than other controls)

**Why this set:**
- Zero: baseline
- Compressed: replication (expect P(fw>comp) ≈ 0.95, P(hs>comp) ≈ 0.95)
- Framework vs Handshake: **main question** (P(hs>fw) = ?)
- Filler: control for handshake token length (P(hs>filler) tests diagnostic value)
- Dropping bare saves 17% of trials, reinvest in more problems

**Two problem categories, 3 problems each = 6 problems:**

1. **Data Processing** (where framework helped in Round 3)
   - Example: RSS feed reader, JSON validator, CSV processor
   - Pre-registered criterion: transforms/validates structured data
   - Round 3 baseline: P(fw>filler) ≈ 0.91

2. **Production Infrastructure** (untested, vocabulary should map)
   - Example: retry logic, circuit breaker, error handler
   - Pre-registered criterion: quality gates, failure handling, observability
   - Round 3 baseline: not tested

**Excluded category:**
- **Algorithmic** — Round 3 showed framework doesn't help (P=0.39)
- Assumption: handshake won't help where framework failed (vocabulary doesn't map to pure computation)
- Saves 33% of trial budget, reinvested in more problems per category
- Pre-registered exclusion: if future work finds handshake helps on algorithmic tasks, invalidates this assumption

**Key comparisons:**

| Question | Comparison | Expected | If confirmed |
|----------|------------|----------|--------------|
| Does more theory help? | P(hs>fw) | 0.45 (skeptical) | Use handshake over framework |
| Is theory still load-bearing? | P(fw>comp), P(hs>comp) | 0.95 (replication) | Don't use compressed |
| Does handshake have diagnostic value? | P(hs>filler) | 0.70 (moderate) | Theory beats noise |
| Problem-type interaction? | P(hs>fw) by category | Varies | Conditional recommendations |

**Clean recommendations at end:**

If P(hs>fw) ≥ 0.95 across both categories:
→ "Use The Handshake for diagnostic tasks on data processing and production infrastructure"

If P(hs>fw) ≥ 0.95 on one category but not the other:
→ "Use Handshake for [winning category], Framework for [other category]"

If P(hs>fw) < 0.50 across both categories:
→ "Use Natural Framework. Handshake is overkill."

If P(fw>filler) < 0.50 on either category:
→ "Theory doesn't help on [category]. Use zero baseline."

**Note:** Recommendations apply only to tested categories (data processing, production infrastructure). Round 3 showed theory doesn't help on algorithmic tasks; not retested in Round 4.

## Next Steps

- [ ] Extract handshake diagnostic content (~9k tokens, accept longer length)
- [ ] Define inclusion criteria for each problem category (before selecting problems)
- [ ] Double-blind problem selection (2 per category, 6 total)
- [ ] Design stopping rules with futility checks at batch 15 (50% of max 30)
- [ ] Set priors for all comparisons (main: P(hs>fw), replications: P(fw>comp), P(hs>comp))
- [ ] Write preregistration document with conditional recommendation logic
- [ ] Commit preregistration to git before running trials

## Connection to Round 3 Findings

**What we learned:**
- Compressed checklist fails because it primes abstractions without grounding
- Framework provides theory: "why these stages exist, when they apply"
- Theory makes diagnostic vocabulary applicable

**Why handshake might help more:**
- Even deeper grounding (contracts, DPI, budget)
- Explicit falsification tests (shows how to diagnose broken roles)
- Formal precision might help models apply vocabulary more accurately

**Why handshake might not help:**
- Saturation: Natural Framework already provides enough grounding
- Complexity: Categorical formalism might confuse rather than clarify
- Task mismatch: Diagnostic tasks need heuristics, not proofs

**Test distinguishes:** Both are plausible. Pre-register, run experiment, see what data says.

---

*This is a planning document. Nothing here is committed until preregistration.*
