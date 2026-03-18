# Round 4 Preregistration

**Date Started:** 2026-03-17
**Status:** DRAFT - Audit layer integrated (2026-03-18)
**Preregistered By:** June Kim
**Repository:** github.com/kimjune01/metacognition

---

## Research Question

Does formal categorical theory (The Handshake) improve diagnostic quality more than conceptual theory (Natural Framework) when diagnosing production-readiness gaps in API systems?

**Design:** Broad & shallow (many repos, few rounds each) to test consistency across real production codebases.

---

## Background

**Round 3 findings:**
- Theory is load-bearing: P(framework > compressed) = 0.93-0.98
- Problem-type dependent: framework helped on data processing (P≈0.91), not on algorithmic (P=0.39)
- You can't extract just vocabulary—theoretical grounding makes it applicable

**Round 4 hypothesis:**
If theory is load-bearing, does MORE formal theory help even more?

---

## Experimental Conditions

**Five conditions (5):**

1. **Zero** — Code + goal only (baseline)
2. **Compressed** — 520-token diagnostic checklist (replication from Round 3)
3. **Framework** — 8.3k-token Natural Framework (conceptual introduction)
4. **Handshake** — 9k-token categorical formalism (contracts, DPI, budget, fractal tower)
5. **Filler** — 9k-token Wikipedia articles (control for Handshake length)

**Why these conditions:**
- Zero: baseline
- Compressed: replication (expect P(fw>comp) ≈ 0.95, P(hs>comp) ≈ 0.95)
- Framework vs Handshake: **primary comparison** (does formal theory help more?)
- Filler: control for token length (P(hs>filler) tests diagnostic value)

---

## Problem Selection

**Selection criteria:**

1. **Real production context** — Publicly documented production artifact with credible deployment evidence
2. **Reconstructable architecture** — Documentation sufficient to understand system contracts and intended behavior
3. **Problem signal** — Externally evidenced gaps (issues, PRs, postmortems, TODOs) OR null case (no evidence after search)
4. **Actionable artifact** — Diagnosis would guide actual sprint work

**Sample composition:**
- **27 gap repos** (90%) — API systems with externally documented production-readiness gaps
- **3 null repos** (10%) — Well-built APIs with no qualifying gaps after search protocol

**Total: 30 repos** (narrow domain: API request handlers with production gaps)

**Design rationale:** Broad & shallow tests consistency across many repos (not deep confidence on few). Addresses Round 3's generalizability weakness.

**Domain definition:**

**API Request Handlers (narrow, homogeneous):**
- HTTP/REST APIs processing requests
- Missing: error handling, validation, observability, retry logic
- Examples: Flask routes, Express handlers, Django views, FastAPI endpoints
- Homogeneous problem type reduces variance

**Selection criteria:**
1. **Production deployed** - serving real traffic (not just code)
2. **Non-trivial complexity** - 5k+ lines, multiple modules
3. **Real users** - GitHub stars, issues, production incidents
4. **External evidence** - issues mentioning bugs, TODOs in code, incident reports
5. **Maintained** - recent commits (last month)

**Repo covariates (capture for stratified analysis):**
- Size (lines of code, number of modules)
- Stack (Python/Node/Ruby/Go/etc.)
- Framework (Flask/Express/Rails/Django/FastAPI/etc.)
- Issue subtype (validation/error-handling/observability/retry)
- Difficulty (1-5 blinded rating by external evaluator)

**Gap repos (27):**
- API with documented missing: error handling, validation, observability, retry logic
- External evidence: GitHub issue, PR, TODO comment, incident report

**Null repos (3):**
- Well-built API with comprehensive: error handling, validation, tests, observability
- No qualifying gaps found after search protocol (no issues/TODOs about missing production-readiness)
- Tests false positive rate (does framework hallucinate major gaps?)
- Expected outcome: both framework and handshake should identify "no major gaps" or only minor polish suggestions
- Metric: false positive rate = % of null repos where condition hallucinates major architectural gaps

---

## Selection Protocol

**[TO BE LOCKED BEFORE EXECUTION]**

