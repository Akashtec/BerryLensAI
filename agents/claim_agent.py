import os
import re
import logging
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env')

model_name = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
mistral_client = InferenceClient(api_key=huggingface_api_key) if huggingface_api_key else None

if mistral_client:
    logger.info("Mistral client initialized with model %s", model_name)
else:
    logger.warning("HUGGINGFACE_API_KEY not found; using deterministic query fallback")


def _fallback_search_queries(claim: str) -> list[str]:
    """Create safe search queries when all AI models are unavailable."""
    normalized_claim = re.sub(r"\s+", " ", claim).strip()
    return [
        normalized_claim,
        f"{normalized_claim} official source",
        f"{normalized_claim} fact check",
    ]


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
def _extract_with_mistral(claim: str) -> list[str]:
    """Extract queries using Mistral through the Hugging Face Inference API."""
    if not mistral_client:
        raise RuntimeError("Hugging Face client not initialized")
    
    prompt = f"""You are Agent #1 (Claim Intelligence) in BerryLens AI.
Analyze this claim and generate 3 short, precise web search queries to fact-check it.

CLAIM: "{claim}"

CRITICAL RULE: Output ONLY 3 lines. Each line must contain ONLY one search query.
Do NOT output headings, analysis, numbers, or bullet points."""

    response = mistral_client.text_generation(
        prompt,
        model=model_name,
        max_new_tokens=150,
        temperature=0.3
    )
    
    lines = (response or "").strip().split("\n")
    queries = [line.strip().lstrip("0123456789.-*` ") for line in lines if line.strip()]
    return queries[:3] or _fallback_search_queries(claim)


def extract_search_queries(claim: str) -> list[str]:
    """
    Analyzes a raw claim and extracts 3 search queries.
    Falls back to deterministic queries if Mistral is unavailable.
    """
    try:
        logger.info("Generating search queries with Mistral")
        queries = _extract_with_mistral(claim)
        logger.info("Mistral generated %d search queries", len(queries))
        return queries
    except Exception as e:
        logger.warning("Mistral query generation failed (%s): %s", type(e).__name__, e)

    logger.warning("Using deterministic fallback search queries")
    return _fallback_search_queries(claim)


if __name__ == "__main__":
    test_claim = "GPT-6 Astra launched yesterday"
    print("\n" + "="*60)
    print("Testing extract_search_queries()...")
    print("="*60)
    result = extract_search_queries(test_claim)
    print(f"\nResult: {result}\n")