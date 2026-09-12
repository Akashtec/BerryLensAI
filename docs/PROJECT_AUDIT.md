# BerryLensAI Project Audit

Last audited: 2026-09-12

## Recovery Point

- Repository root: `C:\Users\Akash\BerryLensAI`
- Git branch: `main`
- Remote tracking: `origin/main`
- Safety checkpoint created before recovery edits: `c793f38 chore: safety checkpoint before recovery`
- Current untracked artifacts observed: `.zip`, `BerryLensAI.zip`, `BerryLensAI-source.zip`, `BerryLensAI-full.zip`
- Secret handling: `.env` exists locally and was not printed or copied. `.env.example` contains placeholders only.

## Environment

- OS shell: Windows PowerShell 5.1
- Project virtual environment: `venv`
- Project Python: `venv\Scripts\python.exe` reports Python 3.12.10
- Global `python`: Python 3.12.10
- `py`: Python 3.14.7
- Global `pip`: bound to Python 3.14, so project commands should use `venv\Scripts\python.exe -m pip`
- Node.js: v24.19.0
- npm: 11.17.0
- Docker: 29.7.2
- Docker Compose: v5.5.1

## Repository Structure

- `app.py`: Flask web app, API routes, session auth, rate limiting, metrics, and persistence wiring.
- `main.py`: CLI entrypoint using the shared `VerificationService`.
- `verification_service.py`: core orchestration path for claim validation, query generation, retrieval, evidence assessment, synthesis, verdict computation, and persistence.
- `agents/`: provider and pipeline stage adapters.
- `models/`: Pydantic contracts for API and pipeline data.
- `db_manager.py/db_manager.py`: SQLite persistence implementation. The directory name is unusual but currently used by dynamic import in `app.py`.
- `evidence_quality.py`: URL normalization, domain tiering, credibility priors, duplicate filtering.
- `verdict_engine.py`: deterministic verdict aggregation from assessed evidence.
- `rag_memory.py`: optional Chroma historical memory.
- `templates/`: Flask UI templates.
- `tests/`: unit/API/failure behavior tests.
- `docs/`: existing architecture and deployment docs.
- `docs/BERRYLENS_SOUL.md`: product promise, engineering principles, and north star.
- `docs/AI_ARCHITECTURE.md`: implemented/partial/optional/planned AI layer map.
- `docs/AI_ENGINEERING_GUIDE.md`: beginner-friendly AI guide grounded in this codebase.
- `docs/AI_MODEL_COMPARISON.md`: comparison of classical ML, transformers, NLI, RAG, and LLM roles.
- `docs/VERIFICATION_POLICY.md`: public verdict and evidence-score policy.
- `docs/DATA_QUALITY.md`: data categories and quality checks.
- `docs/FAILURE_MODES.md`: failure taxonomy for future tests and observability.
- `.github/workflows/ci.yml`: GitHub Actions tests and Docker build job.
- `Dockerfile`, `docker-compose.yml`, `gunicorn.conf.py`, `Procfile`: deployment surfaces.
- `data/` and `chroma_db/`: local SQLite and Chroma runtime state. These are ignored local data, not source of truth.

## Runtime Entrypoints

- Web app: `venv\Scripts\python.exe app.py`
- WSGI production app: `gunicorn --config gunicorn.conf.py app:app`
- Docker app: `docker compose up app`
- CLI: `venv\Scripts\python.exe main.py`
- Offline utility: `train_prior_classifier.py`

No FastAPI entrypoint is present. The current API boundary is Flask.

## Current API Surface

- `GET /health`
- `GET /metrics`
- `GET /api/docs`
- `POST /api/verify`
- `POST /api/v1/verify`
- `POST /api/v1/verify/stream`
- `POST /check`
- `GET /api/reports/<id>` requires login
- `GET /api/v1/result/<id>` requires login
- `GET /api/v1/history` requires login
- `GET /api/v1/stats` requires login
- Browser pages: `/`, `/history`, `/dashboard`, `/claim/<id>`
- Auth helpers: `/register`, `/login`, `/logout`, `/profile`

Mission-requested endpoints `POST /api/verify` and `GET /api/reports/{id}` are now present as aliases over the existing Flask handlers.

## Dependency Graph

Direct runtime dependencies in `requirements.txt`:

- Flask
- chromadb
- huggingface-hub
- gunicorn
- pydantic
- python-dotenv
- sentence-transformers
- tavily-python
- torch CPU wheel
- tenacity

Direct dev dependencies intended in `requirements-dev.txt`:

- black
- flake8
- pre-commit
- pytest via installed environment, but not declared in `requirements-dev.txt`

Resolved dependency issue:

- `requirements-dev.txt` previously contained literal leading `+` characters before `black`, `flake8`, and `pre-commit`; this has been repaired and `pytest` is now declared for development/test setup.

Installed project environment:

- `pip check` reports no broken requirements.
- Extra installed packages exist beyond `requirements.txt`, including Google/GenAI libraries, uvicorn, watchfiles, pytest, and others. The app should not rely on those accidental extras.

