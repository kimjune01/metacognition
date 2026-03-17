"""Round 3 coding problems: incomplete pipeline diagnosis.

Extension of Round 2. Each problem provides a working-but-incomplete system
and failing tests. The model must diagnose what's missing and fix it.
Tests measure behavioral outcomes, not structural properties.
"""

# ---------------------------------------------------------------------------
# Problem 1: Search Index — ingests everything, no quality gating
# ---------------------------------------------------------------------------

INDEX_STARTER_CODE = '''\
import re

def crawl_batch(records):
    """Normalize raw page records into page dicts."""
    pages = []
    for r in records:
        pages.append({
            "id": r["id"],
            "status": r.get("status", "ok"),
            "compilable": r.get("compilable", True),
            "quality_score": r.get("quality_score", 1.0),
            "body": r.get("body", ""),
        })
    return pages

def tokenize(text):
    """Lowercase and split into alphabetic tokens."""
    return [w.lower() for w in re.findall(r"[A-Za-z]+", text)]

def build_index(records):
    """Build an inverted index from page records."""
    pages = crawl_batch(records)
    index = {}
    for page in pages:
        tokens = tokenize(page["body"])
        for tok in set(tokens):
            index.setdefault(tok, []).append(page["id"])
    # sort posting lists for deterministic output
    for tok in index:
        index[tok] = sorted(set(index[tok]))
    return index

def search(index, term):
    """Return sorted document ids containing the term."""
    return index.get(term.lower(), [])
'''

# ---------------------------------------------------------------------------
# Problem 2: Alert Triage — deduplicates but doesn't prioritize or diversify
# ---------------------------------------------------------------------------

ALERT_STARTER_CODE = '''\
def parse_alerts(raw_events):
    """Canonicalize alert dicts."""
    alerts = []
    for e in raw_events:
        alerts.append({
            "id": e["id"],
            "service": e["service"],
            "severity": e["severity"],
            "cluster_key": e["cluster_key"],
            "status": e["status"],
            "timestamp": e["timestamp"],
        })
    return alerts

def drop_resolved(alerts):
    """Remove resolved/closed alerts."""
    return [a for a in alerts if a["status"] == "open"]

def dedupe_exact(alerts):
    """Remove exact duplicate alert ids."""
    seen = set()
    result = []
    for a in alerts:
        if a["id"] not in seen:
            seen.add(a["id"])
            result.append(a)
    return result

def build_review_queue(alerts, limit):
    """Build a review queue from raw alert events."""
    parsed = parse_alerts(alerts)
    filtered = drop_resolved(parsed)
    deduped = dedupe_exact(filtered)
    # Currently just takes the first `limit` survivors
    return deduped[:limit]
'''

# ---------------------------------------------------------------------------
# Problem 3: Batch Reporter — works per-run but forgets across runs
# ---------------------------------------------------------------------------

BATCH_STARTER_CODE = '''\
def parse_rows(lines):
    """Parse CSV-like lines into transaction dicts."""
    rows = []
    for line in lines:
        parts = line.strip().split(",")
        if len(parts) != 3:
            continue
        txn_id, account, amount_str = parts
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        rows.append({"txn_id": txn_id, "account": account, "amount": amount})
    return rows

def valid_rows(rows):
    """Filter out malformed rows and negative amounts."""
    return [r for r in rows if r["amount"] > 0]

def summarize_batch(rows):
    """Compute totals by account for this batch."""
    totals = {}
    for r in rows:
        totals[r["account"]] = totals.get(r["account"], 0) + r["amount"]
    return totals

def render_report(batch_totals, cumulative_totals, batches):
    """Render a report string."""
    lines = []
    # Current batch
    for acct in sorted(batch_totals):
        lines.append(f"current: {acct}={batch_totals[acct]:.0f}")
    # Cumulative
    cum_parts = ", ".join(f"{a}={cumulative_totals[a]:.0f}"
                          for a in sorted(cumulative_totals))
    lines.append(f"cumulative: {cum_parts}")
    # Top account
    if cumulative_totals:
        top = max(cumulative_totals, key=lambda a: cumulative_totals[a])
        lines.append(f"top_account: {top}")
    lines.append(f"batches: {batches}")
    return "\\n".join(lines)

def process_batch(lines, state):
    """Process a batch of transaction lines. Returns (report, updated_state)."""
    rows = parse_rows(lines)
    good = valid_rows(rows)
    batch_totals = summarize_batch(good)
    # BUG: ignores state entirely, returns only current-batch view
    report = render_report(batch_totals, batch_totals, 1)
    return report, state
'''


