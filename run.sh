#!/bin/bash
# Run metacognition experiment
# Usage: ./run.sh [steps] [trials]
# Default: 5 steps, 3 trials per condition

STEPS=${1:-5}
TRIALS=${2:-3}
OUTDIR="results/steps-${STEPS}"
mkdir -p "$OUTDIR"

# Generate the problem chain
# Each step: take previous answer, apply an operation, get new answer
# We pre-compute the correct answer so we can score automatically

FRAMEWORK=$(cat /Users/junekim/Documents/kimjune01.github.io/_posts/2026/2026-03-13-the-natural-framework.md)

# Build the problem: a chain of arithmetic + logic operations
# Deterministic seed based on step count for reproducibility
python3 -c "
import json, random
random.seed(42 + ${STEPS})

ops = [
    ('add', lambda a,b: a+b),
    ('subtract', lambda a,b: a-b),
    ('multiply', lambda a,b: a*b),
    ('integer divide by', lambda a,b: a//b if b != 0 else a),
    ('modulo', lambda a,b: a%b if b != 0 else 0),
]

value = random.randint(10, 99)
steps = []
for i in range(${STEPS}):
    op_name, op_fn = random.choice(ops)
    operand = random.randint(2, 12)
    # avoid division by zero and keep numbers manageable
    if 'divide' in op_name or 'modulo' in op_name:
        operand = random.randint(2, 7)
    new_value = op_fn(value, operand)
    steps.append({'step': i+1, 'operation': op_name, 'operand': operand, 'result': new_value})
    value = new_value

problem_text = f'Start with {steps[0][\"result\"] - steps[0][\"operand\"] if steps[0][\"operation\"] == \"add\" else \"see below\"}.\n'

# rebuild from initial value
value = random.seed(42 + ${STEPS})
value = random.randint(10, 99)
initial = value
lines = [f'Start with {initial}.']
for s in steps:
    lines.append(f'Step {s[\"step\"]}: {s[\"operation\"]} {s[\"operand\"]}.')

problem = '\n'.join(lines)
problem += '\n\nWhat is the final value? Reply with just the number.'

print(json.dumps({'problem': problem, 'answer': steps[-1]['result'], 'initial': initial, 'steps': steps}))
" > "$OUTDIR/problem.json"

PROBLEM=$(python3 -c "import json; d=json.load(open('$OUTDIR/problem.json')); print(d['problem'])")
ANSWER=$(python3 -c "import json; d=json.load(open('$OUTDIR/problem.json')); print(d['answer'])")

echo "Problem:"
echo "$PROBLEM"
echo ""
echo "Correct answer: $ANSWER"
echo ""

# Condition 1: Bare
echo "=== CONDITION: BARE ==="
for i in $(seq 1 $TRIALS); do
    echo "  Trial $i..."
    RESP=$(codex exec -c model="gpt-5.4" "$PROBLEM" 2>/dev/null)
    echo "$RESP" > "$OUTDIR/bare-${i}.txt"
    echo "  Response: $RESP"
done

# Condition 2: Prompt (metacognitive prompt, no framework)
METACOG_PROMPT="After each step, verify your intermediate answer before proceeding to the next step. If something looks wrong, recompute before continuing.

$PROBLEM"

echo ""
echo "=== CONDITION: PROMPT ==="
for i in $(seq 1 $TRIALS); do
    echo "  Trial $i..."
    RESP=$(codex exec -c model="gpt-5.4" "$METACOG_PROMPT" 2>/dev/null)
    echo "$RESP" > "$OUTDIR/prompt-${i}.txt"
    echo "  Response: $RESP"
done

# Condition 3: Framework (full document + task)
FRAMEWORK_PROMPT="Here is a framework for thinking about multi-step information processing. Use it to guide your approach to the following task.

---
$FRAMEWORK
---

Now solve this task. Apply the framework's principles — especially filter (verify each step) and attend (focus on what matters) — as you work through it.

$PROBLEM"

echo ""
echo "=== CONDITION: FRAMEWORK ==="
for i in $(seq 1 $TRIALS); do
    echo "  Trial $i..."
    RESP=$(codex exec -c model="gpt-5.4" "$FRAMEWORK_PROMPT" 2>/dev/null)
    echo "$RESP" > "$OUTDIR/framework-${i}.txt"
    echo "  Response: $RESP"
done

# Score
echo ""
echo "=== SCORING ==="
echo "Correct answer: $ANSWER"
for cond in bare prompt framework; do
    correct=0
    for i in $(seq 1 $TRIALS); do
        resp=$(cat "$OUTDIR/${cond}-${i}.txt" | grep -oE '[-]?[0-9]+' | tail -1)
        if [ "$resp" = "$ANSWER" ]; then
            correct=$((correct + 1))
        fi
        echo "  $cond trial $i: got '$resp' ($([ "$resp" = "$ANSWER" ] && echo "CORRECT" || echo "WRONG"))"
    done
    echo "  $cond: $correct/$TRIALS correct"
done
