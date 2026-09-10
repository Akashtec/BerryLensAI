"""Deterministic source metadata and duplicate handling."""

from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config import settings


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(("utm_", "fbclid", "gclid"))
    ])
    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def domain_for_url(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def source_tier(domain: str) -> str:
    domain = domain.lower().removeprefix("www.")
    for tier in ("tier_1", "tier_2", "tier_3"):
        if domain in settings.source_tiers.get(tier, []):
            return tier
    if domain in settings.source_tiers.get("blacklist", []):
        return "blacklist"
    return "unknown"


def credibility_prior(domain: str) -> float:
    """Return a transparent prior, never a claim that an article is true."""
    return {
        "tier_1": 0.85,
        "tier_2": 0.70,
        "tier_3": 0.55,
        "blacklist": 0.25,
        "unknown": 0.50,
    }[source_tier(domain)]


def deduplicate_evidence(items: list[dict]) -> list[dict]:
    """Remove exact URLs and highly similar snippets, retaining first occurrence."""
    unique = []
    seen_urls: set[str] = set()
    for item in items:
        normalized = normalize_url(item.get("url", ""))
        title = " ".join(item.get("title", "").lower().split())
        snippet = " ".join(item.get("snippet", "").lower().split())
        text = f"{title} {snippet}"
        if not normalized or normalized in seen_urls:
            continue
        if any(
            SequenceMatcher(None, text, previous["_text"]).ratio() >= 0.92
            or SequenceMatcher(None, snippet, previous["_snippet"]).ratio() >= 0.95
            for previous in unique
        ):
            continue
        seen_urls.add(normalized)
        unique.append({**item, "_text": text, "_snippet": snippet})
    return [{key: value for key, value in item.items() if key not in {"_text", "_snippet"}} for item in unique]