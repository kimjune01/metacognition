You are evaluating a diagnostic report for a Python system.

Here is what the system actually does:
{working_capabilities}

Here are the ground-truth gaps — things a production version needs but this code doesn't have:
{gap_list}

Below is a diagnostic report. Score it on three dimensions:

1. OBSERVATION ACCURACY: Does the Observations section correctly describe the system's working capabilities?
   Score: accurate / mostly_accurate / inaccurate

2. GAP COVERAGE: For each ground-truth gap, does the Triage section identify this gap in substance (even if it uses different words)?
   Return: {"gap_1": true/false, "gap_2": true/false, ...}

3. PLAN SPECIFICITY: For each gap the report DID identify, is the Plan section concrete enough to act on?
   Return: {"gap_1": "concrete" / "directional" / "absent", ...}

{diagnostic_report}
