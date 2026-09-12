from pydantic import BaseModel, Field, field_validator
from typing import Literal


class Evidence(BaseModel):
    title: str
    url: str
    snippet: str
    source: str
    query: str
    domain: str = ""
    publication_date: str | None = None
    retrieved_at: str | None = None
    source_tier: str = "unknown"
    credibility_score: float = Field(default=0.5, ge=0.0, le=1.0)


class VerificationResult(BaseModel):
    verdict: Literal[
        "SUPPORTED",
        "REFUTED",
        "PARTIALLY_SUPPORTED",
        "INSUFFICIENT_EVIDENCE",
    ]
    confidence: int = Field(ge=0, le=100)
    explanation: str
    provider_used: str | None = None
    provider_failures: list[str] = Field(default_factory=list)

    @field_validator("verdict", mode="before")
    @classmethod
    def normalize_verdict(cls, value):
        legacy_map = {
            "TRUE": "SUPPORTED",
            "FALSE": "REFUTED",
            "MIXED": "PARTIALLY_SUPPORTED",
            "MISLEADING": "PARTIALLY_SUPPORTED",
            "UNCERTAIN": "INSUFFICIENT_EVIDENCE",
            "ERROR": "INSUFFICIENT_EVIDENCE",
            "INSUFFICIENT EVIDENCE": "INSUFFICIENT_EVIDENCE",
            "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
        }
        normalized = str(value).strip().upper().replace("-", "_")
        return legacy_map.get(normalized, value)
