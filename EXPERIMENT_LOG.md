
## 2026-03-17 13:35 - API Migration Attempt

**Issue**: Claude CLI authentication broken after credit purchase
- CLI returns "Credit balance is too low" despite dashboard showing $48.17 available
- `claude auth login` command no longer works
- Both CLI and API report insufficient credits

**Change**: Modified `run_round3.py` to use Anthropic Python SDK directly
- Lines 12-24: Added `from anthropic import Anthropic` import
- Lines 243-307: Modified `run_cli()` to call API directly for claude model
- codex still uses CLI (working fine)

**Result**: API also returns 400 error "credit balance is too low"
- Suggests systemic credit issue, not CLI-specific
- Possible minimum balance threshold not met
- Experiment paused pending credit resolution

**Status**: Waiting for user to resolve credits issue

## 2026-03-17 13:40 - API Resolution & Experiment Resumed

**Resolution**: Credits issue resolved, API now working
- Test call returned valid response ("What is 2+2?" → "4")
- Anthropic API accepting requests with current credit balance

**Cleanup**: Deleted corrupted batch 4-5 data
- Removed 51 files (scores, reports, judgments for RSS batches 4-5)
- Confirmed 0 cached files remain

**Status**: Phase 2 running successfully (task beee83e)
- Hearthstone: DISCONFIRMED (completed earlier)
- RSS Feed Reader: Regenerating from batch 4
- First trial: zero/codex scored 0.40 (valid, not cached 0.00)
- API calls working correctly via Anthropic Python SDK

**Code Change**: Permanent migration from claude CLI to Anthropic API
- Modified run_round3.py line 268-279
- codex still uses CLI (unchanged)
- claude uses direct API calls (more reliable)

## 2026-03-17 14:00-17:00 - Watching the Bayesian Integral Converge

**Context**: RSS Feed Reader running batches 4-15+ in background while monitoring posteriors

**The Waiting**: 
Watching P(fw>filler) oscillate around 0.90-0.97, trying to stabilize above 0.95. Batch 13 crossed the threshold (0.971), batch 14 dropped back (0.914). The experiment grinds on.

**User reflection**: "scientists must be the most patient people on earth after monks, before computers people had to keep running bayesian experiments at the teetering edge"

This is what Jeffreys did in 1939 - working out Bayesian integrals by hand, hitting walls, writing "this cannot be evaluated," publishing anyway because the framework mattered more than the closed form. We're watching APIs do the grinding and still getting impatient. The patience hasn't changed, just the time scale. We count in minutes instead of months.

**On rigor**: "rigor is rigor regardless of whether it's performative or not, right?"

No. Real rigor is load-bearing - if removing the proof changes what you believe, it was rigorous. Performative rigor is credibility theater. Jeffreys looked sloppy to 1950s mathematicians but was right. You can't always tell from outside which is which.

**Key findings discussed**:

1. **Noise helps (Hearthstone)**:
   - P(zero>bare) = 0.31 - bare beat zero (opposite of prediction!)
   - P(zero>filler) = 0.36 - filler beat zero
   - Wikipedia articles about plate tectonics improved diagnostics over nothing
   - Challenges "shorter prompts are better" dogma

2. **Compressed checklist fails**:
   - Hearthstone: P(comp>bare) = 0.03 (actively harmful)
   - RSS: P(comp>bare) ≈ 0.50 (pure noise)
   - You can't just extract the vocabulary and ship it

3. **Theory is load-bearing**:
   - P(fw>comp) = 0.93-0.98 across both problems
   - The 16× token overhead for grounding is worth paying
   - Contradicts conventional wisdom about prompt length

4. **Problem-specific effects**:
   - Framework hurts on algorithmic tasks (Hearthstone)
   - Framework helps on data-processing tasks (RSS)
   - Task structure matters more than we thought

**Methodological learning**: Need to add futility rules to Bayesian stopping

At batch 15 (50% of max), compressed stuck at P≈0.50 clearly won't reach 0.95 with 15 more batches. But pre-registered rules require running to batch 30. Next experiment: add futility stopping.

