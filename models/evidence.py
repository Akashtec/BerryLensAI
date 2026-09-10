from pydantic import BaseModel, Field
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
        "INSUFFICIENT EVIDENCE",
        "MISLEADING"
    ]
    confidence: int = Field(ge=0, le=100)
    explanation: str