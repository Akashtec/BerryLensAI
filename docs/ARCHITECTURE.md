# BerryLens AI Architecture

For the project philosophy and long-term AI engineering vision, see `docs/BERRYLENS_SOUL.md`. For the AI-specific layer map, see `docs/AI_ARCHITECTURE.md`.

## Pipeline

BerryLens uses one orchestration path in `verification_service.py`:

1. **Claim Analysis:** validate and normalize the submitted claim and generate bounded search queries.
2. **Research Planning:** represent the queries and configured result budget in `ResearchPlan`.
3. **Evidence Retrieval:** query Tavily and normalize results into typed evidence objects.
4. **Evidence Quality Assessment:** normalize domains, assign transparent tier priors, deduplicate URLs/passages, and classify each passage as `SUPPORTS`, `REFUTES`, `NEUTRAL`, or `UNCLEAR`.
5. **Synthesis:** use the Mistral synthesis boundary through Hugging Face to summarize retrieved material. Its output is not the final authority.
6. **Verdict Generation:** `verdict_engine.py` combines validated stance, relevance, stance confidence, credibility prior, and evidence volume. Sparse evidence returns `INSUFFICIENT_EVIDENCE`; balanced conflicting evidence returns `PARTIALLY_SUPPORTED`.
7. **Explanation:** `VerificationReport` carries the summary, reasoning note, evidence groups, uncertainties, queries, status, timing, and source count.

The verdict engine is deterministic for the same assessments and configuration. Confidence is a bounded decision score, not a calibrated probability claim.

## Contracts

`models/schemas.py` is the canonical contract module. It defines `ClaimAnalysis`, `ResearchPlan`, `Source`, `RawEvidence`, `EvidenceAssessment`, `SynthesisResult`, `VerificationReport`, verdict states, stance states, and research status.

Provider failures return safe `INSUFFICIENT_EVIDENCE`/`FAILED` reports or source-level `UNCLEAR` assessments. They do not manufacture evidence or expose internal exception text through the API.

## Storage

SQLite stores structured verification reports as JSON in the `verifications` table and retains the legacy claim/verdict/evidence tables for the existing dashboard. Chroma stores only supplementary historical memory with retrieval timestamps, schema version, and research status. Expired memory is ignored, and failed/cached reports are not stored as fresh evidence.

## API and Frontend

The versioned API is:

- `POST /api/verify`
- `POST /api/v1/verify`
- `POST /api/v1/verify/stream`
- `GET /api/reports/<id>`
- `GET /api/v1/result/<id>`
- `GET /api/v1/history`
- `GET /api/v1/stats`
- `GET /api/docs`
- `GET /health`
- `GET /metrics`

`/check` remains a compatibility alias. Input is validated with Pydantic, request size is bounded, optional API-key authentication and in-memory rate limiting are configurable, and security headers are added to responses. Frontend model/retrieved text is inserted with text-safe DOM APIs.

The claim form consumes `/api/v1/verify/stream`, whose events are emitted by actual service boundaries (`queries_generated`, `evidence_retrieved`, `evidence_assessed`, `synthesis_complete`, `verdict_computed`, and `completed`). It falls back to the normal JSON endpoint if streaming is unavailable.

`/metrics` exposes a small Prometheus-compatible text surface for request and error counters. Docker Compose includes Prometheus and Grafana services; dashboard provisioning remains deployment-specific.

## Deliberate Non-Goals

The system does not add microservices, Kafka, a second search provider, or a factuality classifier to the runtime path. The optional `train_prior_classifier.py` utility is isolated from verification. User authentication and PostgreSQL are not yet wired; the current release uses local SQLite and optional API-key protection, and must not be deployed as a multi-user authenticated service until those boundaries are implemented.