PROBLEMS_ROUND3 = {
    "index_filter": {
        "name": "build_index",
        "starter_code": INDEX_STARTER_CODE,
        "prompt": (
            "Here is a Python document indexing system. The tests below currently fail. "
            "Fix the code so all tests pass. Return ONLY the complete fixed Python code.\n\n"
            "```python\n" + INDEX_STARTER_CODE + "```\n"
        ),
        "tests": [
            # Valid high-quality page appears in results
            (
                'index = build_index([{"id": "a", "status": "ok", "compilable": True, '
                '"quality_score": 0.91, "body": "Vector search with embeddings"}]); '
                'print(search(index, "vector"))',
                "['a']",
            ),
            # Uncompilable page excluded
            (
                'index = build_index([\n'
                '  {"id": "a", "status": "ok", "compilable": True, "quality_score": 0.91, "body": "Vector search with embeddings"},\n'
                '  {"id": "b", "status": "ok", "compilable": False, "quality_score": 0.99, "body": "Vector search with embeddings"},\n'
                ']); print(search(index, "vector"))',
                "['a']",
            ),
            # Low quality excluded
            (
                'index = build_index([\n'
                '  {"id": "a", "status": "ok", "compilable": True, "quality_score": 0.91, "body": "Ranking algorithm details"},\n'
                '  {"id": "c", "status": "ok", "compilable": True, "quality_score": 0.30, "body": "Ranking algorithm details"},\n'
                ']); print(search(index, "ranking"))',
                "['a']",
            ),
            # Stub page (too few tokens) excluded
            (
                'index = build_index([\n'
                '  {"id": "d", "status": "ok", "compilable": True, "quality_score": 0.95, "body": "hi"},\n'
                ']); print(search(index, "hi"))',
                "[]",
            ),
            # Bad status excluded
            (
                'index = build_index([\n'
                '  {"id": "e", "status": "error", "compilable": True, "quality_score": 0.90, "body": "Important content here now"},\n'
                ']); print(search(index, "important"))',
                "[]",
            ),
            # Duplicate body: only first acceptable page indexed
            (
                'index = build_index([\n'
                '  {"id": "x1", "status": "ok", "compilable": True, "quality_score": 0.80, "body": "DPP reranking improves result diversity in search systems"},\n'
                '  {"id": "x2", "status": "ok", "compilable": True, "quality_score": 0.92, "body": "DPP reranking improves result diversity in search systems"},\n'
                ']); print(search(index, "dpp"))',
                "['x1']",
            ),
            # Mixed: valid + invalid, check only valid appears
            (
                'index = build_index([\n'
                '  {"id": "a", "status": "ok", "compilable": True, "quality_score": 0.91, "body": "Vector search with embeddings and ranking"},\n'
                '  {"id": "b", "status": "ok", "compilable": False, "quality_score": 0.99, "body": "Vector search with embeddings and ranking"},\n'
                '  {"id": "c", "status": "ok", "compilable": True, "quality_score": 0.30, "body": "Vector search with embeddings and ranking"},\n'
                '  {"id": "d", "status": "ok", "compilable": True, "quality_score": 0.95, "body": "hi"},\n'
                ']); r = search(index, "vector"); print(r)',
                "['a']",
            ),
            # Empty input
            (
                'index = build_index([]); print(search(index, "anything"))',
                "[]",
            ),
            # All valid unique pages appear
            (
                'index = build_index([\n'
                '  {"id": "p1", "status": "ok", "compilable": True, "quality_score": 0.70, "body": "Alpha beta gamma delta epsilon"},\n'
                '  {"id": "p2", "status": "ok", "compilable": True, "quality_score": 0.80, "body": "Alpha zeta theta iota kappa"},\n'
                ']); print(search(index, "alpha"))',
                "['p1', 'p2']",
            ),
            # quality_score exactly at threshold (0.60) should pass
            (
                'index = build_index([\n'
                '  {"id": "edge", "status": "ok", "compilable": True, "quality_score": 0.60, "body": "Boundary case test for threshold value"},\n'
                ']); print(search(index, "boundary"))',
                "['edge']",
            ),
        ],
    },
    "alert_attend": {
        "name": "build_review_queue",
        "starter_code": ALERT_STARTER_CODE,
        "prompt": (
            "Here is a Python alert triage system. The tests below currently fail. "
            "Fix the code so all tests pass. Return ONLY the complete fixed Python code.\n\n"
            "```python\n" + ALERT_STARTER_CODE + "```\n"
        ),
        "tests": [
            # Diverse services: not all from one noisy source
            (
                'alerts = [\n'
                '  {"id": "1", "service": "payments", "severity": 9, "cluster_key": "db-latency", "status": "open", "timestamp": 10},\n'
                '  {"id": "2", "service": "payments", "severity": 8, "cluster_key": "db-latency", "status": "open", "timestamp": 11},\n'
                '  {"id": "3", "service": "payments", "severity": 7, "cluster_key": "timeout", "status": "open", "timestamp": 12},\n'
                '  {"id": "4", "service": "auth", "severity": 8, "cluster_key": "token", "status": "open", "timestamp": 13},\n'
                '  {"id": "5", "service": "search", "severity": 8, "cluster_key": "index", "status": "open", "timestamp": 14},\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=3)\n'
                'print([a["id"] for a in queue])',
                "['1', '4', '5']",
            ),
            # Resolved alerts filtered + cluster collapse + diversity
            (
                'alerts = [\n'
                '  {"id": "a", "service": "search", "severity": 5, "cluster_key": "lag", "status": "resolved", "timestamp": 1},\n'
                '  {"id": "b", "service": "search", "severity": 9, "cluster_key": "lag", "status": "open", "timestamp": 2},\n'
                '  {"id": "c", "service": "search", "severity": 8, "cluster_key": "lag", "status": "open", "timestamp": 3},\n'
                '  {"id": "d", "service": "auth", "severity": 7, "cluster_key": "token", "status": "open", "timestamp": 4},\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=2)\n'
                'print([a["id"] for a in queue])',
                "['b', 'd']",
            ),
            # Single alert passes through
            (
                'alerts = [\n'
                '  {"id": "x", "service": "api", "severity": 5, "cluster_key": "slow", "status": "open", "timestamp": 1},\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=3)\n'
                'print([a["id"] for a in queue])',
                "['x']",
            ),
            # All resolved -> empty queue
            (
                'alerts = [\n'
                '  {"id": "r1", "service": "db", "severity": 9, "cluster_key": "crash", "status": "resolved", "timestamp": 1},\n'
                '  {"id": "r2", "service": "db", "severity": 8, "cluster_key": "crash", "status": "resolved", "timestamp": 2},\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=5)\n'
                'print([a["id"] for a in queue])',
                "[]",
            ),
            # Severity ordering within diverse selection
            (
                'alerts = [\n'
                '  {"id": "lo", "service": "web", "severity": 2, "cluster_key": "css", "status": "open", "timestamp": 1},\n'
                '  {"id": "hi", "service": "db", "severity": 10, "cluster_key": "oom", "status": "open", "timestamp": 2},\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=2)\n'
                'print([a["id"] for a in queue])',
                "['hi', 'lo']",
            ),
            # Cluster collapse: same cluster_key, keep highest severity
            (
                'alerts = [\n'
                '  {"id": "c1", "service": "api", "severity": 3, "cluster_key": "timeout", "status": "open", "timestamp": 1},\n'
                '  {"id": "c2", "service": "api", "severity": 7, "cluster_key": "timeout", "status": "open", "timestamp": 2},\n'
                '  {"id": "c3", "service": "api", "severity": 5, "cluster_key": "timeout", "status": "open", "timestamp": 3},\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=3)\n'
                'print([a["id"] for a in queue])',
                "['c2']",
            ),
            # Limit respected
            (
                'alerts = [\n'
                '  {"id": str(i), "service": f"svc{i}", "severity": i, "cluster_key": f"k{i}", "status": "open", "timestamp": i}\n'
                '  for i in range(10)\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=3)\n'
                'print(len(queue))',
                "3",
            ),
            # Diversity wraps: if only one service, fill queue from it
            (
                'alerts = [\n'
                '  {"id": "a1", "service": "mono", "severity": 9, "cluster_key": "k1", "status": "open", "timestamp": 1},\n'
                '  {"id": "a2", "service": "mono", "severity": 8, "cluster_key": "k2", "status": "open", "timestamp": 2},\n'
                '  {"id": "a3", "service": "mono", "severity": 7, "cluster_key": "k3", "status": "open", "timestamp": 3},\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=3)\n'
                'print([a["id"] for a in queue])',
                "['a1', 'a2', 'a3']",
            ),
            # Empty input
            (
                'queue = build_review_queue([], limit=5)\n'
                'print([a["id"] for a in queue])',
                "[]",
            ),
            # Mixed: severity tie broken by timestamp
            (
                'alerts = [\n'
                '  {"id": "t1", "service": "svc", "severity": 5, "cluster_key": "a", "status": "open", "timestamp": 20},\n'
                '  {"id": "t2", "service": "svc", "severity": 5, "cluster_key": "b", "status": "open", "timestamp": 10},\n'
                ']\n'
                'queue = build_review_queue(alerts, limit=2)\n'
                'print([a["id"] for a in queue])',
                "['t2', 't1']",
            ),
        ],
    },
    "batch_remember": {
        "name": "process_batch",
        "starter_code": BATCH_STARTER_CODE,
        "prompt": (
            "Here is a Python batch analytics system. The tests below currently fail. "
            "Fix the code so all tests pass. Return ONLY the complete fixed Python code.\n\n"
            "```python\n" + BATCH_STARTER_CODE + "```\n"
        ),
        "tests": [
            # Basic: state accumulates across two batches
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r1, state = process_batch(["t1,alice,10", "t2,bob,7", "bad,row"], state)\n'
                'r2, state = process_batch(["t2,bob,7", "t3,alice,4"], state)\n'
                'print(state["account_totals"] == {"alice": 14, "bob": 7})',
                "True",
            ),
            # Seen transactions tracked
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r1, state = process_batch(["t1,alice,10", "t2,bob,7"], state)\n'
                'r2, state = process_batch(["t2,bob,7", "t3,alice,4"], state)\n'
                'print(state["seen_txns"] == {"t1", "t2", "t3"})',
                "True",
            ),
            # Batch count increments
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r1, state = process_batch(["t1,alice,10"], state)\n'
                'r2, state = process_batch(["t2,bob,5"], state)\n'
                'print(state["batches"])',
                "2",
            ),
            # Report includes current batch totals
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r1, state = process_batch(["t1,alice,10", "t2,bob,7"], state)\n'
                'r2, state = process_batch(["t3,alice,4"], state)\n'
                'print("current: alice=4" in r2)',
                "True",
            ),
            # Report includes cumulative totals
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r1, state = process_batch(["t1,alice,10", "t2,bob,7"], state)\n'
                'r2, state = process_batch(["t3,alice,4"], state)\n'
                'print("cumulative: alice=14, bob=7" in r2)',
                "True",
            ),
            # Report includes top account
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r1, state = process_batch(["t1,alice,10", "t2,bob,7"], state)\n'
                'r2, state = process_batch(["t3,alice,4"], state)\n'
                'print("top_account: alice" in r2)',
                "True",
            ),
            # Duplicate txn_id within same batch: only count once
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r, state = process_batch(["x1,team,5", "x1,team,5", "x2,team,3"], state)\n'
                'print(state["account_totals"] == {"team": 8})',
                "True",
            ),
            # Empty batch: state unchanged, batch count still increments
            (
                'state = {"account_totals": {"a": 10}, "seen_txns": {"t0"}, "batches": 1}\n'
                'r, state = process_batch([], state)\n'
                'print(state["batches"])',
                "2",
            ),
            # Invalid rows don't affect state
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r, state = process_batch(["bad,row", "also,bad"], state)\n'
                'print(state["account_totals"])',
                "{}",
            ),
            # Three batches accumulate correctly
            (
                'state = {"account_totals": {}, "seen_txns": set(), "batches": 0}\n'
                'r1, state = process_batch(["t1,a,10"], state)\n'
                'r2, state = process_batch(["t2,b,20"], state)\n'
                'r3, state = process_batch(["t3,a,5"], state)\n'
                'print(state["account_totals"] == {"a": 15, "b": 20})',
                "True",
            ),
        ],
    },
}
