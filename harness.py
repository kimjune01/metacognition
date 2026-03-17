#!/usr/bin/env python3
"""Round 2 experiment harness: coding tasks with test suites."""

import subprocess
import json
import re
import sys
import os
import time
import textwrap

FRAMEWORK_PATH = "/Users/junekim/Documents/june.kim/_posts/2026/2026-03-13-the-natural-framework.md"
RESULTS_DIR = "results/round2"

from problems import PROBLEMS


def load_framework():
    with open(FRAMEWORK_PATH) as f:
        return f.read()


def make_filler(target_len):
    """Generate length-matched filler text (Wikipedia-style, non-metacognitive)."""
    # Use a boring, non-instructional passage roughly matching framework length
    base = textwrap.dedent("""\
    The history of cartography traces the development of maps and mapping
    from ancient times to the present. Maps have been one of the most
    important human inventions for millennia, allowing for the
    communication of spatial information. The earliest known maps date
    back to ancient Babylon around 2300 BC. These early maps were carved
    on clay tablets and showed local features such as hills, valleys, and
    canals. The ancient Greeks made significant contributions to
    cartography. Anaximander is credited with creating one of the first
    maps of the known world around 610 BC. Eratosthenes calculated the
    circumference of the Earth with remarkable accuracy. Ptolemy's
    Geographia, written around 150 AD, included instructions for creating
    maps using a coordinate system of latitude and longitude.

    During the medieval period in Europe, maps were often influenced by
    religious beliefs. T-O maps placed Jerusalem at the center of the
    world. Islamic cartographers, however, continued the Greek tradition
    of scientific mapmaking. Al-Idrisi created one of the most advanced
    medieval world maps in 1154. The Age of Exploration brought dramatic
    advances in cartography as European explorers charted new territories.
    Mercator's projection, introduced in 1569, became the standard for
    nautical navigation. Modern cartography has been transformed by
    satellite imagery, GIS systems, and digital mapping technologies.
    Today, maps are generated dynamically from vast databases and can be
    customized for any purpose. The transition from paper to digital has
    fundamentally changed how humans interact with spatial information.
    """)
    # Repeat until we match target length
    filler = base
    while len(filler) < target_len:
        filler += "\n" + base
    return filler[:target_len]


def build_prompts(problem, difficulty):
    """Build all 4 condition prompts for a problem."""
    framework = load_framework()

    task = (
        f"Write a Python function that solves this problem.\n\n"
        f"{problem['prompt']}\n"
        f"Return ONLY the function code, no explanation, no tests, "
        f"no markdown fences. Just the Python function."
    )

    metacog = (
        "Before writing code, think through your approach:\n"
        "1. What is the core algorithm needed?\n"
        "2. What edge cases could fail?\n"
        "3. After writing, mentally trace through the examples to verify.\n\n"
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


def run_model(prompt, model):
    """Run a model and return the response."""
    if model == "codex":
        result = subprocess.run(
            ["codex", "exec", "-c", 'model="gpt-5.4"', prompt],
            capture_output=True, text=True, timeout=120,
        )
        return result.stdout.strip()
    elif model == "sonnet":
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    else:
        raise ValueError(f"Unknown model: {model}")


def extract_code(response):
    """Extract Python function from model response."""
    # Try to find code in markdown fences first
    fence_match = re.search(r'```(?:python)?\s*\n(.*?)```', response, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # If response starts with def, take as-is
    if response.strip().startswith("def "):
        return response.strip()

    # Try to find a def block
    def_match = re.search(r'(def \w+\(.*?\).*)', response, re.DOTALL)
    if def_match:
        return def_match.group(1).strip()

    return response.strip()


def run_tests(code, tests):
    """Execute code and run tests. Returns (passed, total, details)."""
    passed = 0
    details = []
    for expr, expected in tests:
        # If the test expression already contains print(), run it directly
        if "print(" in expr:
            test_code = f"{code}\n\n{expr}"
        else:
            test_code = f"{code}\n\nresult = {expr}\nprint(repr(result))"
        try:
            result = subprocess.run(
                ["python3", "-c", test_code],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                err = result.stderr.strip()
                details.append({"expr": expr, "expected": expected, "actual": f"ERROR: {err}", "pass": False})
                continue

            actual = result.stdout.strip()
            # For multi-line output (assertion tests), take last line
            if "\n" in actual:
                actual = actual.strip().split("\n")[-1]

            # Compare values
            try:
                actual_val = eval(actual)
                expected_val = eval(expected)
                if isinstance(expected_val, float):
                    ok = abs(actual_val - expected_val) < 1e-6
                else:
                    ok = actual_val == expected_val
            except Exception:
                ok = actual == expected

            if ok:
                passed += 1
                details.append({"expr": expr, "expected": expected, "actual": actual, "pass": True})
            else:
                err = result.stderr.strip() if result.stderr else None
                details.append({"expr": expr, "expected": expected, "actual": actual, "error": err, "pass": False})
        except subprocess.TimeoutExpired:
            details.append({"expr": expr, "expected": expected, "actual": "TIMEOUT", "pass": False})
        except Exception as e:
            details.append({"expr": expr, "expected": expected, "actual": str(e), "pass": False})

    return passed, len(tests), details


def run_trial(problem, difficulty, condition, model, trial_num, outdir):
    """Run a single trial. Returns result dict."""
    prompts = build_prompts(problem, difficulty)
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
        "difficulty": difficulty,
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


def run_pilot(difficulty="medium", trials=3):
    """Run pilot: all 4 conditions × 2 models × N trials."""
    problem = PROBLEMS[difficulty]
    outdir = os.path.join(RESULTS_DIR, difficulty)
    os.makedirs(outdir, exist_ok=True)

    conditions = ["bare", "prompt", "framework", "filler"]
    models = ["codex", "sonnet"]

    print(f"\n{'='*70}")
    print(f"PILOT: {difficulty} ({problem['name']}), {trials} trials per arm")
    print(f"{'='*70}\n")

    all_results = []
    for condition in conditions:
        for model in models:
            arm = f"{condition}/{model}"
            scores = []
            for t in range(1, trials + 1):
                r = run_trial(problem, difficulty, condition, model, t, outdir)
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
    with open(os.path.join(outdir, "pilot_results.json"), "w") as f:
        json.dump(all_results, f, indent=2)

    return all_results


if __name__ == "__main__":
    difficulty = sys.argv[1] if len(sys.argv) > 1 else "medium"
    trials = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    run_pilot(difficulty, trials)
