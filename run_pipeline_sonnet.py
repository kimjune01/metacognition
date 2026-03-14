#!/usr/bin/env python3
"""Run more Sonnet trials on pipeline problem."""

import os
from harness import run_trial, RESULTS_DIR
from problems import PROBLEMS


def run_arm(difficulty, condition, model, start, count):
    problem = PROBLEMS[difficulty]
    outdir = os.path.join(RESULTS_DIR, difficulty)
    os.makedirs(outdir, exist_ok=True)

    arm = f"{condition}/{model}"
    scores = []
    for t in range(start, start + count):
        r = run_trial(problem, difficulty, condition, model, t, outdir)
        scores.append(r["score"])
        mark = f"{r['passed']}/{r['total']}"
        print(f"  {arm:20s} trial {t}: {mark} ({r['time_s']}s)")

    avg = sum(scores) / len(scores)
    print(f"  {arm:20s} new avg: {avg:.2f}\n")
    return scores


if __name__ == "__main__":
    for cond in ["bare", "prompt", "framework", "filler"]:
        run_arm("pipeline", cond, "sonnet", 4, 5)
