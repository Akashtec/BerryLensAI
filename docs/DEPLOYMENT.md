# Deployment

## Docker

1. Create a production `.env` from `.env.example`.
2. Rotate provider keys if they were ever exposed.
3. Build and run:

```powershell
docker compose build
docker compose up app
```

The app listens on port `8000`; health is available at `/health` and metrics at `/metrics`. Prometheus is available on `9090`; Grafana is available on `3000`. The Compose file includes a Prometheus scrape configuration. Grafana dashboards should be provisioned by the deployment operator according to the metrics exposed by the app.

## Render or another Docker host

Use the repository `Dockerfile`, set the service port to `8000`, and configure `HUGGINGFACE_API_KEY`, `TAVILY_API_KEY`, `FLASK_SECRET_KEY`, and optional `BERRYLENS_API_KEY` as platform secrets. Configure a health check for `/health`.

## Heroku-compatible deployment

The `Procfile`, `runtime.txt`, and `gunicorn.conf.py` are included. Set the same environment variables in the platform configuration and deploy with the platform's normal Git workflow.

## Database status

SQLite remains the supported persistence backend for this release. The application stores reports under the project path and excludes local database files from version control. PostgreSQL migration is a planned follow-up; do not set `DATABASE_URL` expecting it to switch the current raw-SQLite adapter automatically.

## Production scope note

This repository includes deployment scaffolding, health checks, lightweight Prometheus-compatible counters, and session authentication. It does not yet include PostgreSQL switching, a provisioned Grafana dashboard, Swagger UI, or favorites. Treat those as follow-up work before calling the service a fully multi-user production deployment.

## Optional prior classifier

`train_prior_classifier.py` is an optional offline utility. It requires `datasets`, `transformers`, and `torch`, downloads DistilBERT, and saves an auxiliary model. LIAR is political and domain-specific; its metrics must not be presented as general verification accuracy. The trained classifier is not called by the verification pipeline by default.
