from models.schemas import EvidenceAssessment, Source, Stance, Verdict
from verdict_engine import VerdictEngine


def make_assessment(stance: Stance, quality: float) -> EvidenceAssessment:
    return EvidenceAssessment(
        source=Source(
            url="https://example.com/report",
            title="Example report",
            domain="example.com",
        ),
        relevant_passage="Relevant passage",
        stance=stance,
        relevance_score=quality,
        nli_confidence=quality,
        quality_score=quality,
    )


def test_single_source_abstains():
    verdict, confidence = VerdictEngine().compute([
        make_assessment(Stance.SUPPORTS, 0.9),
    ])

    assert verdict is Verdict.UNCERTAIN
    assert confidence < 0.7


def test_consistent_supporting_sources_are_true():
    verdict, confidence = VerdictEngine().compute([
        make_assessment(Stance.SUPPORTS, 0.9),
        make_assessment(Stance.SUPPORTS, 0.8),
    ])

    assert verdict is Verdict.TRUE
    assert confidence > 0.7


def test_balanced_sources_are_mixed():
    verdict, _ = VerdictEngine().compute([
        make_assessment(Stance.SUPPORTS, 0.8),
        make_assessment(Stance.REFUTES, 0.8),
    ])

    assert verdict is Verdict.MIXED