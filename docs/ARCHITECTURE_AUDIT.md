# BerryLens AI Architecture Audit

**Audit date:** 2026-09-09  
**Scope:** Current repository before architectural changes  
**Runtime verified:** Python 3.12.10, project virtual environment, Flask development server

Provider references in this historical audit describe the pre-Mistral state. The runtime now uses Mistral through the Hugging Face Inference API.

## Executive Summary

BerryLens is a small Flask application with two entry points. The active browser path performs claim embedding lookup, Mistral query generation, Tavily retrieval, Mistral evidence synthesis, SQLite persistence, and Chroma persistence. The path works for a basic claim when it is launched with the project virtual environment. The global interpreter does not have the project dependencies and fails before startup.

The architecture is salvageable. The useful core is the existing provider split, Pydantic evidence models, SQLite history, Chroma semantic memory, and simple Flask UI. The next work should harden this path and establish a single structured verification contract before adding more agents or infrastructure.

## Repository Inventory

| Area | Current implementation | Decision |
| --- | --- | --- |
| Web entry point | `app.py`, Flask routes and browser API | KEEP, then REFACTOR |
| CLI entry point | `main.py`, interactive duplicate pipeline | KEEP temporarily, then REFACTOR to shared service |
| Claim analysis | `agents/claim_agent.py`, one Mistral call | KEEP responsibility, FIX validation and limits |
| Web research | `agents/research_agent.py`, Tavily search | KEEP provider, FIX normalization, status, timeout, and deduplication |
| Verdict analysis | `agents/analyst_agent.py`, one Mistral call | KEEP responsibility, FIX strict schema and uncertainty handling |
| Domain models | `models/evidence.py` | REFACTOR into a broader verification contract |
| Relational storage | `db_manager.py/db_manager.py`, SQLite | KEEP for current scale, FIX paths, transactions, and status handling |
| Semantic memory | `rag_memory.py`, Chroma plus Sentence Transformers | KEEP only as historical retrieval, FIX metadata and freshness semantics |
| Frontend | `templates/*.html` and inline JavaScript | KEEP visual shell, FIX API contract and XSS risks |
| Nested templates | `templates/templates/...` and deeper copies | REMOVE after confirming no active route uses them |
| Dependencies | Existing `venv`, no manifest | ADD a pinned dependency manifest and setup documentation |
| Tests | No project tests found | ADD unit, integration, failure, and evaluation tests |
| Documentation | No project README or docs found | ADD README, architecture, and evaluation documentation |

## Actual Execution Paths

### Web startup

1. `app.py` loads `.env` and imports all three agents.
2. Agent imports construct Mistral and Tavily clients at module import time and may raise if keys are missing.
3. `app.py` dynamically imports `db_manager.py/db_manager.py` because the database module is inside a directory with the same name.
4. SQLite tables are initialized.
5. `BerryLensMemory()` creates a Chroma persistent client and a Sentence Transformer embedding function. This can download/load a model before the server accepts requests.
6. Flask starts on port 5000 in debug mode.

### Browser verification path

The active form in `templates/index.html` sends JSON to `POST /check`.

```text
claim text
  -> BerryLensMemory.search()
  -> agents.claim_agent.extract_search_queries()
  -> agents.research_agent.fetch_evidence()
  -> agents.analyst_agent.analyze_evidence()
  -> SQLite save_claim/save_verdict/save_evidence
  -> Chroma BerryLensMemory.store()
  -> JSON response rendered by browser JavaScript
```

On a cache hit, Chroma results are returned immediately and the fresh research path is skipped. There is no freshness or time-sensitivity check on this shortcut.

### Legacy browser path

`POST /verify` handles empty input but has no return for valid input, so a valid submission reaches a Flask 500. The old SQLite pipeline below the successful return in `/check` is unreachable. Its failure update logic therefore does not protect the active path. The nested legacy template tree is not used by the active `GET /` route.

### CLI path

