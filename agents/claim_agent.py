import os
import re
import logging
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from models.schemas import ClaimAnalysis, ClaimType

logger = logging.getLogger(__name__)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env')

model_name = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
mistral_client = InferenceClient(api_key=huggingface_api_key, timeout=8) if huggingface_api_key else None

if mistral_client:
    logger.info("✅ Mistral client initialized with model %s", model_name)
else:
    logger.warning("⚠️ HUGGINGFACE_API_KEY not found; using deterministic query fallback")


MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

ORG_SUFFIXES = {
    "AI", "Association", "Bank", "College", "Company", "Corp", "Corporation",
    "Foundation", "Group", "Inc", "Institute", "LLC", "Ltd", "Ministry",
    "NASA", "NOAA", "Organization", "University",
}

EVENT_WORDS = {
    "acquired", "announced", "banned", "built", "closed", "created",
    "discovered", "founded", "launched", "opened", "passed", "released",
    "reported", "resigned", "signed", "won",
}

OPINION_MARKERS = {
    "bad", "beautiful", "best", "better", "good", "important",
    "overrated", "should", "underrated", "worst",
}

PREDICTION_MARKERS = {
    "by 2030", "by 2040", "could", "expected", "forecast", "may",
    "might", "next year", "planned", "predicts", "will", "would",
}


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        cleaned = " ".join(str(item).split()).strip(" ,.;:")
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique


def _detect_language(text: str) -> str:
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return "unknown"
    return "en"


def _extract_dates(text: str) -> list[str]:
    dates = []
    dates.extend(re.findall(rf"\b(?:{MONTH_PATTERN})\s+\d{{1,2}},?\s+\d{{4}}\b", text, flags=re.IGNORECASE))
    dates.extend(re.findall(rf"\b(?:{MONTH_PATTERN})\s+\d{{4}}\b", text, flags=re.IGNORECASE))
    dates.extend(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text))
    dates.extend(re.findall(r"\b(?:19|20)\d{2}\b", text))
    lowered = text.lower()
    for relative in ("today", "yesterday", "tomorrow", "last year", "this year", "next year"):
        if relative in lowered:
            dates.append(relative)
    return _dedupe(dates)


def _extract_numbers(text: str) -> list[str]:
    pattern = r"(?:[$€£₹]\s*)?\b\d+(?:,\d{3})*(?:\.\d+)?(?:\s?(?:%|percent|million|billion|trillion|degrees?|celsius|fahrenheit|km|miles?))?"
    return _dedupe(re.findall(pattern, text, flags=re.IGNORECASE))


def _extract_entities(text: str) -> list[str]:
    candidates = re.findall(
        r"\b(?:[A-Z][a-zA-Z0-9&.-]*|[A-Z]{2,})(?:\s+(?:[A-Z][a-zA-Z0-9&.-]*|[A-Z]{2,}))*",
        text,
    )
    ignored = {"A", "An", "At", "By", "In", "On", "That", "The", "This"}
    return _dedupe([item for item in candidates if item not in ignored and len(item) > 1])


def _classify_entities(entities: list[str], text: str) -> tuple[list[str], list[str], list[str]]:
    organizations = []
    people = []
    locations = []
    for entity in entities:
        parts = entity.split()
        if set(parts).intersection(ORG_SUFFIXES) or entity.isupper():
            organizations.append(entity)
        elif len(parts) >= 2:
            people.append(entity)
    for match in re.findall(r"\b(?:in|from|at|near)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", text):
        locations.append(match)
    return _dedupe(people), _dedupe(organizations), _dedupe(locations)


def _extract_events(text: str) -> list[str]:
    lowered = text.lower()
    return sorted({word for word in EVENT_WORDS if re.search(rf"\b{re.escape(word)}\b", lowered)})


def _claim_type(text: str) -> ClaimType:
    lowered = text.lower()
    if "?" in text:
        return ClaimType.AMBIGUOUS
    if any(marker in lowered for marker in OPINION_MARKERS):
        return ClaimType.OPINION
    if any(marker in lowered for marker in PREDICTION_MARKERS):
        return ClaimType.PREDICTION
    return ClaimType.FACTUAL


