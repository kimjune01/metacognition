#!/usr/bin/env python3
"""Metacognition experiment runner.

Usage:
  python3 experiment.py [--model codex|sonnet] [step_counts...]
  python3 experiment.py 10 15 20           # GPT-5.4 via codex (default)
  python3 experiment.py --model sonnet 10 15 20  # Claude Sonnet
"""

import random
import subprocess
import json
import re
import sys
import os

FRAMEWORK_PATH = "/Users/junekim/Documents/kimjune01.github.io/_posts/2026/2026-03-13-the-natural-framework.md"
TRIALS = 5


def generate_problem(steps: int, seed: int = 42):
    """Generate a multi-step arithmetic problem. Returns (problem_text, answer)."""
    random.seed(seed + steps)
    ops = [
        ("add", lambda a, b: a + b),
        ("subtract", lambda a, b: a - b),
        ("multiply", lambda a, b: a * b),
    ]
    value = random.randint(10, 99)
    lines = [f"Start with {value}."]
    for i in range(steps):
        op_name, op_fn = random.choice(ops)
        if op_name == "multiply":
            operand = random.randint(2, 4)
        else:
            operand = random.randint(3, 15)
        value = op_fn(value, operand)
        lines.append(f"Step {i+1}: {op_name} {operand}.")
    problem = "\n".join(lines)
    problem += "\n\nWhat is the final value? Reply with just the number."
    return problem, value


def run_codex(prompt: str):
    """Run GPT-5.4 via codex exec."""
    result = subprocess.run(
        ["codex", "exec", "-c", 'model="gpt-5.4"', prompt],
        capture_output=True, text=True, timeout=60,
    )
    return result.stdout.strip()


def run_sonnet(prompt: str):
    """Run Claude Sonnet via Anthropic API."""
    import anthropic
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def extract_number(response: str):
    """Extract the last integer from a response."""
    numbers = re.findall(r"-?\d+", response)
    if numbers:
        return int(numbers[-1])
    return None


def run_experiment(steps: int, model: str = "codex", trials: int = TRIALS):
    """Run all three conditions for a given step count."""
    problem, answer = generate_problem(steps)

    with open(FRAMEWORK_PATH) as f:
        framework = f.read()

    prompts = {
        "bare": problem,
        "prompt": (
            "After each step, verify your intermediate answer before proceeding "
            "to the next step. If something looks wrong, recompute before continuing.\n\n"
            + problem
        ),
        "framework": (
            "Here is a framework for thinking about multi-step information processing. "
            "Use it to guide your approach to the following task.\n\n---\n"
            + framework
            + "\n---\n\nNow solve this task. Apply the framework's principles — "
            "especially filter (verify each step) and attend (focus on what matters) — "
            "as you work through it.\n\n"
            + problem
        ),
    }

    run_fn = run_sonnet if model == "sonnet" else run_codex
    outdir = os.path.join("results", model, f"steps-{steps}")
    os.makedirs(outdir, exist_ok=True)

    with open(os.path.join(outdir, "problem.json"), "w") as f:
        json.dump({"problem": problem, "answer": answer, "steps": steps, "model": model}, f, indent=2)

    print(f"\n{'='*60}")
    print(f"MODEL: {model}  |  STEPS: {steps}  |  ANSWER: {answer}")
    print(f"{'='*60}")
    print(f"Problem:\n{problem}\n")

    results = {}
    for condition, prompt_text in prompts.items():
        print(f"--- {condition.upper()} ---")
        correct = 0
        responses = []
        for t in range(1, trials + 1):
            try:
                resp = run_fn(prompt_text)
            except (subprocess.TimeoutExpired, Exception) as e:
                resp = f"ERROR: {e}"
            got = extract_number(resp)
            is_correct = got == answer
            if is_correct:
                correct += 1
            responses.append({"trial": t, "response": resp, "extracted": got, "correct": is_correct})
            mark = "OK" if is_correct else "WRONG"
            print(f"  Trial {t}: {got} ({mark})")

            with open(os.path.join(outdir, f"{condition}-{t}.txt"), "w") as f:
                f.write(resp)

        results[condition] = {"correct": correct, "total": trials, "responses": responses}
        print(f"  Score: {correct}/{trials}")

    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    args = sys.argv[1:]
    model = "codex"
    if "--model" in args:
        idx = args.index("--model")
        model = args[idx + 1]
        args = args[:idx] + args[idx+2:]

    step_counts = [int(x) for x in args] if args else [10]
    all_results = {}
    for steps in step_counts:
        all_results[steps] = run_experiment(steps, model=model)

    print(f"\n{'='*60}")
    print(f"SUMMARY ({model})")
    print(f"{'='*60}")
    for steps, results in all_results.items():
        print(f"\nSteps: {steps}")
        for cond, data in results.items():
            print(f"  {cond:12s}: {data['correct']}/{data['total']}")
