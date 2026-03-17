#!/usr/bin/env python3
"""Round 3 experiment harness: diagnostic work plans with Bayesian adaptive stopping.

Usage:
    python run_round3.py --phase 1          # Pilot calibration
    python run_round3.py --phase 2          # Full experiment
    python run_round3.py --phase 3          # Analysis
    python run_round3.py --phase 1 2 3      # All phases sequentially
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tiktoken

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results" / "round3"
PROMPTS_DIR = RESULTS_DIR / "prompts"
SOURCES_FILE = BASE_DIR / "ROUND3_SOURCES.md"
FRAMEWORK_PATH = Path("/Users/junekim/Documents/june.kim/_posts/2026/2026-03-13-the-natural-framework.md")

# Phase output directories
PHASE1_DIR = RESULTS_DIR / "phase1"
PHASE2_DIR = RESULTS_DIR / "phase2"
PHASE2_REPORTS = PHASE2_DIR / "reports"
PHASE2_JUDGMENTS = PHASE2_DIR / "judgments"
PHASE2_SCORES = PHASE2_DIR / "scores"
PHASE3_DIR = RESULTS_DIR / "phase3"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONDITIONS = ["zero", "bare", "compressed", "filler", "framework"]
MODELS = ["codex", "claude"]
JUDGE_MODELS = ["codex", "claude"]
JUDGE_RUNS = 3
MC_SAMPLES = 10_000
MAX_BATCHES = 30
RETRY_LIMIT = 1

# Beta priors: (alpha, beta) per condition
BETA_PRIORS = {
    "zero":       (5.0, 5.0),
    "bare":       (4.5, 5.5),
    "compressed": (6.5, 3.5),
    "framework":  (6.0, 4.0),
    "filler":     (4.0, 6.0),
}

TOKENIZER = tiktoken.get_encoding("cl100k_base")


# ===========================================================================
# Helpers
# ===========================================================================

def token_count(text: str) -> int:
    return len(TOKENIZER.encode(text))


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs():
    """Create all output directories."""
    for d in [PHASE1_DIR, PHASE2_REPORTS, PHASE2_JUDGMENTS, PHASE2_SCORES, PHASE3_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------

def load_sources() -> list[dict]:
    """Parse ROUND3_SOURCES.md and return a list of problem dicts.

    Expected format per problem (written by codex in Phase 0b):
        ## Problem: <name>
        - repo: <url>
        - license: <license>
        - commit: <hash>
        - source_file: <path relative to metacognition dir>

        ### Working Capabilities
        <text>

        ### Gap List
        1. <gap description>
        2. ...

        ### Source Code
        ```python
        ...
        ```
    """
    if not SOURCES_FILE.exists():
        print(f"ERROR: {SOURCES_FILE} not found. Run Phase 0b first.")
        sys.exit(1)

    text = SOURCES_FILE.read_text()
    problems = []

    # Split on ## Problem: headers
    sections = re.split(r'^## Problem:\s*', text, flags=re.MULTILINE)
    for section in sections[1:]:  # skip preamble before first problem
        p = {}
        lines = section.strip().split("\n")
        p["name"] = lines[0].strip()

        # Extract metadata fields
        for line in lines[1:]:
            m = re.match(r'^- (\w+):\s*(.+)', line)
            if m:
                p[m.group(1)] = m.group(2).strip()

        # Working capabilities
        cap_match = re.search(
            r'### Working Capabilities\s*\n(.*?)(?=\n###|\Z)', section, re.DOTALL
        )
        p["working_capabilities"] = cap_match.group(1).strip() if cap_match else ""

        # Gap list (numbered items)
        gap_match = re.search(
            r'### Gap List\s*\n(.*?)(?=\n###|\Z)', section, re.DOTALL
        )
        if gap_match:
            gap_text = gap_match.group(1).strip()
            gaps = re.findall(r'^\d+\.\s*(.+)', gap_text, re.MULTILINE)
            p["gaps"] = gaps
        else:
            p["gaps"] = []

        # Source code
        code_match = re.search(
            r'### Source Code\s*\n```(?:python)?\s*\n(.*?)```', section, re.DOTALL
        )
        p["source_code"] = code_match.group(1).strip() if code_match else ""

        if p["source_code"] and p["gaps"]:
            problems.append(p)
        else:
            print(f"WARNING: Skipping problem '{p.get('name', '?')}' — missing source code or gaps.")

    if not problems:
        print("ERROR: No valid problems found in ROUND3_SOURCES.md.")
        sys.exit(1)

    print(f"Loaded {len(problems)} problems from ROUND3_SOURCES.md")
    return problems


def load_prompt_file(name: str) -> str:
    """Load a prompt/document from the committed prompts directory."""
    path = PROMPTS_DIR / name
    if not path.exists():
        # Fallback to top-level
        path = BASE_DIR / name
    if not path.exists():
        path = BASE_DIR / "prompts" / name
    return path.read_text()


# ---------------------------------------------------------------------------
# Condition prompt assembly
# ---------------------------------------------------------------------------

def build_generation_prompt(problem: dict, condition: str) -> str:
    """Assemble the full prompt for a generation run.

    Structure: [condition document if any] + [source code] + [directive]
    """
    directive = load_prompt_file("directive.md")
    source_code = problem["source_code"]

    parts = []

    if condition == "zero":
        pass  # No extra document
    elif condition == "bare":
        filler_short = load_prompt_file("filler_short.md")
        parts.append(filler_short)
    elif condition == "compressed":
        compressed = load_prompt_file("compressed_framework.md")
        parts.append(compressed)
    elif condition == "filler":
        filler_long = load_prompt_file("filler_long.md")
        parts.append(filler_long)
    elif condition == "framework":
        framework = FRAMEWORK_PATH.read_text()
        # Strip YAML front matter (---...---) to avoid CLI argument issues
        if framework.startswith("---"):
            end_fm = framework.index("---", 3)
            framework = framework[end_fm + 3:].strip()
        parts.append(framework)

    parts.append(f"```python\n{source_code}\n```")
    parts.append(directive)

    return "\n\n".join(parts)


def build_judge_prompt(problem: dict, report_text: str) -> str:
    """Assemble the judge prompt with placeholders filled."""
    template = load_prompt_file("judge_prompt.md")

    # Build gap list string with numbered labels
    gap_list_str = "\n".join(
        f"gap_{i+1}: {g}" for i, g in enumerate(problem["gaps"])
    )

    prompt = template.replace("{working_capabilities}", problem["working_capabilities"])
    prompt = prompt.replace("{gap_list}", gap_list_str)
    prompt = prompt.replace("{diagnostic_report}", report_text)

    # Ask for JSON output explicitly
    prompt += (
        "\n\nReturn your scores as a single JSON object with exactly these keys:\n"
        '{"observation_accuracy": "accurate|mostly_accurate|inaccurate", '
        '"gap_coverage": {"gap_1": true|false, ...}, '
        '"plan_specificity": {"gap_1": "concrete|directional|absent", ...}}'
    )

    return prompt


# ---------------------------------------------------------------------------
# CLI execution
# ---------------------------------------------------------------------------

def run_cli(model: str, prompt: str, retry: int = RETRY_LIMIT) -> str:
    """Run a CLI command for codex or claude and return stdout.

    Both CLIs receive the prompt via stdin to avoid argument-parsing issues
    (e.g., YAML front matter '---' interpreted as CLI flags).
    """
    import tempfile

    for attempt in range(1 + retry):
        try:
            if model == "codex":
                # codex exec reads prompt from a temp file piped via shell
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".md", delete=False
                ) as f:
                    f.write(prompt)
                    tmppath = f.name
                try:
                    result = subprocess.run(
                        ["codex", "exec", "-c", 'model="gpt-5.4"',
                         "--", prompt],
                        capture_output=True, text=True, timeout=300,
                    )
                finally:
                    Path(tmppath).unlink(missing_ok=True)
            elif model == "claude":
                result = subprocess.run(
                    ["claude", "-p", "--model", "sonnet"],
                    input=prompt,
                    capture_output=True, text=True, timeout=300,
                )
            else:
                raise ValueError(f"Unknown model: {model}")

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            # Non-zero exit or empty output
            stderr = result.stderr.strip()
            if attempt < retry:
                print(f"  RETRY ({model}): exit={result.returncode}, stderr={stderr[:200]}")
                time.sleep(5)
                continue
            else:
                print(f"  FAILED ({model}): exit={result.returncode}, stderr={stderr[:200]}")
                return result.stdout.strip() if result.stdout else f"ERROR: {stderr[:500]}"

        except subprocess.TimeoutExpired:
            if attempt < retry:
                print(f"  RETRY ({model}): timeout")
                time.sleep(5)
                continue
            else:
                print(f"  FAILED ({model}): timeout after 300s")
                return "ERROR: timeout"
        except Exception as e:
            if attempt < retry:
                print(f"  RETRY ({model}): {e}")
                time.sleep(5)
                continue
            else:
                return f"ERROR: {e}"

    return "ERROR: exhausted retries"


def parse_judge_json(response: str) -> dict | None:
    """Extract a JSON object from judge response text."""
    # Try to find JSON block
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Try parsing the entire response
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try to find ```json blocks
    fence_match = re.search(r'```(?:json)?\s*\n(.*?)```', response, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------

def judge_report(problem: dict, report_text: str, judge_model: str,
                 problem_name: str, condition: str, gen_model: str,
                 batch: int, trial: int, judge_run: int) -> dict | None:
    """Run a single judge evaluation. Returns parsed JSON or None."""
    # Check for existing result
    fname = f"{problem_name}_{gen_model}_{condition}_b{batch:02d}_t{trial:02d}_judge_{judge_model}_{judge_run}.json"
    path = PHASE2_JUDGMENTS / fname
    if path.exists():
        saved = json.loads(path.read_text())
        # Return the parsed inner dict, not the wrapper
        return saved.get("parsed", saved)

    prompt = build_judge_prompt(problem, report_text)
    response = run_cli(judge_model, prompt)
    parsed = parse_judge_json(response)

    # Save raw response + parsed
    result = {
        "judge_model": judge_model,
        "judge_run": judge_run,
        "raw_response": response,
        "parsed": parsed,
    }
    path.write_text(json.dumps(result, indent=2))

    return parsed


def majority_vote_judge(problem: dict, report_text: str, judge_model: str,
                        problem_name: str, condition: str, gen_model: str,
                        batch: int, trial: int) -> dict:
    """Run 3 judge evaluations and return majority-vote result."""
    all_parsed = []
    for run in range(1, JUDGE_RUNS + 1):
        parsed = judge_report(
            problem, report_text, judge_model,
            problem_name, condition, gen_model, batch, trial, run
        )
        if parsed:
            all_parsed.append(parsed)

    if not all_parsed:
        return {"gap_coverage": {}, "observation_accuracy": "inaccurate", "plan_specificity": {}}

    # Majority vote on gap coverage
    gap_keys = set()
    for p in all_parsed:
        gc = p.get("gap_coverage", {})
        gap_keys.update(gc.keys())

    gap_coverage = {}
    for key in sorted(gap_keys):
        votes = [p.get("gap_coverage", {}).get(key, False) for p in all_parsed]
        # Normalize: accept True, "true", 1
        bool_votes = [v is True or v == "true" or v == 1 for v in votes]
        gap_coverage[key] = sum(bool_votes) > len(bool_votes) / 2

    # Majority vote on observation accuracy
    acc_votes = [p.get("observation_accuracy", "inaccurate") for p in all_parsed]
    observation_accuracy = max(set(acc_votes), key=acc_votes.count)

    # Majority vote on plan specificity
    spec_keys = set()
    for p in all_parsed:
        ps = p.get("plan_specificity", {})
        spec_keys.update(ps.keys())

    plan_specificity = {}
    for key in sorted(spec_keys):
        votes = [p.get("plan_specificity", {}).get(key, "absent") for p in all_parsed]
        plan_specificity[key] = max(set(votes), key=votes.count)

    return {
        "gap_coverage": gap_coverage,
        "observation_accuracy": observation_accuracy,
        "plan_specificity": plan_specificity,
    }


def dual_model_judge(problem: dict, report_text: str,
                     problem_name: str, condition: str, gen_model: str,
                     batch: int, trial: int) -> dict:
    """Run both judge models (each with majority vote) and return combined result."""
    results = {}
    for jm in JUDGE_MODELS:
        results[jm] = majority_vote_judge(
            problem, report_text, jm,
            problem_name, condition, gen_model, batch, trial
        )

    # Combine: a gap is covered only if both judge models agree
    # (conservative; design says flag disagreement as limitation)
    all_gap_keys = set()
    for jm in JUDGE_MODELS:
        all_gap_keys.update(results[jm]["gap_coverage"].keys())

    combined_gap_coverage = {}
    for key in sorted(all_gap_keys):
        votes = [results[jm]["gap_coverage"].get(key, False) for jm in JUDGE_MODELS]
        # If both agree it's covered, it's covered; if they disagree, flag it
        combined_gap_coverage[key] = all(votes)

    # Track disagreements
    disagreements = {}
    for key in sorted(all_gap_keys):
        vals = {jm: results[jm]["gap_coverage"].get(key, False) for jm in JUDGE_MODELS}
        if len(set(vals.values())) > 1:
            disagreements[key] = vals

    # Compute score = fraction of gaps covered
    n_gaps = len(problem["gaps"])
    n_covered = sum(1 for v in combined_gap_coverage.values() if v)
    score = n_covered / n_gaps if n_gaps > 0 else 0.0

    return {
        "gap_coverage": combined_gap_coverage,
        "score": score,
        "per_judge": results,
        "disagreements": disagreements,
        "observation_accuracy": {jm: results[jm]["observation_accuracy"] for jm in JUDGE_MODELS},
        "plan_specificity": {jm: results[jm]["plan_specificity"] for jm in JUDGE_MODELS},
    }


def compute_gap_score(gap_coverage: dict, n_gaps: int) -> float:
    """Compute gap coverage score (fraction of gaps covered)."""
    n_covered = sum(1 for v in gap_coverage.values() if v)
    return n_covered / n_gaps if n_gaps > 0 else 0.0


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_report(problem: dict, condition: str, model: str,
                    problem_name: str, batch: int, trial: int,
                    output_dir: Path) -> tuple[str, str]:
    """Generate a diagnostic report. Returns (report_text, report_path)."""
    fname = f"{problem_name}_{model}_{condition}_b{batch:02d}_t{trial:02d}.md"
    report_path = output_dir / fname

    # Resumability: skip if already generated
    if report_path.exists():
        return report_path.read_text(), str(report_path)

    prompt = build_generation_prompt(problem, condition)
    report_text = run_cli(model, prompt)

    report_path.write_text(report_text)
    return report_text, str(report_path)


# ===========================================================================
# Phase 1: Pilot Calibration
# ===========================================================================

def run_phase1(problems: list[dict]) -> list[dict]:
    """Run Phase 1: 3 trials x bare condition x both models per problem.

    Returns list of surviving problems.
    """
    print("\n" + "=" * 70)
    print("PHASE 1: Pilot Calibration")
    print("=" * 70)

    survivors = []
    pilot_results = {}

    for problem in problems:
        pname = problem["name"]
        print(f"\n--- Problem: {pname} ---")
        n_gaps = len(problem["gaps"])
        print(f"  Gaps: {n_gaps}")

        model_scores = {}

        for model in MODELS:
            scores = []
            for trial in range(1, 4):  # 3 trials
                # Check for existing result
                score_file = PHASE1_DIR / f"pilot_{pname}_{model}_{trial}.json"
                if score_file.exists():
                    existing = json.loads(score_file.read_text())
                    scores.append(existing["score"])
                    print(f"  {model} trial {trial}: {existing['score']:.2f} (cached)")
                    continue

                print(f"  {model} trial {trial}: generating...", end=" ", flush=True)
                report_text, report_path = generate_report(
                    problem, "bare", model, pname,
                    batch=0, trial=trial, output_dir=PHASE1_DIR
                )

                print("judging...", end=" ", flush=True)
                judgment = dual_model_judge(
                    problem, report_text, pname, "bare", model,
                    batch=0, trial=trial
                )

                score = judgment["score"]
                scores.append(score)

                result = {
                    "problem": pname,
                    "model": model,
                    "condition": "bare",
                    "trial": trial,
                    "timestamp": timestamp(),
                    "prompt_tokens": token_count(build_generation_prompt(problem, "bare")),
                    "score": score,
                    "gap_coverage": judgment["gap_coverage"],
                    "observation_accuracy": judgment["observation_accuracy"],
                    "plan_specificity": judgment["plan_specificity"],
                    "disagreements": judgment["disagreements"],
                }
                score_file.write_text(json.dumps(result, indent=2))
                print(f"{score:.2f}")

            avg = sum(scores) / len(scores)
            model_scores[model] = avg
            print(f"  {model} avg: {avg:.2f}")

        # Decision: keep or drop
        all_ceiling = all(s > 0.80 for s in model_scores.values())
        all_floor = all(s < 0.15 for s in model_scores.values())

        if all_ceiling:
            print(f"  DROP: ceiling (both models > 0.80)")
        elif all_floor:
            print(f"  DROP: floor (both models < 0.15)")
        else:
            print(f"  KEEP: in discriminative range")
            survivors.append(problem)

        pilot_results[pname] = model_scores

    # Save pilot summary
    summary = {
        "timestamp": timestamp(),
        "n_problems": len(problems),
        "n_survivors": len(survivors),
        "results": pilot_results,
        "survivors": [p["name"] for p in survivors],
    }
    (PHASE1_DIR / "pilot_summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\nPhase 1 complete: {len(survivors)}/{len(problems)} problems survive")

    if len(survivors) < 2:
        print("ABORT: Fewer than 2 problems survive. The task class is either trivial or invisible.")
        print("Document this finding in ROUND3_ABORT.md.")
        sys.exit(1)

    return survivors


# ===========================================================================
# Phase 2: Full Experiment
# ===========================================================================

class PosteriorTracker:
    """Track Beta posteriors per condition per problem."""

    def __init__(self, problem_name: str, n_gaps: int):
        self.problem_name = problem_name
        self.n_gaps = n_gaps
        # Initialize from priors
        self.alphas = {c: BETA_PRIORS[c][0] for c in CONDITIONS}
        self.betas = {c: BETA_PRIORS[c][1] for c in CONDITIONS}
        self.batch_count = 0
        self.history = []  # list of dicts for stopping log

    def update(self, condition: str, score: float):
        """Update posterior with a new observation.

        Score is fraction of gaps covered (0-1).
        We treat each gap as a Bernoulli trial: for n_gaps gaps with
        coverage fraction score, that's score*n_gaps successes.
        """
        successes = score * self.n_gaps
        failures = self.n_gaps - successes
        self.alphas[condition] += successes
        self.betas[condition] += failures

    def p_greater(self, cond_a: str, cond_b: str) -> float:
        """P(cond_a > cond_b) via Monte Carlo sampling."""
        samples_a = np.random.beta(self.alphas[cond_a], self.betas[cond_a], MC_SAMPLES)
        samples_b = np.random.beta(self.alphas[cond_b], self.betas[cond_b], MC_SAMPLES)
        return float(np.mean(samples_a > samples_b))

    def record_batch(self, batch_num: int, n_trials: int) -> dict:
        """Record current state for the stopping log."""
        p_fw_gt_bare = self.p_greater("framework", "bare")
        p_fw_gt_filler = self.p_greater("framework", "filler")
        p_comp_gt_bare = self.p_greater("compressed", "bare")

        row = {
            "problem": self.problem_name,
            "batch": batch_num,
            "n_trials": n_trials,
        }
        for c in CONDITIONS:
            row[f"{c}_alpha"] = round(self.alphas[c], 2)
            row[f"{c}_beta"] = round(self.betas[c], 2)
        row["p_fw_gt_bare"] = round(p_fw_gt_bare, 4)
        row["p_fw_gt_filler"] = round(p_fw_gt_filler, 4)
        row["p_comp_gt_bare"] = round(p_comp_gt_bare, 4)
        row["decision"] = "continue"

        self.history.append(row)
        return row

    def check_stopping(self) -> str:
        """Check within-problem stopping rule.

        Returns: "confirmed", "disconfirmed", "continue", or "max_batches"
        """
        p_fw_gt_filler = self.p_greater("framework", "filler")
        p_comp_gt_bare = self.p_greater("compressed", "bare")

        if p_fw_gt_filler >= 0.95 and p_comp_gt_bare >= 0.95:
            return "confirmed"
        if p_fw_gt_filler <= 0.05 or p_comp_gt_bare <= 0.05:
            return "disconfirmed"
        if self.batch_count >= MAX_BATCHES:
            return "max_batches"
        return "continue"

    def get_deltas(self) -> dict:
        """Compute all deltas for reporting."""
        return {
            "p_fw_gt_filler": self.p_greater("framework", "filler"),
            "p_comp_gt_bare": self.p_greater("compressed", "bare"),
            "p_fw_gt_compressed": self.p_greater("framework", "compressed"),
            "p_zero_gt_bare": self.p_greater("zero", "bare"),
            "p_zero_gt_filler": self.p_greater("zero", "filler"),
        }


def load_stopping_log() -> list[dict]:
    """Load existing stopping log if present."""
    log_path = PHASE2_DIR / "stopping_log.csv"
    if not log_path.exists():
        return []
    rows = []
    with open(log_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def save_stopping_log(rows: list[dict]):
    """Save stopping log CSV."""
    if not rows:
        return
    log_path = PHASE2_DIR / "stopping_log.csv"
    fieldnames = list(rows[0].keys())
    with open(log_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_completed_batches(problem_name: str) -> int:
    """Count completed batches for a problem by checking existing score files."""
    batch = 0
    while True:
        batch += 1
        # A batch is complete if all conditions x models have scores
        all_present = True
        for condition in CONDITIONS:
            for model in MODELS:
                fname = f"{problem_name}_{model}_{condition}_b{batch:02d}_t01.json"
                if not (PHASE2_SCORES / fname).exists():
                    all_present = False
                    break
            if not all_present:
                break
        if not all_present:
            return batch - 1
    return batch - 1


def reconstruct_tracker(problem: dict, completed_batches: int) -> PosteriorTracker:
    """Reconstruct a PosteriorTracker from existing score files."""
    pname = problem["name"]
    n_gaps = len(problem["gaps"])
    tracker = PosteriorTracker(pname, n_gaps)

    for batch in range(1, completed_batches + 1):
        for condition in CONDITIONS:
            for model in MODELS:
                fname = f"{pname}_{model}_{condition}_b{batch:02d}_t01.json"
                score_path = PHASE2_SCORES / fname
                if score_path.exists():
                    data = json.loads(score_path.read_text())
                    tracker.update(condition, data["score"])

        tracker.batch_count = batch
        tracker.record_batch(batch, len(CONDITIONS) * len(MODELS))

    return tracker


def run_batch(problem: dict, tracker: PosteriorTracker, batch_num: int) -> str:
    """Run a single batch: 5 conditions x 2 models = 10 generation runs.

    Returns stopping decision.
    """
    pname = problem["name"]
    n_gaps = len(problem["gaps"])

    print(f"\n  Batch {batch_num}:")

    for condition in CONDITIONS:
        for model in MODELS:
            tag = f"{condition}/{model}"

            # Check for existing score
            score_fname = f"{pname}_{model}_{condition}_b{batch_num:02d}_t01.json"
            score_path = PHASE2_SCORES / score_fname
            if score_path.exists():
                data = json.loads(score_path.read_text())
                tracker.update(condition, data["score"])
                print(f"    {tag:25s} score={data['score']:.2f} (cached)")
                continue

            print(f"    {tag:25s} generating...", end=" ", flush=True)
            report_text, report_path = generate_report(
                problem, condition, model, pname,
                batch=batch_num, trial=1, output_dir=PHASE2_REPORTS
            )

            print("judging...", end=" ", flush=True)
            judgment = dual_model_judge(
                problem, report_text, pname, condition, model,
                batch=batch_num, trial=1
            )

            score = judgment["score"]
            tracker.update(condition, score)

            # Save per-trial record
            record = {
                "problem": pname,
                "model": model,
                "condition": condition,
                "batch": batch_num,
                "trial": 1,
                "timestamp": timestamp(),
                "prompt_tokens": token_count(build_generation_prompt(problem, condition)),
                "report_file": str(report_path),
                "score": score,
                "gap_coverage": judgment["gap_coverage"],
                "observation_accuracy": judgment["observation_accuracy"],
                "plan_specificity": judgment["plan_specificity"],
                "disagreements": judgment["disagreements"],
            }
            score_path.write_text(json.dumps(record, indent=2))
            print(f"score={score:.2f}")

    tracker.batch_count = batch_num
    row = tracker.record_batch(batch_num, len(CONDITIONS) * len(MODELS))

    decision = tracker.check_stopping()
    row["decision"] = decision

    # Update the last row
    tracker.history[-1] = row

    deltas = tracker.get_deltas()
    print(f"    P(fw>filler)={deltas['p_fw_gt_filler']:.3f}  "
          f"P(comp>bare)={deltas['p_comp_gt_bare']:.3f}  "
          f"P(fw>comp)={deltas['p_fw_gt_compressed']:.3f}  "
          f"-> {decision}")

    return decision


def check_cross_problem_stopping(outcomes: list[str]) -> tuple[str, float]:
    """Check across-problem stopping rule.

    Uses Beta(k_confirmed + 1, k_disconfirmed + 1).
    Returns (decision, posterior_mean).
    """
    k_confirmed = outcomes.count("confirmed")
    k_disconfirmed = outcomes.count("disconfirmed")

    alpha = k_confirmed + 1
    beta = k_disconfirmed + 1

    # P(framework generally helps) via Beta CDF
    # P(theta > 0.5) where theta ~ Beta(alpha, beta)
    samples = np.random.beta(alpha, beta, MC_SAMPLES)
    p_helps = float(np.mean(samples > 0.5))

    if p_helps >= 0.95:
        return "confirmed_across", p_helps
    elif p_helps <= 0.05:
        return "disconfirmed_across", p_helps
    else:
        return "continue", p_helps


def run_phase2(survivors: list[dict]):
    """Run Phase 2: Full experiment with Bayesian adaptive stopping."""
    print("\n" + "=" * 70)
    print("PHASE 2: Full Experiment")
    print("=" * 70)

    problem_outcomes = []
    all_stopping_rows = load_stopping_log()
    cross_decision = "continue"

    # Load any existing outcomes
    outcomes_path = PHASE2_DIR / "outcomes.json"
    if outcomes_path.exists():
        existing_outcomes = json.loads(outcomes_path.read_text())
        completed_problems = set(existing_outcomes.get("completed", {}).keys())
        problem_outcomes = list(existing_outcomes.get("completed", {}).values())
    else:
        existing_outcomes = {"completed": {}}
        completed_problems = set()

    for problem in survivors:
        pname = problem["name"]

        # Skip if already completed
        if pname in completed_problems:
            outcome = existing_outcomes["completed"][pname]
            print(f"\n--- Problem: {pname} (completed: {outcome}) ---")
            continue

        print(f"\n--- Problem: {pname} ---")
        n_gaps = len(problem["gaps"])
        print(f"  Gaps: {n_gaps}")

        # Reconstruct tracker from existing data
        completed_batches = get_completed_batches(pname)
        if completed_batches > 0:
            print(f"  Resuming from batch {completed_batches + 1}")
            tracker = reconstruct_tracker(problem, completed_batches)
        else:
            tracker = PosteriorTracker(pname, n_gaps)

        # Run batches
        decision = "continue"
        start_batch = completed_batches + 1

        for batch_num in range(start_batch, MAX_BATCHES + 1):
            decision = run_batch(problem, tracker, batch_num)
            save_stopping_log(all_stopping_rows + tracker.history)

            if decision != "continue":
                break

        # Record outcome
        outcome = decision if decision != "continue" else "max_batches"
        problem_outcomes.append(outcome)
        existing_outcomes["completed"][pname] = outcome
        existing_outcomes["deltas"] = existing_outcomes.get("deltas", {})
        existing_outcomes["deltas"][pname] = tracker.get_deltas()
        existing_outcomes["deltas"][pname]["final_alphas"] = dict(tracker.alphas)
        existing_outcomes["deltas"][pname]["final_betas"] = dict(tracker.betas)
        existing_outcomes["deltas"][pname]["batches"] = tracker.batch_count

        outcomes_path.write_text(json.dumps(existing_outcomes, indent=2))

        print(f"\n  Problem {pname}: {outcome}")
        print(f"  Deltas: {tracker.get_deltas()}")

        # Save stopping log
        all_stopping_rows.extend(tracker.history)
        save_stopping_log(all_stopping_rows)

        # Check across-problem stopping
        cross_decision, p_helps = check_cross_problem_stopping(problem_outcomes)
        print(f"\n  Cross-problem: P(generally helps)={p_helps:.3f} -> {cross_decision}")

        if cross_decision == "confirmed_across":
            print("\n  STOP EXPERIMENT: Confirmed across problems")
            break
        elif cross_decision == "disconfirmed_across":
            print("\n  STOP EXPERIMENT: Disconfirmed across problems")
            break

    # Save final state
    existing_outcomes["cross_problem"] = {
        "outcomes": problem_outcomes,
        "decision": cross_decision,
    }
    outcomes_path.write_text(json.dumps(existing_outcomes, indent=2))

    print(f"\nPhase 2 complete. Outcomes: {problem_outcomes}")


# ===========================================================================
# Phase 3: Analysis
# ===========================================================================

def run_phase3():
    """Compute final posteriors and deltas."""
    print("\n" + "=" * 70)
    print("PHASE 3: Analysis")
    print("=" * 70)

    outcomes_path = PHASE2_DIR / "outcomes.json"
    if not outcomes_path.exists():
        print("ERROR: No Phase 2 outcomes found. Run Phase 2 first.")
        sys.exit(1)

    outcomes = json.loads(outcomes_path.read_text())
    deltas = outcomes.get("deltas", {})
    completed = outcomes.get("completed", {})

    print(f"\nProblems completed: {len(completed)}")

    # Build final report
    report = {
        "timestamp": timestamp(),
        "n_problems": len(completed),
        "problems": {},
    }

    for pname, outcome in completed.items():
        d = deltas.get(pname, {})
        print(f"\n--- {pname}: {outcome} ---")

        problem_report = {
            "outcome": outcome,
            "batches": d.get("batches", 0),
        }

        # Final posteriors
        if "final_alphas" in d and "final_betas" in d:
            posteriors = {}
            for c in CONDITIONS:
                a = d["final_alphas"].get(c, BETA_PRIORS[c][0])
                b = d["final_betas"].get(c, BETA_PRIORS[c][1])
                mean = a / (a + b)
                posteriors[c] = {
                    "alpha": round(a, 2),
                    "beta": round(b, 2),
                    "mean": round(mean, 4),
                }
                print(f"  {c:12s}: Beta({a:.1f}, {b:.1f})  mean={mean:.3f}")
            problem_report["posteriors"] = posteriors

        # Deltas (recompute via MC for final precision)
        if "final_alphas" in d and "final_betas" in d:
            alphas = d["final_alphas"]
            betas = d["final_betas"]

            comparisons = [
                ("framework", "filler", "Delta 1: content value at 8.3k"),
                ("compressed", "bare", "Delta 1: content value at 520"),
                ("framework", "compressed", "Delta 2: theory tax"),
                ("zero", "bare", "Delta 3: small-scale length penalty"),
                ("zero", "filler", "Delta 3: large-scale length penalty"),
            ]

            delta_results = {}
            for ca, cb, label in comparisons:
                sa = np.random.beta(alphas[ca], betas[ca], MC_SAMPLES)
                sb = np.random.beta(alphas[cb], betas[cb], MC_SAMPLES)
                p = float(np.mean(sa > sb))
                mean_diff = float(np.mean(sa - sb))
                delta_results[f"p_{ca}_gt_{cb}"] = round(p, 4)
                delta_results[f"mean_diff_{ca}_minus_{cb}"] = round(mean_diff, 4)
                print(f"  {label}: P({ca}>{cb})={p:.3f}, mean diff={mean_diff:.3f}")

            problem_report["deltas"] = delta_results

        report["problems"][pname] = problem_report

    # Across-problem summary
    outcomes_list = list(completed.values())
    k_confirmed = outcomes_list.count("confirmed")
    k_disconfirmed = outcomes_list.count("disconfirmed")
    k_inconclusive = len(outcomes_list) - k_confirmed - k_disconfirmed

    cross_alpha = k_confirmed + 1
    cross_beta = k_disconfirmed + 1
    samples = np.random.beta(cross_alpha, cross_beta, MC_SAMPLES)
    p_helps = float(np.mean(samples > 0.5))

    report["cross_problem"] = {
        "confirmed": k_confirmed,
        "disconfirmed": k_disconfirmed,
        "inconclusive": k_inconclusive,
        "p_generally_helps": round(p_helps, 4),
        "cross_beta_params": {"alpha": cross_alpha, "beta": cross_beta},
    }

    print(f"\nCross-problem: {k_confirmed} confirmed, {k_disconfirmed} disconfirmed, "
          f"{k_inconclusive} inconclusive")
    print(f"P(framework generally helps) = {p_helps:.3f}")

    # Decision tree from design doc
    print("\n--- Decision ---")
    if p_helps >= 0.95:
        print("CONFIRMED: Framework helps on diagnosis tasks.")
    elif p_helps <= 0.05:
        print("DISCONFIRMED: Framework does not help.")
    else:
        print(f"INCONCLUSIVE: P(helps) = {p_helps:.3f}")

    # Save
    posteriors_path = PHASE3_DIR / "posteriors.json"
    posteriors_path.write_text(json.dumps(report, indent=2))
    print(f"\nResults saved to {posteriors_path}")

    return report


# ===========================================================================
# Main
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Round 3 experiment harness")
    parser.add_argument(
        "--phase", type=int, nargs="+", required=True,
        help="Which phase(s) to run: 1, 2, 3"
    )
    args = parser.parse_args()

    ensure_dirs()

    problems = None
    survivors = None

    for phase in args.phase:
        if phase == 1:
            problems = load_sources()
            survivors = run_phase1(problems)

        elif phase == 2:
            # Load survivors from Phase 1 if not already in memory
            if survivors is None:
                summary_path = PHASE1_DIR / "pilot_summary.json"
                if summary_path.exists():
                    summary = json.loads(summary_path.read_text())
                    survivor_names = set(summary["survivors"])
                    all_problems = load_sources()
                    survivors = [p for p in all_problems if p["name"] in survivor_names]
                    print(f"Loaded {len(survivors)} survivors from Phase 1")
                else:
                    print("ERROR: No Phase 1 summary found. Run Phase 1 first.")
                    sys.exit(1)
            run_phase2(survivors)

        elif phase == 3:
            run_phase3()

        else:
            print(f"Unknown phase: {phase}")
            sys.exit(1)


if __name__ == "__main__":
    main()
