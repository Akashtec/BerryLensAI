# BerryLens AI

BerryLens is an evidence-grounded claim verification application. It retrieves web evidence, assesses source-level stance, computes a deterministic verdict, and exposes uncertainty when evidence is weak or unavailable.

## Project Soul

BerryLens is being built as a real AI engineering system, not a demo that simply asks an LLM whether something is true.

Start here:

- [BerryLens Soul](docs/BERRYLENS_SOUL.md)
- [AI Architecture](docs/AI_ARCHITECTURE.md)
- [AI Engineering Guide](docs/AI_ENGINEERING_GUIDE.md)
- [AI Model Comparison](docs/AI_MODEL_COMPARISON.md)
- [Verification Policy](docs/VERIFICATION_POLICY.md)
- [Data Quality](docs/DATA_QUALITY.md)
- [Failure Modes](docs/FAILURE_MODES.md)

The guiding rule is simple: a technology is implemented only when it has code, purpose, documentation, tests, and verification. Otherwise it is marked as partial, optional, or planned.

## Local Setup

Requires Python 3.12 or newer.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `HUGGINGFACE_API_KEY`, `TAVILY_API_KEY`, and `FLASK_SECRET_KEY` in `.env`. BerryLens uses Mistral through the Hugging Face Inference API for query generation, evidence assessment, and synthesis. Keep `.env` local and rotate keys if they have been exposed. `BERRYLENS_API_KEY` is optional for local development; when set, API requests require `X-API-Key`.

Start the application with the project interpreter:

```powershell
.\venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000`.

## API

`POST /api/verify` or `POST /api/v1/verify`

```json
{"claim": "Water freezes at 0 degrees Celsius at standard pressure."}
```

The response is a `VerificationReport` containing `SUPPORTED`, `REFUTED`, `PARTIALLY_SUPPORTED`, or `INSUFFICIENT_EVIDENCE`, a numeric evidence score in `[0, 1]`, evidence groups, research status, queries, source count, and timing metadata.

Other endpoints:

- `GET /api/reports/<id>` and `GET /api/v1/result/<id>`
- `GET /api/v1/history?limit=20&offset=0`
- `GET /api/v1/stats`
- `POST /check` remains as a compatibility alias
- `POST /api/v1/verify/stream` emits Server-Sent Events for real pipeline stages
- `GET /api/docs` returns the OpenAPI discovery document
- `GET /health` and `GET /metrics` support deployment checks and scraping

OpenAPI discovery JSON is available at `/api/docs` when the app is running. A Swagger UI dependency is intentionally not included yet.

## Testing

```powershell
.\venv\Scripts\python.exe -m pytest -q tests
```

Tests cover schema contracts, verdict selection, URL and passage deduplication, API validation, persistence behavior, and provider failure handling.

## Architecture

The request path is:

```text
Browser -> Flask API -> VerificationService
        -> Claim/query generation
        -> Tavily retrieval and deterministic normalization/deduplication
        -> source-level stance assessment
        -> deterministic evidence-based verdict engine
        -> SQLite report persistence and optional Chroma historical memory
        -> safe structured response
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md), and [docs/ARCHITECTURE_AUDIT.md](docs/ARCHITECTURE_AUDIT.md).

## Deployment

Docker and Gunicorn files are included. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and run `docker compose up --build` for the app plus optional Prometheus/Grafana services.

The current release provides optional API-key protection rather than account authentication. SQLite is the supported database backend; PostgreSQL and per-user history require a future migration before multi-user production deployment.

## Important Limitations

The current source-level assessment uses a Mistral classification boundary and transparent source priors; it is not a calibrated scientific probability. Chroma is historical supplementary memory and is freshness-filtered; it must never replace current evidence for time-sensitive claims. NLI and auxiliary factuality classifiers remain optional future components.

## GitHub Setup

```powershell
git init
git add .
git commit -m "Migrate BerryLensAI to Mistral via Hugging Face"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repository>.git
git push -u origin main
```

Never commit `.env` or API keys. Create the GitHub repository first, without adding a second README, then replace the remote URL above with your repository URL.
