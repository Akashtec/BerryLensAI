# Verification Policy

BerryLens verdicts are evidence-based decisions, not raw LLM opinions.

## Inputs

The verdict engine should consume structured evidence:

- source metadata
- evidence passage
- relation to claim
- relevance score
- source quality score
- contradiction/support strength
- retrieval timestamp
- publication date where available

## Public Verdicts

### SUPPORTED

Use when credible, relevant, preferably independent evidence substantially supports the claim and significant contradiction is absent.

### REFUTED

Use when credible, relevant evidence substantially contradicts the claim.

### PARTIALLY_SUPPORTED

Use when meaningful parts of the claim are supported but other parts are wrong, exaggerated, missing context, ambiguous, or contradicted.

### INSUFFICIENT_EVIDENCE

Use when the system cannot defensibly choose a stronger verdict because evidence is missing, weak, stale, irrelevant, inaccessible, or too contradictory.

## Confidence / Evidence Score

The score is not a calibrated probability. It is a bounded evidence score based on:

- evidence quality
- number of usable sources
- agreement versus contradiction
- relevance to the exact claim
- source independence
- recency where appropriate

Do not describe the score as statistical certainty unless calibration experiments are added.

## Evidence Rules

- Do not fabricate sources.
- Do not cite sources that were not retrieved.
- Do not let the LLM create the final verdict directly.
- Do not count duplicate or syndicated copies as independent evidence.
- Do not hide contradicting evidence.
- Prefer `INSUFFICIENT_EVIDENCE` when evidence is too weak.

## Current Implementation

Implemented:

- deterministic verdict aggregation in `verdict_engine.py`
- evidence and source schemas in `models/schemas.py`
- source grouping into supporting/refuting/neutral evidence
- sentence-level stance heuristic with term normalization, explicit refutation cues, and special-case caveat handling in `agents/analyst_agent.py`
- safe fallback to `INSUFFICIENT_EVIDENCE` on empty evidence

Known limitation:

- current stance classification is tested and more conservative than a raw keyword match, but it is still a heuristic. NLI or another evaluated classifier is required before claiming high verification quality.
