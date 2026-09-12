# BerryLensAI File Classification

Last classified: 2026-09-12

## KEEP

- `app.py`: Current working Flask app and API boundary.
- `main.py`: Current CLI entrypoint over the shared verification service.
- `verification_service.py`: Current central orchestration spine.
- `verdict_engine.py`: Deterministic verdict aggregation; needs schema alignment but is useful.
- `evidence_quality.py`: Useful normalization, source tiering, and deduplication helpers.
- `rag_memory.py`: Useful optional Chroma historical memory with lazy initialization from the web app.
- `models/schemas.py`: Canonical Pydantic response and pipeline contracts.
- `models/evidence.py`: Legacy evidence/result contract used by DB and retrieval adapters.
- `agents/claim_agent.py`: Query generation with deterministic fallback.
- `agents/research_agent.py`: Tavily retrieval adapter with deduplication.
- `agents/analyst_agent.py`: Current evidence assessment and synthesis fallback.
- `db_manager.py/db_manager.py`: Active SQLite persistence adapter, despite unusual path.
- `config.py`: Runtime settings boundary.
- `config/source_tiers.json`: Source credibility prior configuration.
- `templates/base.html`: Shared UI layout.
- `templates/index.html`: Working claim entry and streaming result UI.
- `templates/result.html`: Stored report display.
- `templates/history.html`: Report history page.
- `templates/dashboard.html`: Dashboard page.
- `tests/test_verdict_engine.py`: Useful unit tests for verdict logic.
- `tests/test_failure_contracts.py`: Useful failure-safety and orchestration tests.
- `tests/test_evidence_quality.py`: Useful normalization and dedup tests.
- `tests/test_api_routes.py`: Useful API, stream, and auth tests.
- `requirements.txt`: Runtime dependency source, currently installable in the project venv.
- `.env.example`: Placeholder configuration template with no real secrets.
- `.gitignore`: Protects local secrets, caches, DBs, and editor files.
- `README.md`: Useful current setup and architecture summary.
- `docs/BERRYLENS_SOUL.md`: Product promise, engineering principles, and honest status vocabulary.
- `docs/AI_ARCHITECTURE.md`: Current/planned AI layer map.
- `docs/AI_ENGINEERING_GUIDE.md`: Beginner AI guide grounded in BerryLens code.
- `docs/AI_MODEL_COMPARISON.md`: Comparison of classical ML, transformers, NLI, RAG, and LLM roles.
- `docs/VERIFICATION_POLICY.md`: Public verdict semantics and evidence-score rules.
- `docs/DATA_QUALITY.md`: Runtime/evaluation/training data boundaries and quality checks.
- `docs/FAILURE_MODES.md`: Failure categories for future tests and observability.
- `docs/ARCHITECTURE.md`: Useful current architecture doc.
- `docs/DEPLOYMENT.md`: Useful deployment doc.
- `.github/workflows/ci.yml`: Useful CI test and Docker build workflow.
- `Dockerfile`: Useful production-oriented container build.
- `docker-compose.yml`: Useful local orchestration for app plus metrics stack. `docker compose config` validates, but expands `.env` secrets in output.
- `gunicorn.conf.py`: Useful WSGI config.
- `Procfile`: Useful Heroku-style deployment entry.
- `prometheus.yml`: Useful metrics scrape config.
- `Makefile`: Useful command shortcuts.
- `.pre-commit-config.yaml`: Useful local quality hooks.
- `runtime.txt`: Useful Heroku-style Python version pin.
- `CHANGELOG.md`: Useful release history context.

## REPAIR

- `app.py`: Direct `app.py` startup runs Flask debug mode.
- `agents/analyst_agent.py`: Local stance heuristic is safe but too weak for nuanced support/refutation.
- `README.md`: Setup is mostly useful but must be updated after dependency and route repairs.

## REPAIRED

- `requirements-dev.txt`: Removed invalid literal `+` prefixes and declared `pytest`.
- `models/schemas.py`: Public verdict names now match the mission target classes and normalize legacy stored values.
- `app.py`: Added mission-compatible `POST /api/verify` and `GET /api/reports/<id>` aliases.
- `verification_service.py`: Updated status policy to use target verdict language.
- `templates/index.html`: Displays target verdict values directly instead of mapping old labels to `REAL`/`FAKE`.

## REFACTOR

- `db_manager.py/db_manager.py`: Active and functional, but the folder named `db_manager.py` is confusing and forces dynamic import in `app.py`.
- `models/evidence.py`: Legacy schema overlaps with `models/schemas.py`; consolidate only after tests protect the DB and retrieval boundaries.
- `templates/result.html`: Functional, but should clearly separate evidence, source metadata, and AI-generated explanation.
- `train_prior_classifier.py`: Isolated optional utility; keep out of runtime, document as future/evaluation work.

## REPLACE

- None proven yet. No module should be replaced until equivalent behavior is verified.

## DEPRECATE

- Root `chroma_db/`: Appears to be older local Chroma runtime data. Runtime default is `data/chroma_db`. Do not delete until checked against any user workflow.
- Root `berrylens.db`: Appears to be older local SQLite runtime data. Runtime default is `data/berrylens.db`. Do not delete until checked.
- Legacy tables in SQLite (`claims`, `verdicts`, `evidence`): Still used by `persist_report`, so they cannot be removed yet. Mark for future migration after report persistence is consolidated.
- `/check`: Compatibility alias; keep until API consumers are known.
- Committed or staged zip archives: likely backup/release artifacts, not runtime source. Do not remove until the user confirms their purpose.

## DELETE

- None. The prior nested `templates/templates/...` files were already deleted before this audit and captured in the safety checkpoint.

## UNKNOWN

- `.zip`
- `BerryLensAI.zip`
- `BerryLensAI-source.zip`
- `BerryLensAI-full.zip`
- `New folder/`
- `.vscode/settings.json`
- `.pytest_cache/`
- `__pycache__/`
- `__pycache__.zip`

These are local artifacts or editor/cache files. Do not delete them without confirming whether they are user backups or generated output.
