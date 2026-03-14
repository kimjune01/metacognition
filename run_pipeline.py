#!/usr/bin/env python3
"""Run pipeline (endofunctor) experiment."""

import json
import os
from harness import run_trial, RESULTS_DIR
from problems import PROBLEMS


def run_arm(difficulty, condition, model, num_trials):
    problem = PROBLEMS[difficulty]
    outdir = os.path.join(RESULTS_DIR, difficulty)
    os.makedirs(outdir, exist_ok=True)

    arm = f"{condition}/{model}"
    scores = []
    for t in range(1, num_trials + 1):
        r = run_trial(problem, difficulty, condition, model, t, outdir)
        scores.append(r["score"])
        mark = f"{r['passed']}/{r['total']}"
        print(f"  {arm:20s} trial {t}: {mark} ({r['time_s']}s)")

    avg = sum(scores) / len(scores)
    print(f"  {arm:20s} avg: {avg:.2f}\n")
    return scores


if __name__ == "__main__":
    conditions = ["bare", "prompt", "framework", "filler"]

    print("=== CODEX (8 trials) ===")
    for cond in conditions:
        run_arm("pipeline", cond, "codex", 8)

    print("=== SONNET (3 trials) ===")
    for cond in conditions:
        run_arm("pipeline", cond, "sonnet", 3)