`main.py` repeats the claim, research, analysis, and Chroma flow interactively. It prints results and stores only Chroma memory; it does not create SQLite investigations, claims, verdicts, or evidence. This makes CLI and web behavior diverge.

## Current Architecture Against Target Principles

### What already aligns

- External evidence is retrieved before the final Mistral synthesis call.
- Claim query generation, retrieval, and analysis are separate modules.
- Evidence and verdict objects use Pydantic validation.
- SQLite stores claim, verdict, and source records.
- The UI exposes a result explanation, confidence, and basic source data.
- Chroma is used for prior-check retrieval rather than as the only source of truth.

### Important gaps

- Evidence items do not carry publication time, domain, source type, content hash, stance, quality, or investigation identity.
- Sources are not evaluated for independence, entity match, syndication, or direct support of the proposition.
- The analyst receives a flat text block and controls the verdict and numeric confidence without a documented scoring basis.
- Public verdict literals are `SUPPORTED`, `REFUTED`, `INSUFFICIENT EVIDENCE`, and `MISLEADING`, while the requested public contract is `TRUE`, `FALSE`, or `UNCERTAIN`.
- Compound claims are not decomposed into atomic propositions.
- Research failure is printed and hidden as an empty/partial evidence set rather than represented as a structured status.
- Chroma cache results can silently replace fresh research, including for time-sensitive claims.
- No investigation ID, research trace, latency, call counts, or structured logs are recorded.

## Risk Register

Severity uses `CRITICAL`, `HIGH`, `MEDIUM`, and `LOW`. Each item includes the proposed action category.

### CRITICAL

| Problem | Evidence | Action |
| --- | --- | --- |
| Secrets are present in the workspace `.env` and the Flask app has a predictable fallback secret | `.env`, `app.py` | **FIX:** rotate exposed provider keys, keep `.env` local, require a strong production secret, and never log values |
| The project has no reproducible dependency manifest | No `requirements.txt` or `pyproject.toml`; global `python app.py` fails on `dotenv` | **ADD:** pinned runtime/dev dependencies and documented venv startup |

### HIGH

| Problem | Evidence | Action |
| --- | --- | --- |
| `POST /check` is unauthenticated and can trigger repeated Mistral/Tavily calls | `app.py` route has no auth, rate limit, request size, timeout, or per-run budget | **FIX:** enforce input limits, provider budgets/timeouts, rate limiting, and production access controls |
| User, retrieved, and model content is inserted with `innerHTML` | `templates/index.html` and `templates/dashboard.html` build HTML from response data | **FIX:** use text-safe DOM construction or escaping and add security headers/CSP |
| Valid `POST /verify` is broken and the active failure handler is unreachable | `app.py` | **REMOVE/REFACTOR:** route all submissions through one tested service and delete dead legacy code |
| Provider clients and embedding model initialize at import/startup | agent modules and `BerryLensMemory` | **REFACTOR:** lazy initialization, explicit health checks, and actionable startup errors |
| The quota fallback returns `UNVERIFIABLE`, which violates the Pydantic verdict literal | `agents/analyst_agent.py` versus `models/evidence.py` | **FIX:** normalize provider failures to structured `UNCERTAIN`/failure status |
| Errors are returned to clients as raw `str(error)` | `app.py` `/check` exception handler | **FIX:** return stable public error envelopes and log internal details without secrets |
| SQLite and Chroma persistence are not coordinated | SQLite is written before Chroma; later failures return 500 and leave partial state | **REFACTOR:** persist investigation state transactionally and make Chroma best-effort/repairable |

### MEDIUM

