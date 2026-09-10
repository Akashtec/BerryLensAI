"""Validated contracts shared by verification stages and API responses."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Verdict(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    MIXED = "MIXED"
    UNCERTAIN = "UNCERTAIN"
    ERROR = "ERROR"


class Stance(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    NEUTRAL = "NEUTRAL"
    UNCLEAR = "UNCLEAR"


class ClaimType(str, Enum):
    FACTUAL = "FACTUAL"
    OPINION = "OPINION"
    PREDICTION = "PREDICTION"
    AMBIGUOUS = "AMBIGUOUS"


class ResearchStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CACHED = "CACHED"


class ClaimAnalysis(BaseModel):
    raw_claim: str = Field(min_length=1)
    normalized: str = Field(min_length=1)
    claim_type: ClaimType = ClaimType.FACTUAL
    entities: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    language: str = "en"


class ResearchPlan(BaseModel):
    queries: list[str] = Field(default_factory=list)
    max_results_per_query: int = Field(default=2, ge=1, le=20)
    seek_contradiction: bool = True


class Source(BaseModel):
    url: HttpUrl
    title: str
    domain: str
    credibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    tier: str | None = None
    source_type: str = "UNKNOWN"
    publication_date: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RawEvidence(BaseModel):
    source: Source
    snippet: str
    query_used: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str | None = None
    duplicate_of: str | None = None


class EvidenceAssessment(BaseModel):
    source: Source
    relevant_passage: str
    stance: Stance
    relevance_score: float = Field(ge=0.0, le=1.0)
    nli_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    explanation: str = ""


class SynthesisResult(BaseModel):
    summary: str
    reasoning: str = ""
    uncertainties: list[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    id: int | None = None
    claim: str
    claim_type: ClaimType = ClaimType.FACTUAL
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    reasoning: str = ""
    supporting_evidence: list[EvidenceAssessment] = Field(default_factory=list)
    refuting_evidence: list[EvidenceAssessment] = Field(default_factory=list)
    neutral_evidence: list[EvidenceAssessment] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    search_queries_used: list[str] = Field(default_factory=list)
    research_status: ResearchStatus
    from_cache: bool = False
    sources_checked: int = 0
    processing_time_ms: int | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entities: list[str] = Field(default_factory=list)
    research_plan: ResearchPlan | None = None
    schema_version: str = "1.1"

    @property
    def confidence_pct(self) -> int:
        return round(self.confidence * 100)

    @property
    def all_evidence(self) -> list[EvidenceAssessment]:
        return self.supporting_evidence + self.refuting_evidence + self.neutral_evidence


class VerifyRequest(BaseModel):
    claim: str = Field(min_length=10, max_length=1000)

    @field_validator("claim")
    @classmethod
    def normalize_claim(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("claim cannot be blank")
        return normalized