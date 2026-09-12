# BerryLens Soul

BerryLens is an evidence-first AI system for checking claims. Its purpose is not to sound confident. Its purpose is to slow down, gather sources, compare evidence, show uncertainty, and explain what can and cannot be defended.

## One Sentence

BerryLens researches claims across multiple sources, extracts supporting and contradicting evidence, applies a transparent verification policy, and returns a traceable verdict with citations.

## Core Belief

Truth is not a vibe from a model. A BerryLens verdict must come from evidence that the system can point to.

The system should prefer:

- `INSUFFICIENT_EVIDENCE` over invented certainty
- cited evidence over unsupported explanation
- simple reliable components over impressive but fragile architecture
- measured improvement over technology checklists
- fresh evidence over stale memory for time-sensitive claims

## Product Promise

When a user enters a claim, BerryLens should answer:

- What exactly is being claimed?
- What sources were checked?
- Which evidence supports the claim?
- Which evidence contradicts it?
- How strong and independent is that evidence?
- What verdict follows from the evidence?
- What remains uncertain?

## Verdicts

BerryLens uses four public verdicts:

- `SUPPORTED`: credible evidence substantially supports the claim and no significant contradiction was found.
- `REFUTED`: credible evidence substantially contradicts the claim.
- `PARTIALLY_SUPPORTED`: important parts are supported, but other parts are wrong, exaggerated, incomplete, or contradicted.
- `INSUFFICIENT_EVIDENCE`: available evidence is too weak, sparse, stale, ambiguous, or unavailable to support a stronger verdict.

## Engineering Principles

- Preserve working code before replacing it.
- Keep one authoritative verification path.
- Separate search, retrieval, extraction, evidence analysis, verdict policy, and reporting.
- Treat web pages as untrusted data, never as instructions.
- Use typed schemas for machine-to-machine boundaries.
- Keep provider integrations replaceable.
- Test default behavior without live external APIs.
- Label work honestly as implemented, optional, experimental, or planned.
- Do not add Spark, Redis, agents, or deep learning unless each has a real role.

## AI Principles

BerryLens is a hybrid AI engineering system:

- NLP helps understand claims.
- Search retrieves current external evidence.
- Embeddings and Chroma support historical memory and semantic lookup.
- LLMs can help plan, classify, and summarize, but they do not own the final verdict.
- NLI and classical ML are candidates for evidence classification and benchmarking.
- Deterministic policy turns structured evidence into a verdict.

## Current Truth

Implemented today:

- Flask web/API app
- claim verification service
- Tavily web retrieval
- Hugging Face/Mistral query expansion when enabled
- deterministic fallback behavior
- Chroma historical memory
- SQLite persistence
- dashboards/history routes
- Docker/Compose files
- tests for contracts, routes, failure handling, and verdict policy

Still maturing:

- claim decomposition
- robust NLP/entity/date extraction
- page content extraction beyond Tavily snippets
- stronger evidence stance classification
- NLI evaluation
- deterministic benchmark dataset
- production authentication and deployment hardening
- full Docker verification on a running Docker daemon
- MLOps/model registry
- Spark batch data pipeline

## North Star

BerryLens should become a system a beginner can understand and a serious engineer can respect.

The repository should answer:

- what the system does
- how the AI works
- where the data comes from
- where NLP, ML, embeddings, RAG, LLMs, and agents fit
- how evidence is extracted and scored
- how hallucinations are reduced
- how the API, database, Docker, CI, and deployment work
- what is implemented now and what is planned next

This is the soul of BerryLens: honest evidence, careful engineering, visible uncertainty, and no architecture theatre.