| Problem | Evidence | Action |
| --- | --- | --- |
| Relative storage paths depend on the process working directory | `DB_PATH = "berrylens.db"`, `./chroma_db` | **FIX:** resolve paths from application configuration |
| SQLite connections lack explicit foreign keys, busy timeout, and clear transaction boundaries | `db_manager.py/db_manager.py` | **FIX:** configure connection pragmas and context-managed transactions |
| Search exceptions are swallowed and partial research is not represented | `fetch_evidence()` catches all exceptions and prints | **FIX:** return `ResearchStatus` and per-query errors |
| LLM JSON is manually parsed with weak normalization | `json.loads(response.text)` and unrestricted model response | **REFACTOR:** use strict structured output/schema validation and normalize casing/ranges |
| Duplicate or syndicated sources are only removed by exact URL | `seen_urls` in `research_agent.py` | **ADD:** canonical URL, title/text similarity, and source-independence metadata |
| RAG metadata lacks investigation/source freshness fields | `rag_memory.py` stores only claim and a few strings | **REFACTOR:** distinguish historical context from current verification evidence |
| Confidence is an uncalibrated LLM integer | `VerificationResult.confidence` and analyst prompt | **REFACTOR:** compute a documented confidence band/score from evidence quality and conflict |
| CLI and web pipelines do not share a service or persistence behavior | `main.py` duplicates orchestration | **REFACTOR:** make both call the same verification service |

### LOW

| Problem | Evidence | Action |
| --- | --- | --- |
| Debug server is enabled by default | `app.py` | **FIX:** use configuration and document production WSGI deployment |
| Stale checked-in virtual environment metadata points to another project path | `venv/pyvenv.cfg` | **REMOVE/ADD:** do not rely on the checked-in venv; document recreation |
| Large generated artifacts and caches are mixed with source | `venv`, `__pycache__`, `__pycache__.zip`, Chroma/SQLite data | **REMOVE:** add ignore rules and keep only intentional fixtures/data |
| No structured observability or evaluation dataset exists | no tests, scripts, or evaluation files | **ADD:** investigation metrics, logs, 20-claim evaluation, and failure records |

## Five Highest-Impact Problems

1. **Secrets and configuration hygiene:** provider credentials are present locally, the Flask fallback secret is predictable, and there is no setup manifest. Rotate keys and make configuration explicit before deployment.
2. **Unbounded public provider spend:** `/check` can invoke multiple paid/external calls without authentication, rate limiting, request limits, timeouts, or budgets.
3. **Unsafe output rendering:** model and retrieved content reaches `innerHTML`, creating an XSS path through both fresh and persisted data.
4. **Two competing pipelines:** `/verify`, unreachable legacy code, nested templates, and `main.py` duplicate or bypass the active pipeline, causing inconsistent behavior and unreliable failure states.
5. **Unstructured and uncalibrated verification:** evidence lacks stance/quality/independence/freshness metadata, the LLM controls the numeric confidence, and provider failures can violate the verdict schema.

## Recommended Target Architecture

Keep Flask and the current providers for this stage. Introduce a small service boundary rather than more agents:

```text
Frontend
  -> versioned verification API
  -> VerificationService
       -> Claim/Query models and deterministic validation
      -> ResearchService (Mistral planning + Tavily retrieval)
       -> EvidenceNormalizer/Deduplicator
       -> EvidenceEvaluator (deterministic metadata plus one structured LLM judgment where needed)
       -> VerdictService (strict TRUE/FALSE/UNCERTAIN contract)
       -> SQLite investigation persistence
       -> optional historical Chroma retrieval, never authoritative over fresh evidence
```

The public response should contain the claim, `verification_id`, `verdict`, confidence band or documented score, summary, supporting/refuting/neutral evidence, uncertainties, research status, and trace metadata. It must not expose chain-of-thought.

Recommended configurable limits:

```text
MAX_CLAIM_LENGTH
MAX_QUERIES_PER_CLAIM
MAX_RESULTS_PER_QUERY
MAX_RESEARCH_ROUNDS
PROVIDER_TIMEOUT_SECONDS
```

## Implementation Plan

### Phase 1: Reliability and safety

1. Rotate any exposed Hugging Face and Tavily credentials outside the codebase.
2. Add `.gitignore`, dependency manifest, `.env.example`, and setup instructions.
3. Centralize configuration and resolve database/vector paths from the project directory.
4. Remove the broken/dead `/verify` path or delegate it to the shared service.
5. Replace unsafe `innerHTML` rendering and add security headers.
6. Add bounded input, provider timeout/budget handling, generic API errors, and structured logs.

