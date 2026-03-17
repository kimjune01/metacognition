# Information System Diagnostic Checklist

Six stages every information system needs. Five run forward in order. The sixth runs backward.

## Forward stages

### 1. Perceive
**What it does:** Intake raw input from the environment. The boundary between outside and inside.
**Missing if:** The system has no ingestion step, or can't read its own inputs.
**Ask:** Where does data enter? Is anything lost at the boundary?

### 2. Cache
**What it does:** Normalize, index, and store input for later retrieval. A data structure that holds items before they're processed.
**Missing if:** Raw data is not transformed into a queryable form. Items can't be looked up or compared.
**Ask:** Can the system retrieve what it ingested? Is input indexed or just appended?

### 3. Filter
**What it does:** Reject bad input. Rule-based, no judgment. A threshold, a WHERE clause, a linter. Winners pass, losers are suppressed.
**Missing if:** The system accepts everything. No quality gate, no deduplication, no validation.
**Ask:** What gets rejected? If the answer is "nothing," filter is missing.

### 4. Attend
**What it does:** Rank and select from what survived filtering. This is where judgment enters. Finite output means choosing what matters most.
**Missing if:** The system returns everything that passed the filter, with no prioritization or diversity enforcement.
**Ask:** How does the system decide what comes first? Does it prevent redundant results?

### 5. Remember
**What it does:** Persist results across runs. The interface to durable storage.
**Missing if:** State resets between invocations. Previous results are lost.
**Ask:** Does the system know what happened last time? Can it accumulate over time?

## Backward stage

### 6. Consolidate
**What it does:** Read from stored results and update how the system processes next time. The backward pass. Learning.
**Missing if:** The system processes the same way every time regardless of past results. No adaptation.
**Ask:** Does the system get better over time? Does it update its own rules or parameters?

## How to use

Read the source code. For each stage, answer: present, absent, or shallow? An absent stage means the system lacks that capability entirely. A shallow stage means it exists but doesn't meet the need (e.g., a filter that only checks format but not quality). The first absent or shallow stage is usually the highest-priority fix.
