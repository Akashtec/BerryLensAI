"""Deterministic verdict and confidence aggregation."""

from models.schemas import EvidenceAssessment, Stance, Verdict


class VerdictEngine:
    """Turn assessed evidence into an auditable public verdict."""

    def compute(self, assessments: list[EvidenceAssessment]) -> tuple[Verdict, float]:
        usable = [
            item for item in assessments
            if item.stance in (Stance.SUPPORTS, Stance.REFUTES)
        ]
        if len(usable) < 2:
            return Verdict.UNCERTAIN, self._confidence(usable, 0.6)

        support_score = sum(
            item.quality_score for item in usable if item.stance == Stance.SUPPORTS
        )
        refute_score = sum(
            item.quality_score for item in usable if item.stance == Stance.REFUTES
        )
        total = support_score + refute_score
        if total == 0:
            return Verdict.UNCERTAIN, 0.0

        support_norm = support_score / total
        refute_norm = refute_score / total
        gap = abs(support_norm - refute_norm)
        confidence = self._confidence(usable, 1.15 if gap >= 0.15 else 0.85)

        if support_score and refute_score and gap < 0.35:
            return Verdict.MIXED, confidence
        if gap < 0.15:
            return Verdict.UNCERTAIN, confidence
        return (
            Verdict.TRUE if support_norm > refute_norm else Verdict.FALSE,
            confidence,
        )

    @staticmethod
    def _confidence(assessments: list[EvidenceAssessment], consistency: float) -> float:
        if not assessments:
            return 0.0
        average_quality = sum(item.quality_score for item in assessments) / len(assessments)
        volume_factor = {1: 0.60, 2: 0.75, 3: 0.85, 4: 0.92}.get(len(assessments), 1.0)
        return min(1.0, round(average_quality * consistency * volume_factor, 3))