### Phase 2: Contract and evidence quality

1. Add `Claim`, `SearchQuery`, `ResearchResult`, `EvidenceAssessment`, and `VerificationReport` schemas.
2. Normalize verdicts to public `TRUE`, `FALSE`, and `UNCERTAIN`.
3. Represent partial/failed research explicitly.
4. Add URL normalization, source metadata, content hashes, duplicate detection, stance, and uncertainty fields.
5. Validate Mistral structured output and convert quota/JSON failures into `UNCERTAIN` with a useful status.

### Phase 3: Persistence, RAG, and observability

1. Record investigation IDs, queries, counts, latency, model, errors, and status.
2. Make SQLite the authoritative investigation record and Chroma historical retrieval explicitly non-authoritative.
3. Add freshness metadata and bypass/discount stale cache hits for time-sensitive claims.
4. Add repairable persistence behavior when Chroma is unavailable.

### Phase 4: Tests and evaluation

1. Add deterministic unit tests for schemas, URLs, deduplication, stance, ranking, and confidence.
2. Add Flask/API tests with mocked Mistral, Tavily, SQLite, and Chroma boundaries.
3. Add failure tests for timeout, 429, malformed output, empty results, contradictions, and insufficient evidence.
4. Add a 20-claim evaluation dataset and record accuracy, precision/recall/F1 where applicable, uncertain rate, abstention quality, calibration, latency, call counts, and failures.

## Verification Baseline

The current application was exercised with the claim `The Earth is round.` using the project venv. It returned `SUPPORTED` with `95%` confidence and stored a new Chroma/SQLite result. This proves the happy path is operational, but it does not establish calibration, source independence, resilience, security, or repeated-claim quality.

The global interpreter failed before startup with `ModuleNotFoundError: No module named 'dotenv'`. The documented run command must therefore explicitly use the project environment until dependency setup is made reproducible.

## Open Decisions for Implementation

- Whether the first public API release should preserve `/check` for compatibility while adding `/api/v1/verify`.
- Whether confidence should initially be a qualitative `LOW/MEDIUM/HIGH` band or a documented numeric score with no statistical-calibration claim.
- Whether Chroma remains enabled by default in environments where downloading the embedding model at startup is undesirable.
- Whether the local application needs authentication immediately or whether an authenticated deployment boundary will be required before production use.

## Implementation Progress

The first foundation slice has now been implemented:

- `config.py` centralizes project-root environment loading and configurable research limits.
- `models/schemas.py` defines validated claim, source, evidence assessment, research status, request, and report contracts.
- `verdict_engine.py` computes a deterministic public `TRUE`/`FALSE`/`UNCERTAIN` verdict from assessed evidence and applies a documented thin-evidence penalty.
- `verification_service.py` is the shared orchestration boundary for the web path and CLI.
- `db_manager.py/db_manager.py` now includes a backward-compatible full-report JSON store, and the web path writes each validated report to it while retaining legacy dashboard rows.
- `POST /api/v1/verify` is available, while `/check` remains a compatibility alias.
- The browser now consumes the versioned contract and renders model output with `textContent` rather than `innerHTML`.
- `main.py` uses the shared service instead of maintaining a second orchestration pipeline.
- Deterministic verdict tests were added under `tests/`.

This is intentionally a compatibility step, not the finished evidence architecture. The current service adapts the existing whole-claim Mistral synthesis into transitional evidence stances; source-level NLI, source-quality scoring, syndication detection, rate limiting, structured persistence, and the 20-claim evaluation remain follow-up phases.

The implementation has since added typed research plans, source-tier priors, URL and passage deduplication, independent per-source stance assessment, freshness-filtered Chroma retrieval, canonical versioned read endpoints, configurable API-key/rate controls, safe dashboard rendering, and structured failure reports. NLI-backed assessment and a measured evaluation dataset remain intentionally pending; no accuracy result is claimed.