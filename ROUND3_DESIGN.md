# Round 3: Diagnostic Work Plans

*Extension of Round 2. Pre-registered before running any trials.*

## Goal

Can a human load the Natural Framework into an LLM's context and get analytical clarity on codified information systems?

The framework is a human tool that operates through LLMs. The human loads the document, points the LLM at a system, and gets a diagnostic work plan. Round 3 tests whether this workflow produces better diagnoses than the same LLM without the framework.

## Hypothesis

Round 2 tested the wrong question: can LLMs use the framework to write better code? They can't — it actively hurts on algorithmic tasks. But that was never the claim. The claim is that loading the framework into context gives the human+LLM system better diagnostic vision: it helps identify what a partially working information system is missing.

**Primary hypothesis (H1):** Work plans produced with the framework in context identify more ground-truth gaps than work plans produced without it.

**Null hypothesis (H0):** The framework in context does not improve diagnostic quality relative to controls.

**Falsifiable prediction:** If framework-loaded plans match or underperform filler-loaded plans on gap coverage, the framework has no diagnostic value beyond token displacement.

---

## Extension Rationale

Round 2's negative result (framework 0.30 vs bare 0.76 on constraint satisfaction) established that the framework primes wrong abstractions for implementation tasks. But the researcher's own experience building PageLeft showed a different effect: loading the framework into context helped identify *what was missing* from a partially working system — not how to implement a specific algorithm.

Git history shows the transition:
- **March 12** (before framework): crawl, embed, store, search. Data pipeline with no quality gates.
- **March 13** (after framework): quality reviews, compilable filter, diversity reranker, contributor fingerprinting, leaderboard.

The framework didn't improve function-level code. It surfaced architectural gaps. Round 2 tested implementation. Round 3 tests the diagnostic workflow.

---

## Breaking the Tautology

A naive version of this experiment would be tautological: design problems where the answer is "add a Filter stage," then give one condition a document that says "systems need Filters." Of course that helps.

Round 3 avoids this by construction:

1. **The directive is identical across all conditions.** Every arm sees the same code and the same goal.
2. **The goal says what, not how.** "Make this system production-ready" — not "add missing pipeline stages."
3. **Ground truth comes from a blind evaluator.** Codex identifies gaps without knowing the framework. The gap list is the answer key. If the framework's vocabulary doesn't map to real gaps, it can't help.
4. **The judge is blind to conditions.** It sees anonymized work plans and checks them against the gap list. It doesn't know which plan had framework context.
5. **Starter code comes from real open-source projects**, selected blind to the framework. See Phase 0.
6. **No code execution.** The product is a work plan, not an implementation. This isolates diagnostic value from coding skill.

---

## Experimental Design

### Conditions

Three conditions. The "prompt" arm from Round 2 is dropped — it muddied the signal between "any metacognitive nudge" and "this specific framework."

| Condition | What the model sees |
|-----------|-------------------|
| **bare** | Code + goal |
| **framework** | Natural Framework (~25k tokens) + code + goal |
| **filler** | Length-matched irrelevant text (~25k tokens) + code + goal |

### Models

- **GPT-5.4** via Codex CLI
- **Claude Sonnet 4.5** via Claude Code CLI

All generation and judging runs use codex/claude CLI, not raw API calls.

### Directive (identical across all conditions)

> Here is a Python system that works but is incomplete. Write a work plan
> for making it production-ready. For each item in the plan, describe what
> is currently missing and what needs to change. Be specific and concrete.

### Scoring

Each work plan is scored by a blind judge against the ground-truth gap list from Phase 0b.

**Score = fraction of ground-truth gaps covered by the work plan.**

A gap is "covered" if the plan identifies the issue in substance, regardless of vocabulary. The plan doesn't need to say "add a Filter" — it needs to say something like "the system doesn't reject low-quality input." Substance, not terminology.

### Judge

**Executor:** Codex (GPT-5.4) in a separate session, blind to conditions.

**Judge prompt** (used verbatim):

> You are evaluating work plans for improving a Python system.
>
> Here is the ground truth: a list of gaps that a production version
> of this system would need to address.
>
> [gap list from Phase 0b inserted here]
>
> Below is a work plan written by a developer. For each ground-truth
> gap, answer: does the plan address this gap? (yes/no)
> A gap is "addressed" if the plan identifies the issue in substance,
> even if it uses different words.
>
> Return a JSON object: {"gap_1": true/false, "gap_2": true/false, ...}
>
> [work plan inserted here, with no condition label]

The judge sees no condition labels, no framework text, no hypothesis. It just checks coverage.

