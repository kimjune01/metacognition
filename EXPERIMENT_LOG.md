# Experiment Log - Round 4

**Previous log:** See [EXPERIMENT_LOG_ROUND3.md](EXPERIMENT_LOG_ROUND3.md) for Round 3 execution and completion (2026-03-17).

**This log:** Round 4 planning and execution (2026-03-17 onwards).

---

## 2026-03-17 20:00 - Round 4 Handshake Hypothesis

**Context:** Round 3 complete. P(fw>filler) = 0.9459 on RSS (just missed 0.95), disconfirmed on Hearthstone.

**Key finding:** Theory is load-bearing. P(fw>comp) = 0.93-0.98 across both problems. You can't extract just vocabulary—the grounding makes it applicable.

**Round 4 question:** If theory is load-bearing, does MORE formal theory help even more?

**Hypothesis:** The Handshake (9k tokens of categorical formalism) beats Natural Framework (8.3k tokens of conceptual introduction) for diagnosing production-readiness gaps.

**Why test this:**
- Round 3 showed conceptual theory > checklist
- Handshake adds: categorical contracts, DPI proof, budget analysis, fractal tower
- Question: Does formalization improve applicability, or make it harder to use?

**Design sketch:**
- 2 core categories: data processing + production infrastructure
- 2-3 problems per category
- 2 algorithmic sentinels (test if Handshake rescues)
- 2 null cases (no major gaps)
- Total: 10-12 problems

**Comparisons:**
1. Framework vs Handshake (primary)
2. Framework vs compressed (replication)
3. Handshake vs filler (diagnostic value)
4. Both vs null cases (restraint test)

**Next:** Codex review on experimental design.


## 2026-03-17 21:00 - Selection Criteria Refinement

**User feedback:** "Can we improve project selection with decision criteria? Obviously in real life I would not recommend NF for a passthru pipe."

**Key insight:** Need selection criteria that match the claim scope. Framework isn't for all systems—it's for multi-stage information processing with production-readiness concerns.

**Updated criteria:**

1. **Real production context**
   - Not toy examples or tutorials
   - Actually deployed, serving real users
   - Credible evidence: stars, issues, production incidents

2. **Reconstructable architecture**
   - Documentation sufficient to understand system contracts
   - Can identify what stages exist and what they're supposed to do

3. **Problem signal**
   - External evidence of gaps (issues, PRs, postmortems, TODOs)
   - OR: null case (appears complete after search)

4. **Actionable artifact**
   - Diagnosis would guide actual sprint work
   - Not academic ("system lacks elegance")
   - Practical ("missing retry logic on API calls")

**Why these matter:**
- Prevents selecting systems where framework doesn't apply
- Makes scope of inference clear (production multi-stage systems, not all code)
- External evidence prevents cherry-picking problems we already know the answer to

**Standard reference:** june.kim/diagnosis-llm

**Next:** Start preregistration with refined criteria.


## 2026-03-17 23:00 - Round 4 Pivot to Broad & Shallow Design

**User objective:** "Round 3 was painful enough. I don't want scope creep, but I do want to narrow down the domain to see if we get a more certain result."

**Main objection to Round 3:** "Oh this works for toy RSS readers but it certainly won't work for my complex codebase with paying users."

**Design pivot:** Deep sampling → Broad sampling

**Old design (Round 3):**
- 2 problems × 30 batches = 60 trials per comparison
- Deep confidence on specific problems
- But: only 2 problems, generalizability questioned

**New design (Round 4):**
- 30 repos × 1-2 rounds = 30-60 trials per comparison
- Tests consistency across many repos
- Addresses: "Does it work generally?" not just "Does it work on these two?"

**Key insight:** Testing different dimension
- Round 3: "How confident are we it works on RSS?" (P = 0.9459)
- Round 4: "How often does it work on production repos?" (24/30 = 80%)

**Advantages:**
1. Narrow domain (API request handlers) reduces variance
2. Real production systems (credible external validity)
3. Many examples (addresses "won't scale" objection)
4. Sharable diagnoses (practical value beyond p-values)
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

**2. 80% threshold weakly motivated**
- Fine as aspirational target, not as statistical threshold
- With 30 repos, 24 wins = 0.80 but uncertainty is material
- Need 95% CI + decision threshold (lower bound > 0.60, or observed rate ≥ 0.75)

**3. Repo difficulty confound**
- Need covariates: repo size, framework, language, issue subtype, difficulty (1-5 blinded rating)
- Report stratified results (easy vs hard repos)

**4. Forced binary win/loss loses information**
- Use win/tie/loss categories with margin (0.10 on 5-point scale)
- Report: wins, non-loss rate, false positive on nulls

**Easy fixes implemented:**
1. Changed "maintained: last 6 months" → "last month"
2. Added win/tie/loss (not binary)
3. Added difficulty annotation (1-5 blinded rating)
4. Pre-registered 95% CI, not just point threshold
5. Added repo covariates (size, framework, language)
6. Defined null repos precisely

