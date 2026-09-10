import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from tenacity import retry, stop_after_attempt, wait_exponential

from models.evidence import Evidence, VerificationResult
from models.schemas import EvidenceAssessment, Source, Stance
from evidence_quality import credibility_prior, domain_for_url, source_tier

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / '.env')

logger = logging.getLogger(__name__)
model_name = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
client = InferenceClient(api_key=huggingface_api_key) if huggingface_api_key else None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
def _generate_json(prompt: str) -> dict | list:
    if not client:
        raise RuntimeError("Hugging Face client not initialized")
    response = client.text_generation(
        prompt,
        model=model_name,
        max_new_tokens=500,
        temperature=0.2,
    )
    return json.loads(response or "")


def assess_evidence_stance(claim: str, evidence: list[Evidence]) -> list[EvidenceAssessment]:
    """Classify each source's stance independently from its credibility prior."""
    if not evidence:
        return []

    evidence_block = "\n\n".join(
        f"ID: {index}\nTitle: {item.title}\nURL: {item.url}\nText: {item.snippet}"
        for index, item in enumerate(evidence)
    )
    prompt = f"""Assess each evidence item against the claim.

CLAIM: {claim}

EVIDENCE:
{evidence_block}

Return ONLY a JSON array with one object per evidence ID, using this shape:
[{{"id": 0, "stance": "SUPPORTS|REFUTES|NEUTRAL|UNCLEAR", "relevance": 0.0, "confidence": 0.0, "explanation": "..."}}]

Use UNCLEAR when the passage does not directly address the claim. Do not infer source trust from stance.
"""
    try:
        assessments = _generate_json(prompt)
        by_id = {int(item["id"]): item for item in assessments}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, RuntimeError) as error:
        logger.warning("Evidence stance assessment unavailable: %s", error)
        by_id = {}

    result = []
    for index, item in enumerate(evidence):
        domain = domain_for_url(item.url)
        source = Source(
            url=item.url,
            title=item.title,
            domain=domain,
            tier=source_tier(domain),
            credibility_score=credibility_prior(domain),
        )
        raw = by_id.get(index, {})
        try:
            stance = Stance(str(raw.get("stance", "UNCLEAR")).upper())
        except ValueError:
            stance = Stance.UNCLEAR
        relevance = min(1.0, max(0.0, float(raw.get("relevance", 0.0))))
        stance_confidence = min(1.0, max(0.0, float(raw.get("confidence", 0.0))))
        quality = relevance * stance_confidence * source.credibility_score
        result.append(EvidenceAssessment(
            source=source,
            relevant_passage=item.snippet,
            stance=stance,
            relevance_score=relevance,
            nli_confidence=stance_confidence,
            quality_score=quality,
            explanation=str(raw.get("explanation", "No source-level assessment was available.")),
        ))
    return result


def analyze_evidence(claim: str, evidence: list[Evidence]) -> VerificationResult:
    """
    Agent 3: Synthesizes evidence and returns a structured verdict.
    Falls back gracefully if the API quota is exceeded.
    """

    # Build evidence context
    evidence_text = "\n\n".join([
        f"Source: {e.title} ({e.url})\n{e.snippet}"
        for e in evidence
    ]) if evidence else "No evidence was found."

    prompt = f"""You are BerryLens, an expert fact-checking AI.

CLAIM TO VERIFY:
"{claim}"

EVIDENCE FOUND:
{evidence_text}

Based ONLY on the evidence above, return a JSON object with this exact structure:
{{
  "verdict": "SUPPORTED" or "REFUTED" or "INSUFFICIENT EVIDENCE" or "MISLEADING",
  "confidence": <integer 0-100>,
  "explanation": "<your reasoning here>"
}}

Rules:
- Be concise. One paragraph.
- Cite specific sources.
- Confidence must reflect the strength of the evidence, NOT simply the number of sources.
- Do NOT use 100 confidence unless the evidence is exceptionally strong and directly proves the claim.
- If sources appear to repeat the same underlying report, treat them as one source rather than independent confirmations.
- Give lower confidence when evidence comes from social media, reposts, or indirect reporting.
- Use these confidence guidelines:
  - 90-99: Very strong, direct, independently corroborated evidence.
  - 75-89: Strong evidence, but with some limitations.
  - 50-74: Moderate or mixed evidence.
  - 25-49: Weak evidence.
  - 0-24: Very little or no reliable evidence.
"""

    # DEMO MODE: Skip API call entirely
    # (for testing when quota is unavailable)
    if os.getenv("BERRYLENS_DEMO_MODE", "false").lower() == "true":
        print("  [Agent 3] 🎭 DEMO MODE: Returning mock verdict (no API call).")

        return VerificationResult(
            verdict="INSUFFICIENT EVIDENCE",
            confidence=50,
            explanation=(
                f"DEMO MODE: Skipped LLM call. Pipeline collected "
                f"{len(evidence)} evidence items. Set "
                f"BERRYLENS_DEMO_MODE=false in .env to use real API."
            )
        )

    # REAL MODE: Call Mistral with error handling
    try:
        result = _generate_json(prompt)
        raw_verdict = str(result.get("verdict", "INSUFFICIENT EVIDENCE")).upper()
        verdict_map = {
            "SUPPORTED": "SUPPORTED",
            "TRUE": "SUPPORTED",
            "REFUTED": "REFUTED",
            "FALSE": "REFUTED",
            "MISLEADING": "MISLEADING",
            "INSUFFICIENT EVIDENCE": "INSUFFICIENT EVIDENCE",
            "UNVERIFIABLE": "INSUFFICIENT EVIDENCE",
        }

        return VerificationResult(
            verdict=verdict_map.get(raw_verdict, "INSUFFICIENT EVIDENCE"),
            confidence=result.get(
                "confidence",
                50
            ),
            explanation=result.get(
                "explanation",
                "No explanation provided."
            )
        )

    except (json.JSONDecodeError, TypeError, ValueError, RuntimeError) as e:
        error_str = str(e)

        if (
            "429" in error_str
            or "RESOURCE_EXHAUSTED" in error_str
            or "quota" in error_str.lower()
        ):
            logger.warning("Mistral API quota exceeded (429)")
            print(
                "  → To keep testing: Add "
                "BERRYLENS_DEMO_MODE=true to your .env file"
            )
            print(
                "  → To fix for real: Wait 24 hours OR get "
                "a working Hugging Face API key or BERRYLENS_DEMO_MODE=true."
            )

            return VerificationResult(
                verdict="INSUFFICIENT EVIDENCE",
                confidence=0,
                explanation=(
                    f"API quota exceeded (429). Pipeline collected "
                    f"{len(evidence)} evidence items but could not reach "
                    f"a verdict. Set BERRYLENS_DEMO_MODE=true in .env "
                    f"to test without API calls."
                )
            )

        print(f"  [Agent 3] ❌ Evidence synthesis unavailable: {error_str[:200]}")
        return VerificationResult(
            verdict="INSUFFICIENT EVIDENCE",
            confidence=0,
            explanation=(
                f"The evidence synthesis step failed safely ({type(e).__name__}). "
                "No definitive verdict was generated."
            ),
        )