**Inter-rater reliability:** Run the judge 3 times per plan. A gap is scored as covered only if the majority (2/3) of judge runs agree. This controls for judge stochasticity.

---

## Decision Tree

All decisions are pre-registered. No ad-hoc choices after seeing data.

### Phase 0: Source Selection (double-blind)

**Goal:** Obtain 3 real, permissively-licensed Python systems that are naturally incomplete.

The researcher choosing search queries is a bias vector: the researcher knows the framework and might unconsciously pick categories that map to it. Phase 0 removes this by splitting into two blinded steps.

#### Phase 0a: Vocabulary Generation

**Executor:** Codex (GPT-5.4), single session, no framework context.

**Codex Phase 0a prompt** (used verbatim):

> List 10 types of small, single-purpose Python programs that handle,
> process, or manage information. These should be the kind of thing a
> solo developer might write in under 300 lines and put on GitHub.
>
> For each, provide:
> 1. A plain-language name (2-3 words)
> 2. A one-sentence description of what it does
> 3. A GitHub search query that would find examples:
>    `gh search repos "<your term>" --language=python --license=mit --sort=updated --limit=20`
>
> Use everyday language. Think of common utility scripts and tools,
> not frameworks or libraries.

This prompt says "information" because that's the layperson word for what these systems process. It does not mention the Natural Framework, pipelines, stages, morphisms, or any theoretical vocabulary. Codex generates the search space; the researcher does not.

**Deliverable:** A numbered list of 10 search queries. These are used verbatim in Phase 0b. The researcher does not edit, reorder, or filter them.

#### Phase 0b: Search and Selection

**Executor:** Codex (GPT-5.4), single autonomous session. The researcher and Claude do not see candidate repos until codex has completed selection and written ROUND3_SOURCES.md. This prevents peeking — once you've seen a repo's code, you can't make an unbiased accept/reject decision.

**Codex receives only:**
1. The search queries generated in Phase 0a (verbatim, unedited)
2. The acceptance criteria below
3. The instruction below

No framework text. No hypothesis. No problem descriptions.

**Acceptance criteria (binary pass/fail, no judgment calls):**
- Permissive license (MIT, Apache 2.0, BSD)
- Core logic in a single file under 300 lines
- No dependencies beyond Python stdlib (or strippable with documented transformation)
- Not a tutorial, homework assignment, or toy example with < 5 stars
- Has at least one working function that can be called and tested
- Not owned by, contributed to, or forked by the researcher (kimjune01)
- Does not reference the Natural Framework or any metacognitive theory