def decompose_claim(claim: str) -> list[str]:
    """Split simple compound claims into bounded atomic subclaims."""
    normalized = re.sub(r"\s+", " ", claim).strip()
    pieces = re.split(r"\s+(?:and|but|while|whereas)\s+|;\s*", normalized)
    subclaims = []
    for piece in pieces:
        cleaned = piece.strip(" .")
        if len(cleaned.split()) >= 4:
            subclaims.append(cleaned + ".")
    return _dedupe(subclaims[:5]) or [normalized]


def _fallback_search_queries_from_analysis(analysis: ClaimAnalysis) -> list[str]:
    queries = [subclaim.rstrip(".") for subclaim in analysis.subclaims]
    if analysis.entities or analysis.dates or analysis.events:
        queries.append(" ".join(analysis.entities[:3] + analysis.dates[:2] + analysis.events[:2]))
    queries.extend([
        analysis.normalized,
        f"{analysis.normalized} official source",
        f"{analysis.normalized} fact check",
    ])
    return _dedupe([query for query in queries if query])[:3]


def analyze_claim(claim: str) -> ClaimAnalysis:
    """Create deterministic claim structure before search or evidence analysis."""
    normalized = re.sub(r"\s+", " ", claim).strip()
    entities = _extract_entities(normalized)
    people, organizations, locations = _classify_entities(entities, normalized)
    dates = _extract_dates(normalized)
    analysis = ClaimAnalysis(
        raw_claim=claim,
        normalized=normalized,
        claim_type=_claim_type(normalized),
        entities=entities,
        people=people,
        organizations=organizations,
        locations=locations,
        dates=dates,
        numbers=_extract_numbers(normalized),
        events=_extract_events(normalized),
        subclaims=decompose_claim(normalized),
        language=_detect_language(normalized),
        temporal_context=", ".join(dates) if dates else None,
    )
    analysis.search_queries = _fallback_search_queries_from_analysis(analysis)
    return analysis


def _fallback_search_queries(claim: str) -> list[str]:
    """Create safe search queries when all AI models are unavailable."""
    normalized_claim = re.sub(r"\s+", " ", claim).strip()
    return [
        normalized_claim,
        f"{normalized_claim} official source",
        f"{normalized_claim} fact check",
    ]


def _extract_with_mistral(claim: str) -> list[str]:
    """Extract queries using Mistral through the Hugging Face chat API."""
    if not mistral_client:
        raise RuntimeError("Hugging Face client not initialized")
    
    prompt = f"""You are Agent #1 (Claim Intelligence) in BerryLens AI.
Analyze this claim and generate 3 short, precise web search queries to fact-check it.

CLAIM: "{claim}"

CRITICAL RULE: Output ONLY 3 lines. Each line must contain ONLY one search query.
Do NOT output headings, analysis, numbers, or bullet points."""

    response = mistral_client.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        model=model_name,
        max_tokens=150,
        temperature=0.3,
    )

    content = response.choices[0].message.content if response.choices else ""
    lines = (content or "").strip().split("\n")
    queries = [line.strip().lstrip("0123456789.-*` ") for line in lines if line.strip()]
    return queries[:3] or _fallback_search_queries(claim)


def extract_search_queries(claim: str) -> list[str]:
    """
    Analyzes a raw claim and extracts 3 search queries.
    Falls back to deterministic queries if Mistral is unavailable.
    """
    fallback = _fallback_search_queries(claim)
    if not mistral_client or os.getenv("BERRYLENS_AI_QUERY_EXPANSION", "false").lower() != "true":
        return fallback
    try:
        logger.info("Generating optional AI search queries")
        queries = _extract_with_mistral(claim)
        if queries:
            return queries
    except Exception as error:
        logger.warning("AI query generation unavailable; using direct queries: %s", error)
    return fallback


if __name__ == "__main__":
    test_claim = "GPT-6 Astra launched yesterday"
    print("\n" + "="*60)
    print("Testing extract_search_queries()...")
    print("="*60)
    result = extract_search_queries(test_claim)
    print(f"\nResult: {result}\n")