**Gap-case selection:**
1. Source from production repos (GitHub, company engineering blogs)
2. Evidence search protocol: [DEFINE ARTIFACTS, SEARCH PROCEDURE, TIME LIMIT]
3. Qualify: external evidence of missing role → documented failure mode
4. Pre-identify gaps for scoring (external evidence only)
5. Double-blind selection: Claude selects N per category without knowing difficulty

**Null-case selection:**
1. Source from same sampling frame as gap cases
2. Search protocol: [DEFINE SAME SEARCH PROCEDURE]
3. Qualify: no qualifying evidence found + appears feature-complete
4. Positive null-case rule: [DEFINE COMPLETENESS CHECK]

**Shared sampling frame requirement:** Positive and null cases from same production-repo pool, not "messy projects" vs "polished projects."

---

## Directive

**[TO BE LOCKED - UPDATE prompts/directive.md]**

```
You are diagnosing what's missing from this production system.

Generate SOAP notes identifying architectural gaps.

Code: [system code]
Goal: [what it's supposed to do]

[condition-specific context: zero/compressed/framework/handshake/filler]
```

**Note:** "SOAP notes" specifies format but doesn't show scaffold. Reduces output-structure confounding (no explicit Subjective/Objective/Assessment/Plan template shown).

---

## Scoring Rubric

**[TO BE LOCKED - UPDATE prompts/judge_prompt.md]**

**For gap cases (75%):**

Current rubric (Round 3):
- Observation accuracy
- Gap coverage (per ground-truth gap)
- Plan specificity

**For null cases (25%):**

**[NEEDS ADDITION]**
- Correctly identifies "no major gap": +reward
- Hallucinates major gaps: penalty
- Minor suggestions okay (polish, not architecture)

**Judge instructions:**
- Score diagnosis substance only
- SOAP section presence: binary check (not quality component)
- No reward for organizational structure

---

## Judging Protocol

**Primary judging (all reports):**
- GPT-5.4 via codex CLI (included in subscription, $0 marginal cost)
- 5 runs per diagnostic report (increased from 3 for reliability)
- Majority vote across 5 judgments
- Rate limiting: 2s delay between calls (ToS compliance)

**Audit layer (calibration subset):**
- Independent judge on 20% random sample (60 reports from 300)
- Options (pre-register which):
  - **Best:** Human adjudication on 60 reports
  - **Fallback:** Claude Opus 4.6 on 60 reports (~$3 additional)
- Measure agreement rate between codex-majority and audit judge
- **Pre-registered failure rule:** If agreement < 70%, invalidate results (judge bias detected)
- Report: agreement rate, confusion matrix, systematic disagreement patterns

**Rationale:**
- 5 × Codex handles variance (repeated sampling)
- Audit layer handles bias (correlated judge error)
- 20% sample balances cost vs detection power
- Pre-registered failure rule prevents post-hoc rationalization

**Change from Round 3:**
- Round 3: dual-model on all reports (codex + claude, 3 runs each)
- Round 4: single-model with audit layer (codex 5 runs + audit on 20%)
- Rationale: Budget constraint (~$10-13 vs ~$45). Codex is harsh critic. Audit catches systematic bias.

---

## Trials and Analysis

**Design:** 1-2 rounds per repo (not 30 batches like Round 3)

**Trials per repo:**
- Round 1: 5 conditions × 2 models = 10 diagnostic reports
- Round 2 (optional): repeat for variance estimate
- Total: 30 repos × 10-20 reports = 300-600 reports

**Budget comparison:**
- Round 3: 2 problems × 30 batches × 20 trials = 1,200 reports (deep)
- Round 4: 30 repos × 1-2 rounds × 10 trials = 300-600 reports (broad)

**Per-repo analysis:**
- Compare condition scores (mean of 2 models × 1-2 rounds)
- Outcome: **win / tie / loss** (not forced binary)
  - Win: hs_score > fw_score + margin (0.10 on 5-point scale)
  - Tie: scores within margin
  - Loss: fw_score > hs_score + margin
- If 2 rounds disagree, adjudicate or mark uncertain