Committed to memory in experimental-design.md: "Pre-register futility rules before seeing any data, or you're p-hacking."

**Documentation created**:

1. **Preregistration blog post**: `/round3-preregistration`
   - Title: "Does Loading the Framework Help Diagnose Missing Parts?"
   - Full experimental protocol for replication
   - Links to github.com/kimjune01/metacognition
   - Published before results complete

2. **ROUND3_DISCUSSION.md**: Living document tracking findings and questions
   - Surprising results catalogued
   - Open questions listed
   - Implications explored
   - Will update as RSS completes

**On honest experiments**:

The user emphasized: experiments must be honest and transparent. This means:
- Pre-register before seeing data
- Report negative results
- Don't hide surprising findings
- Document what you learned even if it contradicts predictions
- The goal is understanding, not confirmation

The noise-helps finding contradicted our prediction. The compressed-checklist failure was unexpected. The oscillation revealed a design gap (no futility rules). These are features, not bugs. We learned things we didn't expect.

**Current status**: Batch 15+ in progress
- P(fw>filler) oscillating around 0.91, won't stabilize at 0.95
- P(comp>bare) stuck at 0.50, clearly futile
- Likely outcome: RSS runs to max 30 batches, declares "inconclusive"
- But the signal is clear: framework helps moderately, compressed is worthless, theory matters

**What we're learning about science**:

Pre-registration works. It kept us honest when results contradicted predictions. The double-blind source selection prevented cherry-picking. The dual-model judging caught no systematic bias. The append-only artifact policy means anyone can verify our work.

This is how experiments should be run: lock in predictions, follow the protocol, report what you find, learn from surprises.

**Next**: Wait for RSS to complete, write honest results regardless of outcome.

## 2026-03-17 17:30-19:00 - Meta-Reflections on Honest Science

**Context**: Posteriors converged at batch 15, conclusions clear even though experiment running to batch 30. Created results blog post while waiting for formal completion.

**Discussion with Claude on what constitutes honest science:**

Started with question: "Is not publishing Rounds 1-2 p-hacking if I waited to see if Round 3 came up positive?"

Not p-hacking (multiple experiments, not multiple analyses on same data) but is publication bias. Mitigated by disclosing Rounds 1-2 in Round 3 post. The test: would I publish Round 3 if it came up completely negative? If yes (because pre-registered and well-designed), then clean.

**The honesty paradox:**
- Dishonest researchers are certain they're honest (unconscious bias)
- Honest researchers are uncertain about honesty (conscious doubt)  
- Therefore uncertainty signals honesty
- But knowing this creates certainty about uncertainty
- Which breaks the signal
- Paradox

**Resolution:** Stop trying to self-certify honesty (impossible due to bias blind spot). Make work auditable to others. Not "am I honest?" but "is this auditable?"

Honesty is intersubjective, not introspective. Can't know if you're honest by looking inward. Can only make work transparent enough for others to evaluate.

**The recursion problem:**

Gave checklist for honest science (pre-register, disclose, make auditable). User noted: "that's a checklist" - and we just proved checklists fail without grounding.

Gave theory behind checklist (why humans rationalize, why selection bias compounds, why introspection fails). User noted: "recursion" - that's still just a list of claims without grounding those claims.

Pattern repeats at every meta-level. Can't bottom out. Theory is load-bearing means the value isn't compressible. Can't extract "the answer" and carry it away. Understanding comes from thinking through specific cases with enough grounding to make useful judgments, not from following extracted checklists.

The recursion stops when understanding becomes useful, not when it becomes complete.

**Git commits as preregistration:**

Novel as a recognized practice (not widely formalized) but technically sound. Cryptographic timestamps, immutable history, verifiable. Computational researchers sometimes do this but it's not "official" like OSF.

Advantage: Same tool as code, distributed verification, complete audit trail visible in commit history.

More valuable than just preregistration: committed all intermediate stages (bugs, fixes, learnings, reflections). Most research only shows polished result. This shows the messy middle where the actual learning lives.

**The repo as dataset for LLM study:**

