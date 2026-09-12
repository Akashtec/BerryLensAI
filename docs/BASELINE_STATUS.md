# BerryLensAI Baseline Status

Last checked: 2026-09-12

## Current Startup Command

Development server:

```powershell
.\venv\Scripts\python.exe app.py
```

Production-style WSGI command:

```powershell
.\venv\Scripts\python.exe -m gunicorn --config gunicorn.conf.py app:app
```

Note: Gunicorn is not a native Windows production server; use the Docker/Linux path for production parity.

## Required Environment

- Use the project venv at `venv`.
- Python target is 3.12.10.
- Use `.\venv\Scripts\python.exe -m pip`, because global `pip` points at Python 3.14.
- `.env` may define:
  - `HUGGINGFACE_API_KEY`
  - `HUGGINGFACE_MODEL`
  - `TAVILY_API_KEY`
  - `FLASK_SECRET_KEY`
  - `BERRYLENS_API_KEY`
  - `BERRYLENS_DB_PATH`
  - `BERRYLENS_CHROMA_PATH`
  - rate and retrieval limits

No real secret values were inspected or printed.

## Successful Execution Path

Verified path:

```text
POST /api/verify or POST /api/v1/verify
  -> VerifyRequest validation
  -> extract_search_queries
  -> fetch_evidence
  -> assess_evidence_stance
  -> analyze_evidence
  -> VerdictEngine.compute
  -> VerificationReport JSON response
  -> SQLite report persistence
  -> optional Chroma memory write
```

Observed smoke result:

- `GET /health`: HTTP 200
- `GET /api/docs`: HTTP 200 and advertises the versioned API.
- `GET /metrics`: HTTP 200 with Prometheus-compatible text.
- `POST /api/v1/verify` with `Water freezes at 0 degrees Celsius at standard pressure.`: HTTP 200 with structured `VerificationReport`.
- Current sample verdict from live retrieval was `INSUFFICIENT_EVIDENCE` with `PARTIAL` research status because the local stance heuristic found mostly neutral evidence and one weak refuting passage.
- `POST /api/verify` is now present as an alias and covered by tests.
- Post-change `GET /api/docs` advertises `/api/verify` and `/api/reports/{id}`.

## Tests Run

```powershell
.\venv\Scripts\python.exe -m pytest -q tests
```

Result:

```text
24 passed in 1.57s
```

Dependency check:

```powershell
.\venv\Scripts\python.exe -m pip check
```

Result:

```text
No broken requirements found.
```

## Known Failures

None currently reproduced after the first repair.

## Resolved Failures

- The current app imports successfully.
- The Flask dev server starts.
- `/health` is reachable over HTTP.
- The test suite passes.
- `pip check` reports no broken requirements.
- `requirements-dev.txt` dry run now succeeds.
- Public verdict classes now match the mission target contract.
- Mission alias `POST /api/verify` now works.
- Mission alias `GET /api/reports/<id>` now exists and currently follows the same login requirement as `/api/v1/result/<id>`.
- Prior nested duplicate template paths are already removed in the safety checkpoint.

Resolved development dependency install failure:

```powershell
.\venv\Scripts\python.exe -m pip install --dry-run -r requirements-dev.txt
```

Previously failed with:

```text
ERROR: Invalid requirement: '+black==25.1.0'
```

Cause: `requirements-dev.txt` contained literal `+` prefixes.

## Remaining Failures And Gaps

- Evidence stance classification is now a sentence-level heuristic with caveat handling, but still needs NLI or structured model evaluation before high-confidence production claims.
- Live retrieval depends on Tavily; deterministic integration fixtures are still needed.
- `docker compose config` validates the Compose file, but its raw output expands `.env` values and must not be pasted into public logs or docs.
- Docker build was inspected but not yet executed in this recovery pass.
- CI exists but has not been run remotely in this recovery pass.