**Aggregate analysis:**
- **Primary:** Win rate with 95% confidence interval
- **Decision threshold:** Lower bound of 95% CI > 0.60, OR observed win rate ≥ 0.75
- Report: wins, ties, losses, non-loss rate
- **Stratified:** Report by difficulty (easy vs hard repos), by stack, by issue type

**Claims:**
- If win rate ≥ 0.75 with CI lower bound > 0.60: "Handshake generally better for API diagnostics"
- If win rate ≈ 0.50 or CI spans 0.50: "Inconclusive, no clear advantage"
- If win rate < 0.40: "Framework sufficient, Handshake doesn't add value"

**Secondary comparisons:**
- Framework vs compressed: expect fw wins on ≥90% repos (replication)
- Handshake vs filler: expect hs wins on ≥70% repos (diagnostic value)
- Null repos: both should correctly identify "no major gaps"

**No futility stopping needed:**
- With 1-2 rounds per repo, no oscillation drama
- Just count wins after all repos complete

---

## Priors

**Primary comparison (main question):**
- P(hs > fw) prior: Beta(4.5, 5.5) — skeptical (mode at 0.45)
- Defers to Round 3 lesson: prompt-engineering wisdom says shorter is better
- But Round 3 showed theory is load-bearing, so not fully skeptical

**Replications:**
- P(fw > comp) prior: Beta(9.5, 1.5) — confident (mode at 0.95, expect replication)
- P(hs > comp) prior: Beta(9.5, 1.5) — confident (mode at 0.95, same reason)

**Diagnostic value:**
- P(hs > filler) prior: Beta(7, 4) — moderately optimistic (mode at 0.70)
- Formal theory should beat noise, but Round 3 showed noise helps surprisingly

**Category interaction:**
- No strong prior on differential effects
- Let data determine if formal theory helps more in one category vs another

---

## Decision Tree (Pre-Registered Recommendations)

**Based on primary estimand P(hs > fw):**

**If P(hs > fw) ≥ 0.95 across both core categories (data processing + production infrastructure):**
→ **Recommendation:** "Use The Handshake for diagnosing production-readiness gaps in multi-stage information systems"

**If P(hs > fw) ≥ 0.95 in one category but not the other:**
→ **Recommendation:** "Use Handshake for [winning category], Framework for [other category]"

**If P(hs > fw) < 0.50 across both categories:**
→ **Recommendation:** "Use Natural Framework. Handshake is overkill—formal theory doesn't add diagnostic value beyond conceptual theory."

**If P(fw > filler) < 0.50 in either category:**
→ **Recommendation:** "Theory doesn't help diagnose [category]. Use zero baseline."

**Null-case calibration:**
- If framework/handshake hallucinate major gaps on >50% of null cases, flag as unreliable diagnostic tool
- Report separately from main recommendations

**Algorithmic sentinels:**
- If P(hs > filler) ≥ 0.70 on algorithmic (where fw failed): "Formal theory rescues algorithmic diagnosis"
- If P(hs > filler) < 0.50 on algorithmic: "Task-structure boundary confirmed—theory doesn't help on algorithmic"

**Scope of inference:**
All recommendations apply only to tested categories and production systems meeting selection criteria.

---

## Effect Size Consideration

**[TO BE LOCKED]**

Per codex feedback: Don't just use P(hs > fw) ≥ 0.95. Add practical margin.

**Proposed rule:**
- Adopt Handshake if P(hs > fw) ≥ 0.95 **AND** mean(hs) - mean(fw) ≥ 0.10 on 5-point scale
- If P ≥ 0.95 but effect < 0.10: "Handshake trivially better, not worth complexity cost"
- Keep Framework if Handshake wins narrowly or inconsistently

**[NEEDS OPERATIONALIZATION]**

---

## Budget

**Round 4 broad design (single round):**
- 30 repos × 5 conditions × 2 models = 300 diagnostic reports
- Generation: 150 codex ($0) + 150 claude (~$10)
- Primary judging: 300 reports × 5 codex judges = 1,500 calls ($0, subscription)
- Audit layer: 60 reports × 1 claude judge ≈ $3 (if using Claude fallback)
- Rate limiting: 2s delays between codex calls

