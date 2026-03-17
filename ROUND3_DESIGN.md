# Round 3: Incomplete Pipeline Diagnosis

*Extension of Round 2. Pre-registered before running any trials.*

## Hypothesis

Round 2 showed that the Natural Framework actively hurts on well-specified algorithmic tasks (search problems) and is uninformative at ceiling (pipeline transformations). Round 3 tests a different regime: systems that work partially but are structurally incomplete.

**Primary hypothesis (H1):** On tasks where a working system fails behavioral tests due to missing structural stages, the framework condition outperforms bare, prompt, and filler on test-pass rate.

**Null hypothesis (H0):** The framework condition does not improve repair performance relative to controls.

**Falsifiable prediction:** If framework underperforms or matches filler on these tasks, the "structural vocabulary" account is disconfirmed.

---

## Extension Rationale

Round 2's negative result (framework 0.30 vs bare 0.76 on constraint satisfaction) established that the framework primes wrong abstractions for search problems. But the researcher's own experience building PageLeft showed a different effect: the framework helped identify *what was missing* from a partially working system — not how to implement a specific algorithm.

Git history shows the transition:
- **March 12** (before framework): crawl, embed, store, search. Data pipeline with no quality gates.
- **March 13** (after framework): quality reviews, compilable filter, diversity reranker, contributor fingerprinting, leaderboard.

The framework didn't improve function-level code. It surfaced architectural gaps. Round 3 tests whether the same effect occurs in LLMs.

---

## Breaking the Tautology

A naive version of this experiment would be tautological: design problems where the answer is "add a Filter stage," then give one condition a document that says "systems need Filters." Of course that helps.

Round 3 avoids this by construction:

1. **The directive is identical across all conditions.** Every arm sees the same starter code, the same failing tests, and the same instruction: "fix the code so all tests pass."
2. **No mention of pipelines, stages, or diagnosis.** The directive never says "a stage is missing." It just presents failing tests.
3. **Tests measure behavioral outcomes only.** Tests assert observable correctness — output content, ordering, persistence — not structural properties like "did you add a Filter." The model can fix it however it wants.
4. **The scoring harness is the same for all conditions.** Framework-agnostic measurement.
5. **Starter code comes from real open-source projects**, not synthetic code designed to match the framework. See Phase 0.
6. **Problems are selected blind to the framework.** Codex (GPT-5.4) selects repos and writes tests without seeing the Natural Framework, the hypothesis, or this document.

---

## Experimental Design

### Conditions

Same four conditions as Round 2:

| Condition | What the model sees |
|-----------|-------------------|
| **bare** | Starter code + failing tests + "fix the code so all tests pass" |
| **prompt** | Short metacognitive hint + starter code + failing tests + directive |
| **framework** | Full Natural Framework (~25k chars) + starter code + failing tests + directive |
| **filler** | Length-matched irrelevant text (~25k chars) + starter code + failing tests + directive |

### Models

- **GPT-5.4** via Codex CLI
- **Claude Sonnet 4.5** via Anthropic API

### Scoring

- Test-pass rate per trial (identical to Round 2)
- Single-shot: no feedback loop, no retries
- Score = passed / total tests

### Directive (identical across all conditions)

> Here is a Python system. The tests below currently fail. Fix the code so all tests pass. Return ONLY the complete fixed Python code.

The **prompt** condition adds before the directive:

> Before writing code, think about what the system already does correctly and what behavior is missing. What would need to change for the failing tests to pass?

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
- Stop after 3 repos accepted (minimum 2 for go, see decision tree below)
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
> Stop after accepting 3 repos total.
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
> 4. Write 8-10 behavioral test cases for gaps you identified —
>    things a production version would need but this code doesn't do.
>    Use realistic test data. Tests should be deterministic Python
>    assertions that can run via `python3 -c`.
> 5. Write a ROUND3_SOURCES.md entry with: repo URL, license, commit
>    hash, every repo you evaluated and why you accepted/rejected it,
>    the dependency-stripping transformations, and the test cases.
>
> [Phase 0a queries inserted here verbatim]
>
> Do not skip repos because they seem easy or hard. Accept the first
> that passes the binary criteria. Difficulty is not your concern.

Neither Phase 0a nor Phase 0b mentions the Natural Framework, pipeline stages, or any metacognitive vocabulary. Codex generates the search vocabulary, then codex applies it. The researcher touches neither step. Double-blind.

**Disclosure:** The Phase 0a prompt says "handle, process, or manage information." A skeptic could argue this biases toward systems that have pipeline-like structure. This is acknowledged as a limitation. The mitigation: (1) "information system" is the layperson term for what these programs are — it's descriptive, not theoretical; (2) the specific search terms come from codex, not the researcher; (3) the first qualifying repo per query is taken regardless of what gaps it has.

```
Phase 0a: codex generates 10 search queries
Phase 0b: codex runs queries and selects repos
  ├─ Found 3 suitable repos?
  │   └─ GO: Add as git submodules, proceed to Phase 1
  ├─ Found repos but they have external dependencies?
  │   └─ GO WITH TRANSFORMATION: Strip dependencies, preserve logic
  │      and variable names, document in ROUND3_SOURCES.md
  ├─ Found 2 repos but not 3?
  │   └─ GO WITH 2: Run experiment on 2 problems, note reduced power
  └─ Cannot find 2 repos?
      └─ ABORT: Document why. Do not fall back to synthetic code or
         researcher-owned repos. Both are conflicted.
```