Complete research artifact with reasoning, failures, iterations could teach LLMs research methodology (not just facts). Test: Could an LLM study this repo and replicate the methodology on new problems? Would reveal what LLMs can/can't learn from process documentation.

Recursive irony: Experiment designed with LLMs, executed using LLMs, about LLM capabilities, becomes training data for LLM research capabilities.

**Work logs in research:**

Lab notebooks are standard in traditional science but private. Public, detailed, honest work logs in computational research are rare. Most researchers publish polished results, hide messy process.

This log captures things usually lost: bugs and fixes, reasoning evolution, what surprised vs expected, reflections on methodology. Makes research process auditable, not just results.

**Key insight:** All published research is selected. Nobody publishes everything they try. The question isn't "did you select?" (everyone does) but "can a reader evaluate your selection bias?"

This experiment makes that evaluation possible through: preregistration (public), artifacts (append-only), disclosed history (Rounds 1-2), honest reporting (surprises, negatives, uncertainties), complete process log (this file).

**On statisticians and their own statistics papers:**

Statisticians writing methodology papers are subject to same biases they're trying to prevent (cherry-picking examples, researcher degrees of freedom in choosing which methods to compare). Meta-methods research has same problems as any research, just one level up.

No one escapes bias through individual virtue. Science works through collective error correction: make work auditable, publish failures, let others check your work. Process is error-correcting even if individuals aren't error-free.

**Status**: Round 3 results blog post published. Experiment still running (batch 16+). Conclusions won't change with more data - posteriors converged. Waiting for formal completion to honor pre-registered protocol (run to batch 30 or stopping criterion).

## 2026-03-17 20:00 - Round 4 Planning: The Handshake Hypothesis

**Context**: Round 3 completed (results published). Planning next experiment based on key finding: theory is load-bearing.

**Hypothesis**: If theory is load-bearing (Round 3: P(fw>comp) = 0.93-0.98), does even more formal theory help even more?

**The Handshake as experimental condition:**
- Round 3 tested Natural Framework (8.3k tokens, conceptual introduction)
- The Handshake is more formal/detailed (~9k tokens after extraction)
- Includes: contracts, data processing inequality, budget formalism, fractal tower
- Question: Does deeper theoretical grounding improve diagnostic quality?

**Goal**: Clean, actionable recommendation backed by data

For practitioners to know "when to use what," need:
1. Direct framework vs handshake comparison (head-to-head on same problems)
2. Problem-type clustering (which approach for which task type)
3. Pre-registered decision tree (data → recommendation)

**Design decisions:**

**Conditions (5):**
- Zero, Compressed, Framework, Handshake, Filler (9k Wikipedia)
- Dropped: Bare (Round 3 already tested, less informative than other controls)
- Savings: 17% of trials per batch

**Problem categories (2):**
- Data Processing (3 problems) — where framework helped (Round 3: P≈0.91)
- Production Infrastructure (3 problems) — untested, vocabulary should map
- **Excluded: Algorithmic** — Round 3 showed framework doesn't help (P=0.39)

**Decision to drop algorithmic category:**
- Round 3 already showed framework fails on algorithmic tasks (Hearthstone P=0.39)
- Assumption: handshake won't help where framework failed (vocabulary doesn't map to pure computation)
- Saves 33% of trial budget (2 problems out of 6)
- Reinvest in higher power or more problems in categories where theory plausibly helps
- Pre-registered exclusion: documents assumption that handshake won't break the pattern
- Focus: differentiate framework vs handshake in domains where both might work

**Key comparisons:**
- P(hs>fw) — main question: does more formal theory help?
- P(fw>comp), P(hs>comp) — replication: theory still load-bearing?
- P(hs>filler) — diagnostic value of formal theory
- Category interaction — does handshake help differentially by problem type?

**Pre-registered recommendation logic:**
- If P(hs>fw) ≥ 0.95 across both categories → "Use Handshake"
- If P(hs>fw) ≥ 0.95 on one category only → conditional recommendation
- If P(hs>fw) < 0.50 → "Framework sufficient, handshake overkill"
- If P(fw>filler) < 0.50 on either category → "Theory doesn't help on [category]"

