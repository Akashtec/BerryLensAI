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
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    groq_api_key = os.getenv("GROQ_API_KEY")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    cerebras_api_key = os.getenv("CEREBRAS_API_KEY")
    primary_llm_provider = os.getenv("PRIMARY_LLM_PROVIDER", "gemini").strip().lower()
    fallback_llm_providers = [
        provider.strip().lower()
        for provider in os.getenv("FALLBACK_LLM_PROVIDERS", "").split(",")
        if provider.strip()
    ]
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_fallback_models = [
        model.strip()
        for model in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.0-flash,gemini-1.5-flash").split(",")
        if model.strip()
    ]
    groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    cerebras_model = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
    llm_timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", os.getenv("GEMINI_TIMEOUT_SECONDS", "8")))
    disable_llm = os.getenv("BERRYLENS_DISABLE_LLM", "false").lower() == "true"
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
