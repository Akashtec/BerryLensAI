# Failure Modes

This file names the ways BerryLens can fail so tests and logs can target real risks.

## Retrieval Failure

Search provider timeout, quota exhaustion, bad API key, no results, or network failure.

Expected behavior: continue safely, record failure, return `INSUFFICIENT_EVIDENCE` if no usable evidence remains.

## Source Failure

A URL is blocked, malformed, redirects unexpectedly, returns non-HTML, or has unreadable content.

Expected behavior: skip or mark source as failed without crashing the investigation.

## Extraction Failure

The system retrieves a page but cannot extract clean text.

Expected behavior: preserve source metadata, mark extraction failure, avoid citing missing text.

## Relevance Failure

Retrieved evidence is about similar words but not the actual claim.

Expected behavior: classify as neutral/low relevance and avoid using it as decisive evidence.

## Stance Failure

Evidence is classified as support/refutation incorrectly.

Expected behavior: improve with deterministic fixtures, NLI/LLM comparison, and human-reviewed benchmark examples.

## LLM Failure

The model times out, returns malformed JSON, refuses, hallucinates, or produces uncited statements.

Expected behavior: validate output, retry only within limits, fall back safely, never expose secret/internal errors.

## Citation Failure

The report mentions a source or factual point not present in retrieved evidence.

Expected behavior: block or downgrade the generated report; require traceable source references.

## Temporal Failure

The claim depends on time, but old evidence is treated as current.

Expected behavior: track claim date, publication date, retrieval date, and verification date.

## Contradiction Failure

The system finds supporting evidence but misses strong contradiction.

Expected behavior: actively seek contradictory evidence and show both sides.

## Infrastructure Failure

Database, Chroma, Docker, CI, or deployment fails.

Expected behavior: expose `/health`, log operational details without secrets, and keep the API failure envelope stable.

## Security Failure

Prompt injection, malicious URLs, oversized input, debug stack traces, leaked secrets, or unauthenticated public usage.

Expected behavior: validate input/tool/output boundaries, keep secrets out of logs/docs, and protect public deployments.
