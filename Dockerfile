# Use the current pinned multi-architecture digest for immutable builds.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    BERRYLENS_DB_PATH=/app/data/berrylens.db \
    BERRYLENS_CHROMA_PATH=/app/data/chroma_db

# Create a non-root user to run the app
RUN useradd --create-home --shell /bin/bash appuser
RUN mkdir -p /app/data \
  && chown appuser:appuser /app/data

WORKDIR /app

# Copy requirements and install dependencies first (better layer caching)
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
  && python -m pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.7.1+cpu \
  && sed '/^--extra-index-url /d; /^torch==/d' requirements.txt > /tmp/runtime-requirements.txt \
  && python -m pip install --no-cache-dir \
    --index-url https://pypi.org/simple \
    -r /tmp/runtime-requirements.txt \
  && rm /tmp/runtime-requirements.txt \
  && python -m pip check

# Copy the application code
COPY --chown=appuser:appuser . .

# Switch to the non-root user
USER appuser

# Expose the port
EXPOSE 8000

# Use Python's standard library so the healthcheck needs no extra runtime package.
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

# Run Gunicorn
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]