## AI Architecture

- LLM provider: Hugging Face Inference API using `mistralai/Mistral-7B-Instruct-v0.3` by default.
- Query generation: `agents/claim_agent.py`; deterministic fallback is always available.
- Retrieval: `agents/research_agent.py`; Tavily search when `TAVILY_API_KEY` is configured.
- Evidence stance: `agents/analyst_agent.py`; sentence-level local heuristic with term normalization, explicit refutation cues, and caveat handling. It is tested, but still not a configured NLI or structured LLM boundary.
- Synthesis: `agents/analyst_agent.py`; currently returns conservative insufficient-evidence summaries unless structured generation is later wired.
- Verdict: `verdict_engine.py`; deterministic aggregation from `EvidenceAssessment`.
- Vector memory: `rag_memory.py`; Chroma stores historical completed reports and is lazily initialized by the web app.

Current public verdict classes:

- `SUPPORTED`
- `REFUTED`
- `PARTIALLY_SUPPORTED`
- `INSUFFICIENT_EVIDENCE`

Legacy stored report values such as `TRUE`, `FALSE`, `MIXED`, and `UNCERTAIN` are normalized when reports are loaded.

## Persistence

- SQLite report database path defaults to `data/berrylens.db`.
- Legacy tables: `claims`, `verdicts`, `evidence`, `source_trust`.
- Current report table: `verifications`, storing canonical report JSON.
- Users table exists for simple session authentication.
- Chroma data exists in both `data/chroma_db/` and root `chroma_db/`; runtime default now points at `data/chroma_db`.

## Infrastructure

- Dockerfile uses `python:3.12-slim`, non-root `appuser`, health check, Gunicorn, and CPU Torch handling.
- Compose runs `app`, `prometheus`, and `grafana`.
- `docker compose config` succeeds locally. Its output expands `.env` values, so do not paste it into public logs, tickets, or documentation.
- Prometheus config exists.
- CI installs runtime requirements, runs tests, and builds Docker on pushes to main/tags.
- No CD pipeline is present.

## Testing

- Existing tests:
  - `tests/test_analyst_agent.py`
  - `tests/test_verdict_engine.py`
  - `tests/test_failure_contracts.py`
  - `tests/test_evidence_quality.py`
  - `tests/test_api_routes.py`
- Current result after first repairs: `24 passed in 1.57s`.
- Tests cover deterministic stance heuristics, verdict behavior, provider failure safety, API validation/streaming, auth scoping, URL normalization, and deduplication.
- Missing test areas: deterministic integration fixtures for live retrieval abstraction, CLI smoke, database isolation per test, Docker build test in local audit, and regression/evaluation dataset.

## Security Observations

- `.env` is ignored and was not printed.
- Optional `BERRYLENS_API_KEY` protects verification endpoints when configured.
- `MAX_CONTENT_LENGTH` limits request body size.
- Basic in-memory rate limiting applies to `/check`, `/api/v1/verify`, and `/api/v1/verify/stream`.
- Security headers are set after requests.
- Passwords are hashed using Werkzeug helpers.
- CORS is not broadly enabled.
- Risks to address:
  - Flask dev server uses `debug=True` when `app.py` is executed directly.
  - Retrieved web content is summarized heuristically now, but future LLM prompts must explicitly treat retrieved content as untrusted data.
  - Auth exists but is minimal and not production-grade.
  - `api_result`, `api_v1_history`, and `api_v1_stats` require login, but mission wants public report retrieval behavior to be decided.

## Executed Verification

Commands run:

- `git status --short --branch`
- `git log --oneline -5`
- `.\venv\Scripts\python.exe -m pytest -q tests`
- `.\venv\Scripts\python.exe -m pip check`
- `docker compose config`
- `.\venv\Scripts\python.exe app.py`
- `Invoke-RestMethod http://127.0.0.1:5000/health`
- `Invoke-RestMethod http://127.0.0.1:5000/api/docs`
- `Invoke-RestMethod http://127.0.0.1:5000/metrics`
- `Invoke-RestMethod -Method Post http://127.0.0.1:5000/api/v1/verify`

Results:

- Tests pass.
- `pip check` passes.
- `docker compose config` validates the Compose model.
- Flask app starts on `127.0.0.1:5000`.
- `/health` returns HTTP 200.
- `/api/docs` returns HTTP 200.
- `/metrics` returns HTTP 200 with Prometheus-compatible text.
- `/api/v1/verify` returns a structured report for a live sample claim.
- `/api/verify` is covered by an automated route test.
- Post-change `/api/docs` advertises `/api/verify` and `/api/reports/{id}`.

## Current Highest-Impact Issues

1. Evaluate NLI or structured model-based evidence classification against deterministic fixtures, because the current stance layer is still heuristic.
2. Add deterministic smoke/integration fixtures that do not require live Tavily or Hugging Face.
3. Decide whether authenticated report retrieval should remain required for `GET /api/reports/{id}`.
