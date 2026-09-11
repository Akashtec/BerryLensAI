import logging
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from tavily import TavilyClient

from config import settings
from evidence_quality import credibility_prior, deduplicate_evidence, domain_for_url, source_tier
from models.evidence import Evidence

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env')

logger = logging.getLogger(__name__)
api_key = os.getenv("TAVILY_API_KEY")
client = TavilyClient(api_key=api_key) if api_key else None

if client is None:
    logger.warning("TAVILY_API_KEY not found; evidence retrieval will return no results")


def fetch_evidence(queries: list[str]) -> list[Evidence]:
    """
    Runs search queries through Tavily and returns unique,
    structured evidence objects.
    """

    if not client:
        return []

    evidence_items = []

    for query in queries[:settings.max_queries_per_claim]:
        if not query.strip():
            continue
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=settings.max_results_per_query,
                timeout=8,
            )

            for result in response.get("results", []):
                title = result.get("title", "")
                url = result.get("url", "")
                snippet = result.get("content", "")[:600]

                # Skip results without a URL
                if not url:
                    continue

                evidence_items.append(
                    Evidence(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=title,
                        query=query,
                        domain=domain_for_url(url),
                        source_tier=source_tier(domain_for_url(url)),
                        credibility_score=credibility_prior(domain_for_url(url)),
                    )
                )

        except Exception:
            logger.exception("Search failed for query %r", query)

    unique = deduplicate_evidence([
        item.model_dump() for item in evidence_items
    ])
    return [Evidence.model_validate(item) for item in unique]


if __name__ == "__main__":
    test_queries = ["NASA alien life Mars 2026"]

    evidence = fetch_evidence(test_queries)

    for item in evidence:
        print(item)