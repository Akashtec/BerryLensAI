"""Application configuration loaded from the repository environment file."""

import os
import json
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def _load_source_tiers() -> dict:
    path = PROJECT_ROOT / "config" / "source_tiers.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tier_1": [], "tier_2": [], "tier_3": [], "blacklist": []}


def _int_setting(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error


class Settings:
    """Runtime settings with conservative local-development defaults."""

    huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
    huggingface_model = os.getenv(
        "HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3"
    )
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    flask_secret_key = os.getenv("FLASK_SECRET_KEY")
    api_key = os.getenv("BERRYLENS_API_KEY")
    rate_limit_per_minute = _int_setting("RATE_LIMIT_PER_MINUTE", 5)
    demo_mode = os.getenv("BERRYLENS_DEMO_MODE", "false").lower() == "true"
    max_claim_length = _int_setting("MAX_CLAIM_LENGTH", 1000)
    max_queries_per_claim = _int_setting("MAX_QUERIES_PER_CLAIM", 3)
    max_results_per_query = _int_setting("MAX_RESULTS_PER_QUERY", 2)
    max_research_rounds = _int_setting("MAX_RESEARCH_ROUNDS", 1)
    max_cache_age_days = _int_setting("MAX_CACHE_AGE_DAYS", 30)
    database_path = Path(
        os.getenv("BERRYLENS_DB_PATH", PROJECT_ROOT / "data" / "berrylens.db")
    ).expanduser()
    chroma_path = Path(
        os.getenv("BERRYLENS_CHROMA_PATH", PROJECT_ROOT / "data" / "chroma_db")
    ).expanduser()
    source_tiers = _load_source_tiers()
    min_evidence_quality = float(os.getenv("MIN_EVIDENCE_QUALITY", "0.3"))


settings = Settings()