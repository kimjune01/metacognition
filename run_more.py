#!/usr/bin/env python3
"""Run additional trials on specific arms for Bayesian update."""

import json
import os
import sys
from harness import run_trial, RESULTS_DIR
from problems import PROBLEMS


def run_arm(difficulty, condition, model, start_trial, num_trials):
    problem = PROBLEMS[difficulty]
    outdir = os.path.join(RESULTS_DIR, difficulty)
    os.makedirs(outdir, exist_ok=True)

    arm = f"{condition}/{model}"
    scores = []
    for t in range(start_trial, start_trial + num_trials):
        r = run_trial(problem, difficulty, condition, model, t, outdir)
        scores.append(r["score"])
        mark = f"{r['passed']}/{r['total']}"
        print(f"  {arm:20s} trial {t}: {mark} ({r['time_s']}s)")

    avg = sum(scores) / len(scores)
    print(f"  {arm:20s} new avg: {avg:.2f}")
    return scores


if __name__ == "__main__":
    # Run 5 more codex trials on frontier for bare, prompt, framework, filler
    difficulty = "frontier"
    for condition in ["bare", "prompt", "framework", "filler"]:
        print(f"\n=== {condition}/codex ===")
        run_arm(difficulty, condition, "codex", 4, 5)
