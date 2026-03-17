#!/usr/bin/env python3
"""Round 3 experiment harness: domain-matched pipeline tasks.

Extension of Round 2. Tests whether the Natural Framework helps on tasks
whose structure matches the framework (X -> X transformations) rather than
tasks where it was shown to hurt (search problems).

Uses the same 4 conditions, same 2 models, same scoring as Round 2.
"""

import sys
import os

# Reuse the Round 2 harness infrastructure
from harness import (
    load_framework,
    make_filler,
    run_model,
    extract_code,
    run_tests,
    run_trial,
    FRAMEWORK_PATH,
)
from problems_round3 import PROBLEMS_ROUND3

RESULTS_DIR = "results/round3"


def build_prompts_round3(problem):
    """Build all 4 condition prompts for a Round 3 problem."""
    framework = load_framework()

    task = (
        f"Write a Python function that solves this problem.\n\n"
        f"{problem['prompt']}\n"
        f"Return ONLY the function code, no explanation, no tests, "
        f"no markdown fences. Just the Python function."
    )

    metacog = (
        "Before writing code, think through your approach:\n"
        "1. What transformation passes are needed?\n"
        "2. How do the passes interact — can one pass create work for another?\n"
        "3. What is the fixed-point condition — when do you stop?\n"
        "4. After writing, mentally trace through the examples to verify.\n\n"
    )

    framework_prefix = (
        "Here is a framework for thinking about multi-step information processing. "
        "Use it to guide your approach — especially filter (verify each step) "
        "and attend (focus on what matters).\n\n---\n"
        + framework
        + "\n---\n\n"
    )

    filler_prefix = (
        "Here is some background context.\n\n---\n"
        + make_filler(len(framework))
        + "\n---\n\n"
    )

    return {
        "bare": task,
        "prompt": metacog + task,
        "framework": framework_prefix + task,
        "filler": filler_prefix + task,
    }


def run_round3_trial(problem_key, condition, model, trial_num, outdir):
    """Run a single Round 3 trial. Returns result dict."""
    import json
    import time

    problem = PROBLEMS_ROUND3[problem_key]
    prompts = build_prompts_round3(problem)
    prompt_text = prompts[condition]

    start = time.time()
    try:
        response = run_model(prompt_text, model)
    except Exception as e:
        response = f"ERROR: {e}"
    elapsed = time.time() - start

    code = extract_code(response)
    passed, total, test_details = run_tests(code, problem["tests"])

    result = {
        "condition": condition,
        "model": model,
        "problem": problem_key,
        "trial": trial_num,
        "passed": passed,
        "total": total,
        "score": passed / total if total > 0 else 0,
        "time_s": round(elapsed, 1),
        "prompt_len": len(prompt_text),
        "response_len": len(response),
        "tests": test_details,
    }

    # Save
    trial_file = os.path.join(outdir, f"{condition}-{model}-{trial_num}.json")
    with open(trial_file, "w") as f:
        json.dump(result, f, indent=2)

    code_file = os.path.join(outdir, f"{condition}-{model}-{trial_num}.py")
    with open(code_file, "w") as f:
        f.write(code)

    return result


def run_round3(problem_key="regex_simplifier", trials=8):
    """Run Round 3: all 4 conditions x 2 models x N trials for one problem."""
    import json

    problem = PROBLEMS_ROUND3[problem_key]
    outdir = os.path.join(RESULTS_DIR, problem_key)
    os.makedirs(outdir, exist_ok=True)

    conditions = ["bare", "prompt", "framework", "filler"]
    models = ["codex", "sonnet"]

    print(f"\n{'='*70}")
    print(f"ROUND 3: {problem_key} ({problem['name']}), {trials} trials per arm")
    print(f"{'='*70}\n")

    all_results = []
    for condition in conditions:
        for model in models:
            arm = f"{condition}/{model}"
            scores = []
            for t in range(1, trials + 1):
                r = run_round3_trial(problem_key, condition, model, t, outdir)
                scores.append(r["score"])
                mark = f"{r['passed']}/{r['total']}"
                print(f"  {arm:20s} trial {t}: {mark} ({r['time_s']}s)")
                all_results.append(r)
            avg = sum(scores) / len(scores)
            print(f"  {arm:20s} avg: {avg:.2f}")
            print()

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Arm':20s} {'Avg Score':>10s} {'Prompt Len':>12s}")
    print("-" * 44)
    for condition in conditions:
        for model in models:
            arm_results = [r for r in all_results
                          if r["condition"] == condition and r["model"] == model]
            avg = sum(r["score"] for r in arm_results) / len(arm_results)
            plen = arm_results[0]["prompt_len"]
            print(f"  {condition}/{model:6s}      {avg:>8.2f}   {plen:>10d}")

    # Save aggregate
    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(all_results, f, indent=2)

    return all_results


if __name__ == "__main__":
    problem = sys.argv[1] if len(sys.argv) > 1 else "regex_simplifier"
    trials = int(sys.argv[2]) if len(sys.argv) > 2 else 8

    if problem == "all":
        for p in PROBLEMS_ROUND3:
            run_round3(p, trials)
    else:
        run_round3(problem, trials)