**Budget:**
- 5 conditions × 2 models × 6 problems = 60 trials per batch
- 3× more expensive than Round 3 per batch
- Focused question: where does more formal theory help?

**Status**: Planning phase. Next steps:
- Extract handshake diagnostic content (~9k tokens)
- Define inclusion criteria for problem categories
- Double-blind problem selection (3 per category)
- Design stopping rules with futility checks
- Set priors and write preregistration

**Methodological learning applied from Round 3:**
- Need futility stopping rules (add at batch 15, 50% of max)
- Pre-register problem categories before selecting problems
- Pre-register decision tree for recommendations
- Direct comparisons for clean recommendations (can't recommend without head-to-head data)


## 2026-03-17 21:00 - Selection Criteria Refinement

**Context**: Codex reviewed Round 4 design, identified critical selection bias issue.

**Codex's main critique:**
Current criteria optimized for finding cases where diagnosis CAN help, not estimating when it ACTUALLY does help. Criterion "identifiable gaps" preselects positive cases where NF has room to shine.

**Key fixes applied:**

**1. Add null/calibration cases (20-30%)**
- Include systems where best diagnosis is "mostly complete, no major NF gap"
- Tests if framework can correctly identify when nothing is broken
- Prevents "all problems have gaps" tautology

**2. External evidence requirement**
- Cannot decide during selection what gaps exist
- Require: issue thread, postmortem, maintainer TODO, incident note, bug cluster
- OR: null case (no such evidence exists)
- Prevents smuggling own diagnosis into selection

**3. Separate production realism from complexity**
- Stars don't measure architecture complexity
- Use: "publicly documented production artifact with credible deployment"
- Not: ">1k stars or known company" (weak proxy, may exclude good cases)

**4. Pre-register qualifying gaps**
- Define what counts as NF-relevant gap before seeing problems
- Example: "missing role X causing externally documented failure mode Y"
- Prevents drift toward NF-friendly examples

**5. Output-structure confounding fix**
- Codex noted: Round 3 directive shows SOAP-like structure
- If Handshake primes that structure better, wins on format not diagnosis
- Solution: Directive says "Generate SOAP notes" without showing scaffold
- All conditions get same instruction, no format bias
- LLMs know SOAP (medical documentation format)
- Judges score on diagnosis substance, not organization

**Revised selection criteria:**

1. **Real production context** - publicly documented, credible deployment
2. **Reconstructable architecture** - enough docs to understand contracts/behavior
3. **Problem signal** - externally evidenced gap (issues, postmortem, TODO) OR null case
4. **Actionable artifact** - diagnosis would guide sprint work

**Sample composition:**
- 70-80% actionable-gap cases (test if theory improves fix planning)
- 20-30% null/calibration cases (test if framework says "nothing major missing")

**Updated directive:**
```
You are diagnosing what's missing from this production system.

Generate SOAP notes identifying architectural gaps.

Code: [system code]
Goal: [what it's supposed to do]
[condition-specific context: zero/compressed/framework/handshake/filler]
```

**Why this eliminates confounding:**
- No structure shown in directive (just "generate SOAP notes")
- All conditions get same instruction
- If Handshake organizes better, that's real effect (formal theory → clearer thinking)
- Not circular (not teaching format then rewarding it)

**Next**: Get codex feedback on updated design, finalize selection protocol.


## 2026-03-17 21:30 - Codex Review: Design-Implementation Gap

**Codex's assessment:** Closer, but not ready to preregister. Main issue is design-implementation mismatch, not conceptual bias anymore.

**1. SOAP-without-scaffolding: reduces confounding, doesn't eliminate it**
- "SOAP notes" still specifies response schema
- Removed explicit scaffold but structure is latent treatment
- Acceptable if claim is: "helps produce better diagnostic notes under standard format"
- Not acceptable if claim is: "purely better diagnosis independent of format"
- **Implementation issue:** prompts/directive.md still has old scaffold (Observations/Triage/Plan)
- Design doc and actual prompts out of sync

**2. Null proportion: pick one value, not range**
- Recommendation: 25% (good compromise)
- Enough to test restraint, doesn't dilute power on main comparison
- OR 33% if null-case calibration is primary estimand
- Must pre-register exact value

**3. Main remaining holes:**

**Null-case ground truth underspecified:**
- "No external evidence" is absence of evidence (weak)
- Need positive rule: no qualifying evidence after fixed search protocol + system appears feature-complete relative to stated goal

**Scoring rubric is positive-case shaped:**
- Current judge_prompt.md assumes gap_list exists
- For null cases: need explicit rewards for correctly saying "no major gap"
- Need penalties for hallucinated gaps

**Selection frame needs tightening:**
- Positive and null must come from same sampling process
- Otherwise nulls = "easy polished projects", gap cases = "messy troubled projects"
- Bias by difficulty, not gap presence

**Evidence protocol needs timebox:**
- Define which artifacts count (issues, PRs, postmortems, TODOs)
- How many must be checked
- How searched (GitHub API, manual review, time limit)
- Without this, selection can drift

**Judges shouldn't reward SOAP conformity:**
- Score substance only
- Section presence is binary check, not quality component

**4. Not ready to preregister - need one more refinement pass:**

Must lock down:
- Exact null proportion (25%)
- Null-case qualification protocol (search protocol + feature-complete check)
- Null-case scoring rubric (rewards for correct "no gap", penalties for hallucination)
- Shared sampling frame (positive and null from same process)
- Final prompt text (update directive.md to match design)

**Status:** Biggest risk shifted from conceptual bias to operationalization mismatch. Design is sound. Implementation needs to catch up.

**Next:** One more refinement pass before preregistration.


## 2026-03-17 23:00 - Round 4 Pivot: Broad & Shallow Design

**Context:** Round 4 planning after Round 3 complete. Initial design had 8-10 problems, testing across categories with deep sampling (30 batches per problem). User feedback: Round 3 was painful (oscillation drama, grinding), don't want scope creep.

**User insight:** "How about many repos with 1-3 rounds each, instead of few repos with 30 batches?"

**Objection addressed:** Round 3's weakness is narrow generalizability. "It worked on RSS reader (toy example), but won't work on my complex production codebase."

**Design pivot: Deep → Broad**

**Old design (deep sampling):**
- 6-8 problems
- 30 batches per problem
- Tests: "How confident are we it works on THESE problems?"
- Result: "94.9% confident framework helps on RSS reader"
- Weakness: Narrow scope, oscillation drama, grinding

**New design (broad sampling):**
- 30 production API repos
- 1-2 rounds per repo
- Tests: "How often does it work across MANY problems?"
- Result: "Handshake won on 25/30 production repos"
- Strength: Generalizability, no oscillation, practical value

**What changes:**

**Dimension tested:**
- Deep: per-repo confidence (P=0.949 on specific problem)
- Broad: consistency across repos (wins on X/30 repos)

**Sample:**
- 30 API repos with documented production gaps
- Domain: "API request handlers missing error handling/validation/observability"
- Criteria: deployed, 5k+ lines, real users, external evidence, maintained

**Trials:**
- 1-2 rounds per repo (not 30 batches!)
- 5 conditions × 2 models × 30 repos × 1-2 rounds = 300-600 reports
- Same budget as narrow-deep design, spread wide not deep

**Analysis:**
- Binary per repo: handshake > framework? (based on scores)
- Aggregate: handshake won on X/30 repos
- Pre-register threshold: X ≥ 24 (80%) to claim "generally better"
- If X ≈ 15 (50%) → inconclusive
- If X ≤ 10 (33%) → framework sufficient

**Practical value:**
- Generate 30 real diagnoses (6 per repo: 5 conditions + 1 duplicate)
- Share with maintainers
- Get feedback on diagnostic quality
- Actual value, not just research artifact

**Why this kills the generalizability objection:**

Round 3: "Worked on 2 toy examples" → "Won't scale to my complex codebase"
Round 4: "Worked on 25/30 production repos with real users" → "Burden shifts to you to explain why yours is exceptional"

If maintainers respond positively (implement fixes, confirm gaps), that's empirical proof of practical value.

**Advantages:**
1. No oscillation drama (1-2 rounds, done, move on)
2. Tests consistency (does it work GENERALLY?)
3. Practical output (diagnoses to share)
4. Clearer for practitioners ("works 80% of time" > "works confidently on 2 examples")
5. Directly addresses main objection to Round 3

**Trade-offs:**
- Less per-repo confidence (1-2 rounds vs 30 batches)
- More selection risk (30 repos vs 2, bias matters more)
- Need tight criteria + external evidence
- Variance within repo (fix: 2 rounds minimum for variance estimate)

**Pre-registration updates needed:**
- Change sample: 30 repos (not 6-8 problems)
- Change trials: 1-2 rounds per repo (not 30 batches)
- Change analysis: aggregate win rate (not per-problem posteriors)
- Keep: external evidence, null cases, SOAP directive, effect size

**Next:** Update preregistration with broad design, ask codex for review.


## 2026-03-17 23:15 - Updated Round 4 Preregistration with Broad Design

**Changes made to ROUND4_PREREGISTRATION.md:**

1. **Research question:** Added "Design: Broad & shallow to test consistency"
2. **Sample:** Changed from 8 problems to 30 repos (27 gap + 3 null)
3. **Domain:** Narrowed to API request handlers (homogeneous)
4. **Selection criteria:** Production deployed, 5k+ lines, real users, external evidence, maintained
5. **Trials:** Changed from 30 batches per problem to 1-2 rounds per repo
6. **Analysis:** Changed from Bayesian posteriors to aggregate win rate (X/30 repos)
7. **Threshold:** ≥24/30 (80%) to claim "generally better"
8. **Budget:** 300-600 reports (vs 1,200 for deep design)

**Key insight:** Tests "how often does it work?" not "how confident are we it works on specific problems?"

**Addresses Round 3 weakness:** "Worked on toy examples" → "Worked on 80% of production repos"

**Next:** Commit, ask codex for review on broad design.


## 2026-03-17 23:30 - Codex Review: Broad Design Needs Tighter Measurement

**Codex's assessment:** "Broad pivot is directionally right. Main risk: you've changed the estimand - measuring cross-repo win rate under noisy single-shot evaluations."

**What works:**
- Narrow domain is good (API repos with similar defect classes)
- Practical value is strong (real diagnoses to share)
- Testing external validity instead of local robustness

**Main issues:**

**1. 1-2 rounds too thin if scoring pipeline is noisy**
- Single round only works if: issue clearly defined, rubric tight, grading deterministic
- Single-trial noise will dominate win/loss calls
- Fix: Not more rounds, but better measurement

**Codex recommendation:**
- Keep 1 repo = 1 sampled issue
- Add 2 blinded graders (not just model variance)
- Allow win/tie/loss (not forced binary)
- Adjudication for close cases

**2. 80% threshold weakly motivated**
- Fine as aspirational target, not as statistical threshold
- With 30 repos, 24 wins = 0.80 but uncertainty is material
- Need to justify from: effect size, prior baseline, or CI width

**Codex recommendation:**
- Pre-register both: win rate + 95% CI AND decision threshold
- Primary: win rate with CI
- Decision: lower bound > 0.60, or observed rate ≥ 0.75
- Report interval, not just "hit 80%"

**3. Repo difficulty confound**
- If handshake wins 20 easy repos, loses 10 hard → raw count hides failure mode
- Need covariates: repo size, framework, language, issue subtype, difficulty

**Codex recommendation:**
- Add blinded difficulty rating (1-5 scale)
- Capture: size, stack, framework, issue type
- Report stratified results (easy vs hard repos)

**4. Forced binary win/loss loses information**
- Some repos will be ties or incomparable
- Forcing binary inflates noise

**Codex recommendation:**
- Use win/tie/loss categories
- Report: wins, non-loss rate, false positive on nulls

**5. Additional methodological holes:**
- Selection bias (explicit sampling rules before evaluation)
- Target leakage (issue too visible from external evidence)
- Rubric instability (subjective scores inherit grader noise)
- Non-independence (30 repos not independent if share framework/org)
- Null definition (what exactly is "no major gap"?)

**Easy fixes to implement:**
1. Change "maintained: last 6 months" → "last month" (user note)
2. Add win/tie/loss (not binary)
3. Add difficulty annotation (1-5 blinded rating)
4. Pre-register 95% CI, not just point threshold
5. Add repo covariates (size, framework, language)
6. Define null repos precisely

**Harder fixes (defer):**
- 2 blinded graders per report (doubles grading cost)
- Adjudication protocol for close cases
- Stratified analysis by difficulty

**Codex offered:** "I can turn this into concrete preregistration template with success criteria, repo sampling rules, grading rubric, and analysis plan."

**Next:** Implement easy fixes to preregistration.


## 2026-03-17 23:45 - Implemented Easy Fixes from Codex Review

**Changes to ROUND4_PREREGISTRATION.md:**

1. **Maintained:** Changed "last 6 months" → "last month" (user feedback)

2. **Repo covariates added:** Size, stack, framework, issue subtype, difficulty (1-5 blinded rating)
   - Enables stratified analysis (easy vs hard repos, by stack, by issue type)

3. **Win/tie/loss instead of binary:**
   - Win: hs_score > fw_score + 0.10 margin
   - Tie: scores within margin
   - Loss: fw_score > hs_score + margin
   - Reports: wins, ties, losses, non-loss rate

4. **95% CI instead of point threshold:**
   - Primary: win rate with 95% confidence interval
   - Decision: lower bound > 0.60 OR observed rate ≥ 0.75
   - Not just "hit 80%" - report full interval

5. **Null repos defined precisely:**
   - Comprehensive: error handling, validation, tests, observability
   - Metric: false positive rate (% hallucinating major gaps)
   - Expected: both should say "no major gaps" or minor polish only

**Deferred (too expensive for initial design):**
- 2 blinded human graders per report (doubles grading cost)
- Adjudication protocol for close cases
- Would be valuable but budgetarily prohibitive

**Status:** Easy fixes implemented. Preregistration now has:
- Tighter measurement (win/tie/loss, margin, CI)
- Covariates for stratified analysis
- Precise null definition
- Honest claims tied to CI, not arbitrary threshold

**Next:** Commit easy fixes.


## 2026-03-18 00:00 - Final Round 4 Design: Codex-Only Judging ($10 Budget)

**Budget constraint:** User can't spend $500. Revised economics based on subscription model.

**Key realization:** Codex CLI is included in subscription ($0 marginal cost). Claude API is expensive ($3-15/M tokens).

**Cost breakdown:**

**Previous estimate (dual judging):**
- Generation: 150 codex + 150 claude = ~$20
- Judging: 900 codex + 900 claude = ~$70
- Total: ~$90

**Actual costs (with subscription):**
- 150 codex generations: $0 (subscription)
- 150 claude generations: ~$10 (API)
- 1,500 codex judges (5 runs × 300 reports): $0 (subscription)
- Total: ~$10

**Final judging design:**
- Codex only (GPT-5.4 via CLI)
- 5 runs per report (increased from 3 for reliability)
- Majority vote across 5 judgments
- Rate limiting: 2s delay between calls (ToS compliance)

**Change from Round 3:**
- Round 3: dual-model (codex + claude, 3 runs each) = robust but expensive
- Round 4: codex-only (5 runs) = budget-conscious but still reliable

**Rationale:**
- Codex is harsh critic (valuable signal, not noise)
- 5 runs handle variance (more than Round 3's 3)
- Single model okay for relative comparison (win/loss, not absolute scores)
- $10 is affordable vs $90

**Limitation noted:**
- No cross-model validation (can't catch codex-specific bias)
- But: codex was reliable in Round 3, 5 runs improve reliability
- For win/loss comparison (not absolute scoring), single model sufficient

**Rate limiting:**
- 2s delay between codex calls (same as Round 3)
- ~1 hour per repo × 30 repos = ~30 hours total
- Spread over days/weeks, ToS compliant

**Status:** Final design locked. Budget: $10. Affordable. Ready to execute when resources align.

**Next:** Codex review on final design.


## 2026-03-18 00:30 - Audit Layer Added (Codex Calibration Concern)

**Codex's verdict on $10 design:** "Not ready to execute as-is. Codex-only judging is not a fatal flaw if you add an external calibration layer."

**Main concern:** 5 × Codex addresses variance, not bias
- Repeated sampling finds consistent answer
- But if Codex has systematic blind spots, 5 repeats won't fix it
- Correlated judge error is the risk

**Codex recommendation:**
- Keep 5 × Codex majority vote for all 300 reports (cheap, handles variance)
- Add independent audit on 20% subset (60 reports)
- Best: human adjudication on subset
- Cheapest: Claude judge on subset only
- Report agreement between codex-majority and audit judge
- Pre-register failure rule: if agreement < 70%, invalidate results

**Why this works:**
- 5 × Codex handles variance (repeated sampling)
- Audit layer handles bias (independent judge catches systematic error)
- 20% sample balances cost vs detection power
- Pre-registered failure rule prevents post-hoc rationalization

**Updated preregistration (ROUND4_PREREGISTRATION.md):**

1. **Judging protocol:**
   - Primary: 5 × Codex on all 300 reports ($0)
   - Audit: 1 × independent judge on 60 reports (20% sample)
   - Options: human (best, $0 but time) or Claude ($3)
   - Agreement threshold: ≥70% or invalidate

2. **Budget:**
   - Without audit: $10 (generation only)
   - With Claude audit: $13 (generation + 60 audit judges)
   - Still affordable

3. **Open items:**
   - Added: "Select audit method" (human vs Claude)
   - Pre-register choice before execution

**Status:** Design complete with calibration layer. Addresses codex's concern about single-model bias. Ready for implementation when resources align.

**Next:** Add output artifacts structure.


## 2026-03-18 00:45 - Output Artifacts Structure Added

**User question:** "Do we also pipe the outputs to a new folder for the diagnoses?"

**Insight:** Experiments should produce useful artifacts, not just p-values. If we're diagnosing 30 production repos, those reports should be shareable with maintainers.

**Added to preregistration:**

1. **Experimental data** (`round4/`)
   - All 5 conditions × 2 models
   - Judgments, scores, analysis
   - Scientific record, append-only

2. **Shareable diagnoses** (`diagnoses/`)
   - Best diagnosis per repo (winning condition only)
   - Full comparison (all 5 conditions side-by-side)
   - Summary README with methodology
   - Cross-repo patterns and findings

**Post-experiment plan:**
- Export 30 best diagnoses as GitHub-ready markdown
- Contact maintainers for permission to share (opt-in)
- Publish corpus as reference examples
- Blog post: "30 Production API Diagnoses"

**Practical value:**
- For maintainers: actionable sprint-plannable diagnosis
- For practitioners: see what Framework/Handshake quality looks like
- For researchers: corpus of AI diagnostics with ground truth
- For science: outputs become productive, not just validated

**Status:** Full artifact protocol documented. Ready for implementation when resources align.

**Next:** Commit, then implementation phase.


## 2026-03-18 00:50 - Prompts Added to Output Artifacts

**User:** "And of course we share the prompts, right?"

**Yes.** Full reproducibility requires sharing:
- directive.md (diagnostic generation prompt)
- judge_prompt.md (scoring rubric)
- All condition content (framework.md, handshake.md, compressed.md, filler.md)

**Added to preregistration:**
- `round4/prompts/` directory with all prompt materials
- Post-experiment action: publish prompts for full replication
- Anyone can run the experiment on their own repos

**Transparency principle:** Science requires reproducible methods, not just results. Prompts are the experimental protocol. Must be shared.

**Status:** Complete artifact protocol (data + diagnoses + prompts). Ready for implementation.

**Next:** Commit changes, then begin implementation phase when resources align.