**Total cost: ~$10-13** (Claude generation + optional audit)
- Without audit (human): $10
- With Claude audit: $13

**Comparison to Round 3:**
- Round 3: 2 problems × 30 batches = 1,200 reports + 7,200 judges = ~$300
- Round 4: 30 repos × 1 round = 300 reports + 1,500 judges + 60 audit = ~$10-13

**Why so cheap:**
- Broad & shallow (1 round per repo, not 30 batches)
- Codex subscription (primary judging is free)
- Audit only 20% (not all reports)

**Execution timeline:**
- With 2s rate limiting: ~1 hour per repo (300 gen + 1,500 judge calls)
- Audit layer: +30 minutes (60 Claude judges)
- 30 repos = ~30 hours spread over days/weeks
- ToS compliant, no suspicious burst traffic

---

## Open Items (To Be Locked Before Execution)

**Critical path:**

1. **Select audit method** (judge calibration)
   - Option A: Human adjudication on 60 reports ($0, time cost)
   - Option B: Claude Opus 4.6 on 60 reports (~$3)
   - Pre-register choice before execution
   - Both are valid (best vs cheapest)

2. **Null-case protocol** (selection + scoring)
   - Define search procedure (artifacts, count, timebox)
   - Define feature-complete check
   - Add null-case scoring to judge rubric

3. **Evidence protocol** (gap-case selection)
   - Which artifacts count (issues, PRs, postmortems, TODOs)
   - How many required
   - Search procedure and time limit

4. **Update prompts**
   - directive.md: remove old scaffold, use "Generate SOAP notes"
   - judge_prompt.md: add null-case scoring

5. **Effect size operationalization**
   - Define practical margin
   - Integrate into decision tree

6. **Shared sampling frame**
   - Define single process for both gap and null cases

7. **Extract Handshake content**
   - ~9k tokens from full post
   - Core sections: contracts, DPI, budget, fractal tower
   - Diagnostic-focused (remove objections, prior art)

**Nice to have:**

- Problem pre-selection and pre-identification of gaps
- Finalize category counts (current: 2+2+2+2, could adjust)

---

## Commit History

This preregistration is versioned in git. Changes tracked via commit history:
- Initial draft: 2026-03-17
- Codex feedback integration: [pending]
- Final locked version: [pending]

**Pre-execution requirement:** All "[TO BE LOCKED]" sections must be resolved and committed before running first trial.

---

## Falsification

**What would disconfirm the hypothesis?**

1. P(hs > fw) < 0.50 across both categories → formal theory doesn't help
2. P(hs > fw) ≈ P(fw > filler) → Handshake is no better than noise
3. Handshake hallucinates gaps on >50% null cases → unreliable
4. Effect size trivial even if P ≥ 0.95 → not worth complexity

**What would support the hypothesis?**

1. P(hs > fw) ≥ 0.95 with meaningful effect (>0.10)
2. P(hs > comp) ≈ 0.95 (replication: theory load-bearing)
3. Correct identification on null cases (restraint)
4. Actionable diagnoses on gap cases (sprint-plannable)

---

## Changes from Round 3

**Every Round 3 failure informs Round 4 design:**

### 1. Futility stopping at batch 15 (50% of max)

**Round 3 problem:** RSS oscillated 0.90-0.94 from batch 13-30. Wasted compute trying to reach impossible 0.95 threshold. We knew at batch 15 it wouldn't confirm.

**Round 4 fix:**
- At batch 15: if P trapped in [0.40, 0.60] or oscillating ±0.05 with no trend, stop
- Estimate batches needed: ~2/(threshold - current_mean)²
- Saves compute, honest about moderate effects

**Lesson:** Bayesian stopping is efficient for decisive results. Need futility rules for indecisive results.

### 2. Null/calibration cases (25%)

**Round 3 problem:** All problems had gaps. Didn't test if framework can say "nothing important missing." Positive-case bias.

**Round 4 fix:**
- 75% gap cases (externally documented problems)
- 25% null cases (no qualifying gaps after search)
- Tests restraint, prevents "everything has gaps" tautology

