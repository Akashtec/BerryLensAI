"""Evidence assessment and synthesis with a deterministic local fallback."""

import json
import logging
import os
import re
from typing import Any

from models.evidence import Evidence, VerificationResult
from models.schemas import EvidenceAssessment, Source, Stance

logger = logging.getLogger(__name__)


def _extract_json(content: str) -> dict | list:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI response content must be a non-empty string")
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
    if text.endswith("```"):
        text = text[:-3].rstrip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = min((index for index in (text.find("{"), text.find("[")) if index >= 0), default=-1)
        if start < 0:
            raise ValueError("No JSON object or array found in AI response")
        parsed, end = json.JSONDecoder().raw_decode(text[start:])
        if text[start + end:].strip():
            raise ValueError("Unexpected content found after JSON payload")
    if not isinstance(parsed, (dict, list)):
        raise ValueError("AI JSON must be an object or array")
    return parsed


def _generate_json(prompt: str) -> dict | list:
    """Call the optional model boundary; callers always provide a fallback."""
    raise RuntimeError("Structured analyst generation is not configured")


def _source(evidence: Evidence) -> Source:
    return Source(
        url=evidence.url,
        title=evidence.title or evidence.domain or "Untitled source",
        domain=evidence.domain or evidence.source or "unknown",
        credibility_score=evidence.credibility_score,
        tier=evidence.source_tier,
    )


def assess_evidence_stance(claim: str, evidence: list[Evidence]) -> list[EvidenceAssessment]:
    """Classify retrieved passages conservatively without requiring an AI key."""
    assessments = []
    claim_terms = set(re.findall(r"[a-z0-9]+", claim.lower()))
    refuting_words = {"false", "not", "否", "debunk", "incorrect", "refuted", "misleading"}
    supporting_words = {"true", "confirmed", "evidence", "verified", "supports", "correct"}
    for item in evidence:
        passage = f"{item.title} {item.snippet}".lower()
        overlap = len(claim_terms.intersection(re.findall(r"[a-z0-9]+", passage)))
        relevance = min(1.0, overlap / max(1, min(8, len(claim_terms))))
        if any(word in passage for word in refuting_words):
            stance = Stance.REFUTES
        elif any(word in passage for word in supporting_words):
            stance = Stance.SUPPORTS
        else:
            stance = Stance.NEUTRAL
        assessments.append(EvidenceAssessment(
            source=_source(item),
            relevant_passage=item.snippet[:1200],
            stance=stance,
            relevance_score=relevance,
            nli_confidence=0.5,
            quality_score=max(0.0, min(1.0, item.credibility_score * (0.5 + relevance / 2))),
            explanation="Classified by the local evidence heuristic; treat neutral evidence as unresolved.",
        ))
    return assessments


def analyze_evidence(claim: str, evidence: list[Evidence]) -> VerificationResult:
    """Produce a safe summary when structured model synthesis is unavailable."""
    try:
        generated = _generate_json(f"Summarize evidence for: {claim}")
        if isinstance(generated, dict):
            return VerificationResult.model_validate(generated)
    except Exception as error:
        logger.info("Structured synthesis unavailable: %s", error)
    if not evidence:
        return VerificationResult(
            verdict="INSUFFICIENT EVIDENCE",
            confidence=0,
            explanation="No usable sources were retrieved, so BerryLens cannot make a defensible claim-level judgment.",
        )
    return VerificationResult(
        verdict="INSUFFICIENT EVIDENCE",
        confidence=0,
        explanation=f"BerryLens retrieved {len(evidence)} source(s), but automated synthesis is unavailable. Review the cited passages directly.",
    )