**Next:** Commit easy fixes.


## 2026-03-18 00:00 - Final Round 4 Design: Codex-Only Judging ($10 Budget)

**Budget constraint:** User can't spend $500.

**Key realization:** Codex CLI is included in subscription ($0 marginal cost). Claude API is expensive.

**Cost breakdown:**
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

**Limitation noted:**
- No cross-model validation (can't catch codex-specific bias)
- But: codex was reliable in Round 3, 5 runs improve reliability

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
- Cheapest: Claude judge on subset only ($3)
- Report agreement between codex-majority and audit judge
- Pre-register failure rule: if agreement < 70%, invalidate results

**Updated preregistration:**
1. Primary: 5 × Codex on all 300 reports ($0)
2. Audit: 1 × independent judge on 60 reports (20% sample)
3. Agreement threshold: ≥70% or invalidate
4. Budget: $10-13 (with optional Claude audit)

**Status:** Design complete with calibration layer. Addresses codex's concern about single-model bias.


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

3. **Prompts** (`round4/prompts/`)
   - directive.md, judge_prompt.md
   - framework.md, handshake.md, compressed.md, filler.md
   - Full reproducibility

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


## 2026-03-18 00:55 - Research Goals Clarified

**User:** "We should make our goals clear in the prereg: learn to science, and produce potentially useful diagnoses."

**Added Research Goals section to preregistration:**

### Goal 1: Learn to do science

**Methodological practice:**
- Pre-registration discipline
- Bayesian stopping with futility rules
- Audit layers for single-model judging
- Broad vs deep sampling trade-offs
- Transparent artifacts (prompts, data, reasoning, mistakes)

**Learning from failure:**
- Round 3 taught us: futility rules, null cases, external evidence, problem clustering
- Each mistake documented, each lesson applied
- Process transparency enables collective error correction

**Value:** Building methodology that others can use for honest prompt engineering experiments.

### Goal 2: Produce potentially useful diagnoses

**Practical artifacts:**
- 30 diagnostic reports on real production API systems
- Actionable gap identification (sprint-plannable)
- Shareable with maintainers (opt-in, with attribution)
- Reference examples of diagnostic quality

**Test in the wild:**
- Do maintainers find these useful?
- Do they act on the diagnoses?
- What's the conversion rate from "diagnosis shared" to "gap fixed"?

**Value:** Experiments should produce useful outputs, not just p-values. If the diagnoses are good, they have immediate practical value beyond the experimental finding.

**Honest accounting:** We don't know if maintainers will appreciate unsolicited diagnoses. That's part of the experiment—both the methodology (does Handshake help?) and the artifact quality (do humans use these outputs?).

**Status:** Dual goals explicit. Design complete. Ready for implementation when resources align.

**Next:** Update with two-phase design.


## 2026-03-18 01:00 - Two-Phase Design: Diagnosis + Implementation

**User insight:** "I think we should only deliver the diagnosis if we can provide a PR about the most critical problem they have at the same time."

**Why this is better:**
- Unsolicited advice = quackery
- Unsolicited contribution with rationale = how OSS works
- Code proves we understood the system
- Concrete value vs abstract critique

**Two-phase approach:**

**Phase 1: Diagnosis (experimental)**
- 30 repos, 5 conditions, statistical testing
- Pre-registered protocol
- Answers: Does theory help? Does formalization help more?
- Budget: ~$10-13

**Phase 2: Implementation (practical validation)**
- 5-10 repos selected from Phase 1
- Implement fix for "most critical gap"
- Submit PR with diagnosis as context
- Answers: Can we prioritize? Can we fix? Will maintainers use it?
- Budget: Human time (implementation)

**Selection for Phase 2:**
- Diagnosis identified clear, fixable gap
- Can be addressed in single PR (not architectural)
- Project is active (commits in last week)
- Gap has external evidence (issues/TODOs)

**Success metrics:**
- 1-2 PRs merged (20-40%)
- 3-5 PRs engaged (60%)
- Conversion funnel: 30 diagnoses → X fixable → Y PRs → Z merged

**User reality check:** "Nobody wants to be told that they need to do more work and pick up the slack, people are lazy, we gotta respect that."

**Acknowledgment:**
- Even good PRs create work (review, test, decide, maintain)
- People are lazy = rational effort conservation
- Most unsolicited PRs ignored (base rate: 1-5%)
- Need to make this as low-friction as possible

**Alternative approach (lower friction):**
- Publish corpus with diagnosis + suggested fixes
- Don't submit PRs (don't create unsolicited work)
- Let maintainers discover and use if interested
- Measure organic adoption (views, stars, references)

**Status:** Two-phase design documented. Phase 2 is post-hoc (not pre-registered). Can decide after Phase 1 whether to submit PRs or just publish corpus.

**Next:** Commit changes, then implementation phase when ready.