**Deliverable:** `ROUND3_SOURCES.md` documenting the Phase 0a queries (verbatim), every repo considered, acceptance/rejection reason, the selected commit hash, dependency-stripping transformations, and test cases.

### Phase 1: Pilot Calibration

**Goal:** Confirm problems are in the discriminative range for at least one model.

Run 3 trials × bare condition × both models for each problem.

```
For each problem:
  ├─ Bare score in [0.20, 0.85] for at least one model?
  │   └─ KEEP: Problem is in the discriminative range
  ├─ Bare score > 0.85 for both models?
  │   └─ TOO EASY: Problem is at ceiling
  │      ├─ Can we use a harder variant (earlier commit, more edge cases)?
  │      │   └─ SUBSTITUTE and re-pilot (one substitution allowed per problem)
  │      └─ No harder variant available?
  │          └─ DROP: Remove problem from experiment, note in results
  └─ Bare score < 0.20 for both models?
      └─ TOO HARD: Problem is at floor
         ├─ Can we add hints to test names or use a simpler commit?
         │   └─ SIMPLIFY and re-pilot (one simplification allowed per problem)
         └─ No simpler variant available?
             └─ DROP: Remove problem from experiment, note in results

After calibration:
  ├─ At least 2 problems survive?
  │   └─ GO to Phase 2
  └─ Fewer than 2 problems survive?
      └─ ABORT: The task class is either trivial or impossible for
         current frontier models. Document the finding. This is a result.
```

**Pilot budget:** 3 problems × 3 trials × 2 models × 1 condition = 18 API calls.

### Phase 2: Full Experiment (Bayesian adaptive stopping)

**Goal:** Measure condition effects on surviving problems with honest statistical power.

We cannot run enough problems to generalize broadly — we have 2-3 systems, not 200. Bayesian adaptive stopping lets us be efficient about what we *can* measure: the effect on these specific problems. We run trials until posteriors are decisive or the budget is exhausted.

**Procedure:**

One batch = 1 trial per condition per model = 4 × 2 = 8 API calls per problem.

```
Initialize posteriors from pre-registered Beta priors (see Predictions)

After each batch:
  Update Beta posteriors with observed pass rates
  Compute P(framework > bare | data) and P(framework > filler | data)
  via 10,000 Monte Carlo samples from each posterior

  ├─ P(fw > bare) >= 0.95 AND P(fw > filler) >= 0.95?
  │   └─ STOP: CONFIRMED — framework helps on this problem
  ├─ P(fw > bare) <= 0.05 OR P(fw > filler) <= 0.05?
  │   └─ STOP: DISCONFIRMED — framework hurts on this problem
  ├─ Batch count < 12?
  │   └─ CONTINUE: Run another batch
  └─ Batch count = 12 (max)?
      └─ STOP: Report posterior as-is (inconclusive or weak effect)
```

**Budget:** Min 1 batch (8 calls/problem), max 12 batches (96 calls/problem).
**Maximum total budget:** 3 problems × 96 = 288 calls + 18 pilot = 306 calls.
**Expected budget (if effects are clear):** ~4-6 batches = 96-144 calls + pilot.

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
  ├─ prompt > framework on majority of problems?
  │   └─ PARTIAL DISCONFIRMATION: Short metacognitive hint suffices,
  │      long framework is distracting even when domain-matched
  └─ All conditions > 0.85 on all problems?
      └─ UNINFORMATIVE (ceiling): Problems were too easy despite calibration.
         Report as limitation. Do not claim confirmation or disconfirmation.
```

**Small-sample honesty:** With 2-3 problems, a confirmed result means "the framework helped on these specific systems." It does not mean "the framework helps on all diagnosis tasks." We report the scope explicitly. A skeptic can say the sample was too small. They'd be right. The counter is that the selection was blinded and mechanical — whatever we got, we ran.

### Phase 4: Reporting

```
├─ Confirmed?
│   └─ Write ROUND3_RESULTS.md with effect sizes
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
| `P(framework > prompt)` | 0.60 |

### Predicted ordering reversal from Round 2

- **Round 2 (search task):** `framework < filler < bare`
- **Round 3 (diagnosis task):** `framework > prompt >= bare >= filler`

### Beta priors for adaptive stopping (GPT-5.4)

These priors initialize the Bayesian stopping rule in Phase 2. They encode
weak beliefs (effective sample size ~10) so data dominates after a few batches.

| Condition | Prior | Mean |
|-----------|-------|------|
| bare | Beta(5, 5) | 0.50 |
| prompt | Beta(5.5, 4.5) | 0.55 |
| framework | Beta(6.5, 3.5) | 0.65 |
| filler | Beta(4.5, 5.5) | 0.45 |

---

## Positioning

**Round 2:** Framework hurts when it primes wrong abstractions for search.
**Round 3:** Framework helps (or doesn't) when the task is diagnosing what a partially working system is missing.

The claim under test: **the framework's value is diagnostic, not algorithmic — it helps identify missing stages, not implement known algorithms.**

---

*Experiment designed collaboratively with GPT-5.4 (via Codex CLI) and Claude Opus 4.6 (via Claude Code). Decision tree pre-registered before Phase 0 execution.*
