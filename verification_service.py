"""Shared verification orchestration for the web and CLI entry points."""

from collections.abc import Callable
import logging
from time import perf_counter

from agents.analyst_agent import analyze_evidence, assess_evidence_stance
from agents.claim_agent import extract_search_queries
from agents.research_agent import fetch_evidence
from models.schemas import (
    ClaimAnalysis,
    ResearchPlan,
    ResearchStatus,
    Stance,
    VerificationReport,
    Verdict,
    VerifyRequest,
)
from verdict_engine import VerdictEngine

logger = logging.getLogger(__name__)


class VerificationService:
    """Run the providers behind one validated report contract."""

    def __init__(self, memory=None, persist: Callable | None = None):
        self.memory = memory
        self.persist = persist
        self.verdict_engine = VerdictEngine()

    def verify(self, raw_claim: str, progress: Callable[[str, dict], None] | None = None, user_id: int | None = None) -> VerificationReport:
        request = VerifyRequest(claim=raw_claim)
        started = perf_counter()

        try:
            queries = extract_search_queries(request.claim)
        except Exception:
            logger.exception("Query generation stage failed")
            queries = [request.claim]
        self._emit(progress, "queries_generated", {"count": len(queries)})

        try:
            evidence = fetch_evidence(queries)
        except Exception:
            logger.exception("Evidence retrieval stage failed")
            evidence = []
        self._emit(progress, "evidence_retrieved", {"count": len(evidence)})

        try:
            assessments = assess_evidence_stance(request.claim, evidence)
        except Exception:
            logger.exception("Evidence assessment stage failed")
            assessments = []
        self._emit(progress, "evidence_assessed", {"count": len(assessments)})

        try:
            synthesis = analyze_evidence(request.claim, evidence)
        except Exception:
            logger.exception("Evidence synthesis stage failed")
            synthesis = self._safe_synthesis(evidence)

        verdict, confidence = self.verdict_engine.compute(assessments)
        if not evidence:
            status = ResearchStatus.FAILED
            verdict = Verdict.INSUFFICIENT_EVIDENCE
        elif verdict in (Verdict.INSUFFICIENT_EVIDENCE, Verdict.PARTIALLY_SUPPORTED):
            status = ResearchStatus.PARTIAL
        else:
            status = ResearchStatus.COMPLETE

        report = VerificationReport(
            claim=request.claim,
            claim_type=ClaimAnalysis(
                raw_claim=request.claim,
                normalized=request.claim,
            ).claim_type,
            verdict=verdict,
            confidence=confidence,
            summary=synthesis.explanation,
            reasoning="The summary was generated from retrieved evidence; the final verdict was computed from validated source assessments.",
            synthesis_provider=getattr(synthesis, "provider_used", None),
            provider_failures=getattr(synthesis, "provider_failures", []),
            supporting_evidence=[item for item in assessments if item.stance == Stance.SUPPORTS],
            refuting_evidence=[item for item in assessments if item.stance == Stance.REFUTES],
            neutral_evidence=[item for item in assessments if item.stance in (Stance.NEUTRAL, Stance.UNCLEAR)],
            uncertainties=[] if assessments else ["No usable evidence was retrieved."],
            search_queries_used=queries,
            research_status=status,
            sources_checked=len(evidence),
            research_plan=ResearchPlan(queries=queries),
            processing_time_ms=round((perf_counter() - started) * 1000),
        )
        self._emit(progress, "synthesis_complete", {})
        self._emit(progress, "verdict_computed", {"verdict": report.verdict.value})
        if self.persist:
            try:
                self.persist(report, user_id)
            except Exception:
                logger.exception("Report persistence failed")
        elif self.memory and status in (ResearchStatus.COMPLETE, ResearchStatus.PARTIAL):
            try:
                self.memory.store(request.claim, {
                    "verdict": report.verdict.value,
                    "confidence": report.confidence_pct,
                    "summary": report.summary,
                    "research_status": report.research_status.value,
                    "schema_version": report.schema_version,
                    "sources": [
                        {"title": item.source.title, "url": str(item.source.url)}
                        for item in report.all_evidence[:3]
                    ],
                })
            except Exception:
                logger.exception("Historical memory write failed; returning report")
        return report

    @staticmethod
    def _emit(progress: Callable[[str, dict], None] | None, stage: str, data: dict):
        if progress:
            progress(stage, data)

    @staticmethod
    def _failure_report(claim: str, started: float) -> VerificationReport:
        return VerificationReport(
            claim=claim,
            verdict=Verdict.INSUFFICIENT_EVIDENCE,
            confidence=0.0,
            summary="Verification could not be completed safely.",
            reasoning="A pipeline stage failed before a defensible evidence-based result was available.",
            uncertainties=["External research or evidence assessment was unavailable."],
            research_status=ResearchStatus.FAILED,
            processing_time_ms=round((perf_counter() - started) * 1000),
        )

    @staticmethod
    def _safe_synthesis(evidence) -> object:
        from models.evidence import VerificationResult

        return VerificationResult(
            verdict="INSUFFICIENT_EVIDENCE",
            confidence=0,
            explanation=(
                "Evidence was retrieved, but the language-model synthesis stage "
                f"was unavailable. Retrieved {len(evidence)} source(s)."
            ),
            provider_used="deterministic",
        )

    @staticmethod
    def _cached_report(cached: dict, claim: str, started: float) -> VerificationReport:
        verdict_map = {
            "SUPPORTED": Verdict.SUPPORTED,
            "TRUE": Verdict.SUPPORTED,
            "REFUTED": Verdict.REFUTED,
            "FALSE": Verdict.REFUTED,
            "MIXED": Verdict.PARTIALLY_SUPPORTED,
            "PARTIALLY_SUPPORTED": Verdict.PARTIALLY_SUPPORTED,
            "INSUFFICIENT EVIDENCE": Verdict.INSUFFICIENT_EVIDENCE,
            "INSUFFICIENT_EVIDENCE": Verdict.INSUFFICIENT_EVIDENCE,
            "UNCERTAIN": Verdict.INSUFFICIENT_EVIDENCE,
            "ERROR": Verdict.INSUFFICIENT_EVIDENCE,
        }
        verdict = verdict_map.get(
            str(cached.get("verdict", "")).upper().replace("-", "_"),
            Verdict.INSUFFICIENT_EVIDENCE,
        )
        confidence = min(1.0, max(0.0, float(cached.get("confidence", 0)) / 100))
        return VerificationReport(
            claim=claim,
            verdict=verdict,
            confidence=confidence,
            summary=cached.get("summary", "Retrieved from historical memory."),
            reasoning="Retrieved from historical memory; fresh research was not performed.",
            uncertainties=["This result is historical and may require fresh verification."],
            research_status=ResearchStatus.CACHED,
            from_cache=True,
            processing_time_ms=round((perf_counter() - started) * 1000),
        )
