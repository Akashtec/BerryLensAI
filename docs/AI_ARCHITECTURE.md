# AI Architecture

This document explains the intended BerryLens AI system and marks what is implemented today versus planned.

## Status Legend

- `IMPLEMENTED`: code exists, is connected, documented, and tested or smoke-verified.
- `PARTIAL`: code exists but needs stronger tests, quality, or integration.
- `OPTIONAL`: available but not required for the main verification path.
- `PLANNED`: not implemented yet.

## Online Verification Flow

```text
User claim
  -> Flask API / UI
  -> VerificationService
  -> claim validation and query planning
  -> Tavily search
  -> evidence normalization and deduplication
  -> evidence stance assessment
  -> deterministic verdict engine
  -> SQLite persistence
  -> optional Chroma historical memory
  -> JSON report and dashboard display
```

## AI Layer Map

| Layer | Status | Current role | Code |
| --- | --- | --- | --- |
| Claim validation | IMPLEMENTED | Normalize and validate incoming claim length/content shape | `models/schemas.py` |
| Claim analysis | PARTIAL | Basic claim type defaults and search-query planning | `models/schemas.py`, `agents/claim_agent.py` |
| NLP | PARTIAL | Sentence-level token normalization, relevance scoring, caveat detection, and stance heuristics | `agents/analyst_agent.py` |
| Classical ML | OPTIONAL | Offline prior-classifier training script only | `train_prior_classifier.py` |
| Deep learning | PARTIAL | Sentence-transformer embeddings through Chroma; optional Hugging Face model calls | `rag_memory.py`, `agents/claim_agent.py` |
| Transformers | PARTIAL | Mistral via Hugging Face for optional query expansion; sentence-transformer embeddings | `agents/claim_agent.py`, `rag_memory.py` |
| Embeddings | IMPLEMENTED | Historical semantic memory lookup/store | `rag_memory.py` |
| Vector database | IMPLEMENTED | Chroma persistent collection for previous fact-check memory | `rag_memory.py` |
| RAG memory | PARTIAL | Similar prior investigation memory; not authoritative evidence | `rag_memory.py`, `app.py` |
| LLM | PARTIAL | Optional query generation; structured analyst generation is not configured yet | `agents/claim_agent.py`, `agents/analyst_agent.py` |
| Agents | PARTIAL | Logical modules exist as simple stage adapters, not autonomous agents | `agents/` |
| Tools | PARTIAL | Search, memory, persistence, and verdict tools are code boundaries, not a formal tool registry | `agents/`, `db_manager.py/`, `verdict_engine.py` |
| Guardrails | PARTIAL | Input validation, request-size limit, rate limit, schema validation, safe failure reports | `app.py`, `models/schemas.py`, `verification_service.py` |
| Evaluation | PLANNED | Need deterministic benchmark dataset and metrics | future `evaluation/` |
| MLOps | PLANNED | Need model registry, prompt versions, evaluation reports | future docs/artifacts |
| Spark/data engineering | PLANNED | Batch ingestion only when workload justifies it | future `spark/` |

## Fresh Evidence vs Historical RAG

Fresh evidence is the evidence retrieved for the current claim during the current investigation. Historical RAG memory is previous BerryLens output stored in Chroma.

Policy:

- Fresh evidence dominates for current or time-sensitive claims.
- Historical memory may provide context or detect repeated claims.
- Historical memory must not silently replace fresh evidence.
- Failed or cached reports should not be stored as fresh evidence.
- Stale memory should be ignored or clearly labeled.

## Deterministic vs Model-Based Components

Deterministic or rule-based:

- request validation
- URL/domain normalization
- source tier priors
- duplicate filtering
- sentence-level relevance and stance heuristics
- verdict aggregation
- API error envelopes

Model-based or probabilistic:

- optional Mistral query generation
- sentence-transformer embeddings
- future NLI/evidence classification
- future structured evidence synthesis

External:

- Tavily search
- Hugging Face inference

Local:

- Flask app
- SQLite
- Chroma storage
- deterministic verdict engine

## Target AI Shape

The desired mature system is:

```text
Claim
  -> NLP claim analysis
  -> atomic subclaims
  -> research planner
  -> search and source retrieval
  -> content extraction
  -> evidence extraction
  -> NLI / evidence classifier
  -> LLM evidence synthesis
  -> deterministic verification policy
  -> final report with citations
```

Each added layer must improve measurable quality, reliability, traceability, or maintainability.