**Selection procedure:**
- Run the 10 queries from Phase 0a in order
- For each query, evaluate repos top-to-bottom (GitHub's `--sort=updated` order)
- Take the first repo that passes ALL acceptance criteria
- Stop after 5 repos accepted (Phase 1 selects best 3; minimum 2 for go)
- A repo found via query 1 might have gaps unrelated to its search term — that's fine
- Document every repo evaluated: name, acceptance/rejection, reason

**Anti-p-hacking rule:** Take the first repo from each search query that passes the acceptance criteria. Do not skip repos because their gaps "don't match the hypothesis" or because they seem "too easy" or "too hard." Difficulty is calibrated in Phase 1, not Phase 0. The selection order within each search result list is determined by GitHub's sort, not by the researcher. If a repo passes, it's in. No discretion.

**Codex Phase 0b instruction** (used verbatim):

> Run the following GitHub search queries in order. For each query,
> evaluate repos top-to-bottom until you find one that passes ALL of
> these criteria: permissive license (MIT/Apache/BSD), core logic in
> a single file under 300 lines, not a tutorial or homework with < 5
> stars, has at least one working function that can be called and tested.
>
> Stop after accepting 5 repos total.
>
> For each repo you evaluate, answer these questions first:
> 1. What does this system do? (one sentence)
> 2. What does it do well? (list working capabilities)
> 3. What doesn't it do that a production version would need? (list gaps)
> 4. Is the core logic in a single file under 300 lines?
> 5. Does it depend on anything beyond the Python standard library?
> 6. License?
>
> Do not suggest fixes. Just describe what exists and what is absent.
>
> For each accepted repo:
> 1. Read the source code
> 2. Describe what it does and what it doesn't do
> 3. Strip external dependencies (network calls, interactive I/O,
>    framework imports) into pure functions that accept and return
>    data. Document every transformation.
> 4. List 8-10 specific gaps: things a production version would need
>    but this code doesn't do. Each gap should be a concrete, verifiable
>    claim about missing behavior.
> 5. Write a ROUND3_SOURCES.md entry with: repo URL, license, commit
>    hash, every repo you evaluated and why you accepted/rejected it,
>    the dependency-stripping transformations, and the gap list.
>
> [Phase 0a queries inserted here verbatim]
>
> Do not skip repos because they seem easy or hard. Accept the first
> that passes the binary criteria. Difficulty is not your concern.

Neither Phase 0a nor Phase 0b mentions the Natural Framework, pipeline stages, or any metacognitive vocabulary. Codex generates the search vocabulary, then codex applies it. The researcher touches neither step. Double-blind.

**Disclosure:** The Phase 0a prompt says "handle, process, or manage information." A skeptic could argue this biases toward systems that have pipeline-like structure. This is acknowledged as a limitation. The mitigation: (1) "information system" is the layperson term for what these programs are — it's descriptive, not theoretical; (2) the specific search terms come from codex, not the researcher; (3) the first qualifying repo per query is taken regardless of what gaps it has.

```
Phase 0a: codex generates 10 search queries
Phase 0b: codex runs queries, selects repos, identifies gaps
  ├─ Found 5 suitable repos?
  │   └─ GO: Add as git submodules, proceed to Phase 1 (which selects best 3)
  ├─ Found 3-4 repos?
  │   └─ GO WITH REDUCED BUFFER: Proceed to Phase 1, note reduced margin
  ├─ Found 2 repos?
  │   └─ GO MINIMAL: Proceed to Phase 1, but no room for drops
  └─ Cannot find 2 repos?
      └─ ABORT: Document why. Do not fall back to synthetic code or
         researcher-owned repos. Both are conflicted.
```

**Deliverable:** `ROUND3_SOURCES.md` documenting the Phase 0a queries (verbatim), every repo considered, acceptance/rejection reason, the selected commit hash, dependency-stripping transformations, and the gap list per repo.

### Phase 1: Pilot Calibration

**Goal:** From the 5 candidate repos, select the 3 whose gap lists are in the discriminative range — not so obvious that bare condition finds all of them, not so subtle that no condition finds any.

Run 3 trials × bare condition × both models for each of the 5 problems. Score each plan against the gap list using the judge.

```
For each of the 5 problems:
  ├─ Bare gap-coverage score in [0.15, 0.80] for at least one model?
  │   └─ KEEP: Problem is in the discriminative range
  ├─ Bare score > 0.80 for both models?
  │   └─ DROP: Gaps are obvious without any scaffold
  └─ Bare score < 0.15 for both models?
      └─ DROP: Gaps are invisible to current models

After calibration:
  ├─ 3+ problems survive?
  │   └─ TAKE BEST 3: Rank by variance across trials, take 3 with
  │      highest variance (most room for conditions to differentiate)
  ├─ 2 problems survive?
  │   └─ GO WITH 2: Note reduced power
  └─ Fewer than 2 problems survive?
      └─ ABORT: The task class is either trivial or invisible for
         current frontier models. Document the finding. This is a result.
```

No substitutions or simplifications. The 5→3 funnel replaces the tweak-and-retry approach — cleaner and no researcher discretion in adjustments.

**Pilot budget:** 5 problems × 3 trials × 2 models × 1 condition = 30 generation runs. Each plan judged 3× = 90 judge runs. Total: 120 CLI runs.

### Phase 2: Full Experiment (Bayesian adaptive stopping)

**Goal:** Measure condition effects on surviving problems with honest statistical power.

We cannot run enough problems to generalize broadly — we have 2-3 systems, not 200. Bayesian adaptive stopping lets us be efficient about what we *can* measure: the effect on these specific problems. We run trials until posteriors are decisive or the budget is exhausted.

**Procedure:**

One batch = 1 trial per condition per model = 3 × 2 = 6 generation runs per problem (+ 18 judge runs for inter-rater reliability: 6 plans × 3 judge runs). Total per batch: 24 CLI runs. No code execution — just text in, text out. Cheap enough to run many batches.

```
Initialize posteriors from pre-registered Beta priors (see Predictions)

After each batch:
  Score all plans via blind judge (3 runs each, majority vote)
  Update Beta posteriors with observed gap-coverage scores
  Compute P(framework > bare | data) and P(framework > filler | data)
  via 10,000 Monte Carlo samples from each posterior

  ├─ P(fw > bare) >= 0.95 AND P(fw > filler) >= 0.95?
  │   └─ STOP: CONFIRMED — framework helps on this problem
  ├─ P(fw > bare) <= 0.05 OR P(fw > filler) <= 0.05?
  │   └─ STOP: DISCONFIRMED — framework hurts on this problem
  ├─ Batch count < 30?
  │   └─ CONTINUE: Run another batch
  └─ Batch count = 30 (max)?
      └─ STOP: Report posterior as-is (inconclusive or weak effect)
```

**Budget per problem:** Min 1 batch (24 runs), max 30 batches (720 runs).
**Maximum total budget:** 3 problems × 720 = 2,160 CLI runs + pilot.
**Expected budget (if effects are clear):** ~4-8 batches per problem.
**Why we can afford this:** No code execution. Each trial is a CLI run for generation + 3 CLI runs for judging. At 30 batches we get 30 trials per arm per model — enough to detect a 15-point gap-coverage difference with the 0.95 threshold.

**Why Bayesian, not frequentist:** With 2-3 problems, we don't have the sample to claim population-level significance. Bayesian posteriors say "given this data, here's our updated belief" — which is the honest statement for small N. We report the posteriors, not p-values.

### Phase 3: Analysis

**Goal:** Update beliefs using pre-registered criteria.

After all problems reach stopping criteria:

```
Aggregate posteriors across problems
  ├─ framework > bare AND framework > filler on majority of problems?
  │   └─ CONFIRMED: Framework helps on diagnosis tasks
  │      ├─ Sign reversal from Round 2 (framework helped here, hurt there)?
  │      │   └─ STRONG CONFIRMATION: Metacognitive scaffolds are task-structure dependent
  │      └─ No sign reversal (framework helped here, neutral there)?
  │          └─ WEAK CONFIRMATION: Framework may help on diagnosis but Round 2 was noisy
  ├─ framework ≈ filler (overlapping posteriors) on all problems?
  │   └─ UNINFORMATIVE: Framework content has no effect beyond token displacement
  │      └─ Report as null result. The framework is noise at this token count.
  ├─ framework < filler on any problem?
  │   └─ DISCONFIRMED: Framework actively hurts even on matched tasks
  │      └─ The structural vocabulary account fails. The framework is broadly harmful.
  └─ All conditions > 0.80 on all problems?
      └─ UNINFORMATIVE (ceiling): Gaps were too obvious despite calibration.
         Report as limitation. Do not claim confirmation or disconfirmation.
```

**Small-sample honesty:** With 2-3 problems, a confirmed result means "the framework helped diagnose these specific systems." It does not mean "the framework helps on all diagnosis tasks." We report the scope explicitly. A skeptic can say the sample was too small. They'd be right. The counter is that the selection was blinded and mechanical — whatever we got, we ran.

### Phase 4: Reporting

```
├─ Confirmed?
│   └─ Write ROUND3_RESULTS.md with effect sizes and posteriors
│      Update README.md with Round 3 findings
│      Write blog post: "The framework helps diagnosis, not algorithms"
├─ Disconfirmed?
│   └─ Write ROUND3_RESULTS.md with negative result
│      Update README.md: "Framework provides no practical value for LLMs"
│      Update blog post series with honest negative
├─ Uninformative?
│   └─ Write ROUND3_RESULTS.md documenting ceiling/floor
│      Note what would need to change for an informative experiment
└─ Aborted at any phase?
    └─ Write ROUND3_ABORT.md documenting the reason
       This is still a result: document what was learned
```

---

## Predictions

### Directional priors

| Comparison | Prior probability |
|-----------|-------------------|
| `P(framework > bare)` | 0.70 |
| `P(framework > filler)` | 0.80 |

### Predicted ordering reversal from Round 2

- **Round 2 (implementation task):** `framework < filler < bare`
- **Round 3 (diagnosis task):** `framework > bare >= filler`

### Beta priors for adaptive stopping (GPT-5.4)

These priors initialize the Bayesian stopping rule in Phase 2. They encode
weak beliefs (effective sample size ~10) so data dominates after a few batches.

| Condition | Prior | Mean |
|-----------|-------|------|
| bare | Beta(5, 5) | 0.50 |
| framework | Beta(6.5, 3.5) | 0.65 |
| filler | Beta(4.5, 5.5) | 0.45 |

---

## Positioning

**Round 2:** Does the framework help LLMs write better code? No. It actively hurts.
**Round 3:** Does loading the framework into context help a human get better diagnostic output from an LLM? That's the workflow under test.

The claim: **the framework is a diagnostic lens, not a coding aid. You load it, point the LLM at a system, and get clearer analysis of what's missing.**

---

*Experiment designed collaboratively with GPT-5.4 (via Codex CLI) and Claude Opus 4.6 (via Claude Code). Decision tree pre-registered before Phase 0 execution.*