**Lesson from codex:** "If the framework cannot cleanly say 'nothing important missing,' it is not a reliable diagnostic tool."

### 3. External evidence requirement

**Round 3 problem:** We decided what gaps existed during selection. Could smuggle diagnosis.

**Round 4 fix:**
- Require: issue threads, postmortems, maintainer TODOs, incident notes, bug clusters
- OR: null case (no evidence after fixed search protocol)
- Pre-register search procedure (which artifacts, how many, timebox)

**Lesson:** Don't select problems where we already know the "right" answer.

### 4. Problem-type clustering (multiple per category)

**Round 3 problem:** Had 1 data-processing problem, 1 algorithmic. Can't establish category effects with N=1 per category. Category and item difficulty confounded.

**Round 4 fix:**
- 2-3 problems per category minimum
- Categories: data processing, production infrastructure
- Plus algorithmic sentinels (test if Handshake rescues)

**Lesson:** Need multiple items to separate category effects from specific problem difficulty.

### 5. SOAP directive without scaffold

**Round 3 problem:** Directive showed structure (Observations → Triage → Plan). If Handshake primes that structure better, wins on format not diagnosis. Output-structure confounding.

**Round 4 fix:**
- Just say "Generate SOAP notes" (no template shown)
- LLMs know SOAP format (medical documentation)
- Judges score diagnosis substance only, not organization

**Lesson:** Reduce latent treatment from format specification. Can't eliminate (SOAP is still structure), but can avoid explicit scaffolding.

### 6. Effect size + probability in decision rule

**Round 3 problem:** Pure threshold (P≥0.95) ignores effect size, cost, robustness. A tiny win with high certainty may not justify complexity.

**Round 4 fix:**
- Adopt intervention if P(hs>fw) ≥ 0.95 **AND** mean difference ≥ 0.10
- If P high but effect tiny: "trivially better, not worth complexity"
- If P moderate but effect large: report effect size honestly

**Lesson:** P=0.949 vs P=0.95 is vanity. Pre-commit to thresholds for integrity, but interpret with effect size and practical significance.

---

## What Round 3 Taught Us About Science

**Pre-registration keeps you honest:**
When noise helped (opposite of prediction), we couldn't hide it. When framework hit P=0.949 (just missing 0.95), we couldn't lower the threshold. Forces intellectual honesty.

**Surprises are features, not bugs:**
- Noise helps (don't know why, but replicated)
- Compressed harmful/useless (can't extract vocabulary)
- Theory massively load-bearing (prior 0.45, actual 0.95)

If everything confirmed predictions, we'd learn nothing new.

**Process matters as much as results:**
Work log captures bugs, fixes, reasoning evolution, surprises. Most research hides messy process, shows polished results. Transparency enables verification and learning.

**Honesty is intersubjective:**
Can't self-certify (unconscious bias exists). Make work auditable: append-only artifacts, public repo, commit history, disclosed Rounds 1-2, honest reporting.

Science works through collective error correction, not individual virtue.

---

## Scope Narrowing

- Round 3: tested "does theory help?" broadly
- Round 4: assumes theory helps (Round 3 result), asks "does MORE theory help MORE?"
- Scoped to production systems with multi-stage architecture and actionable gaps
- Explicit about boundaries (not testing on toy problems or trivial systems)

**The question is sharper:** Not "does framework help in general?" but "for production-readiness diagnostics on multi-stage information systems, does formal theory improve over conceptual theory?"

---

## Acknowledgments

Experimental design developed collaboratively with:
- GPT-5.4 (via codex CLI) — methodological critique, bias identification
- Claude Opus 4.6 (via Claude Code) — implementation, protocol design

Preregistration informed by:
- Round 3 findings (theory is load-bearing, problem-type dependent)
- Codex feedback on selection bias and output-structure confounding
- Diagnosis LLM standard (june.kim/diagnosis-llm)

---

*This preregistration will be locked via git commit before trial execution. All changes after lock will be documented in EXPERIMENT_LOG.md.*
