from models.schemas import ResearchStatus, VerificationReport, Verdict
from verification_service import VerificationService


def test_cached_legacy_supported_result_maps_to_true():
    report = VerificationService._cached_report(
        {'verdict': 'SUPPORTED', 'confidence': '80', 'summary': 'Cached summary'},
        'A sufficiently long claim.',
        0.0,
    )

    assert report.verdict is Verdict.SUPPORTED
    assert report.confidence == 0.8
    assert report.research_status is ResearchStatus.CACHED


def test_cached_unknown_result_abstains():
    report = VerificationService._cached_report(
        {'verdict': 'UNVERIFIABLE', 'confidence': '0', 'summary': 'Failed'},
        'A sufficiently long claim.',
        0.0,
    )

    assert report.verdict is Verdict.INSUFFICIENT_EVIDENCE
    assert report.confidence == 0.0


def test_legacy_report_verdicts_normalize_to_mission_contract():
    report = VerificationReport(
        claim="A sufficiently long claim.",
        verdict="MIXED",
        confidence=0.5,
        summary="Legacy record.",
        research_status=ResearchStatus.COMPLETE,
    )

    assert report.verdict is Verdict.PARTIALLY_SUPPORTED


def test_query_provider_failure_returns_safe_uncertain_report(monkeypatch):
    import verification_service as service_module
    from models.evidence import VerificationResult

    def fail(_claim):
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(service_module, "extract_search_queries", fail)
    monkeypatch.setattr(service_module, "fetch_evidence", lambda queries: [])
    monkeypatch.setattr(service_module, "assess_evidence_stance", lambda claim, evidence: [])
    monkeypatch.setattr(
        service_module,
        "analyze_evidence",
        lambda claim, evidence: VerificationResult(
            verdict="INSUFFICIENT_EVIDENCE",
            confidence=0,
            explanation="No evidence available.",
        ),
    )
    report = VerificationService().verify("A sufficiently long claim.")

    assert report.verdict is Verdict.INSUFFICIENT_EVIDENCE
    assert report.research_status is ResearchStatus.FAILED
    assert "provider timeout" not in report.summary


def test_claim_generation_falls_back_when_mistral_is_unavailable(monkeypatch):
    import agents.claim_agent as claim_agent

    def fail(_claim):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(claim_agent, "_extract_with_mistral", fail)

    queries = claim_agent.extract_search_queries("Is Sweetie Fox married?")

    assert queries == [
        "Is Sweetie Fox married?",
        "Is Sweetie Fox married? official source",
        "Is Sweetie Fox married? fact check",
    ]


def test_synthesis_provider_failure_returns_safe_uncertain_result(monkeypatch):
    import agents.analyst_agent as analyst_agent

    def fail(_prompt):
        raise RuntimeError("Mistral structured generation failed after retries")

    monkeypatch.setattr(analyst_agent, "_generate_json", fail)
    result = analyst_agent.analyze_evidence("A sufficiently long claim.", [])

    assert result.verdict == "INSUFFICIENT_EVIDENCE"
    assert result.confidence == 0


def test_service_connects_all_pipeline_stages_and_persists(monkeypatch):
    import verification_service as service_module
    from models.evidence import VerificationResult

    calls = []

    monkeypatch.setattr(service_module, "extract_search_queries", lambda claim: ["query"])
    monkeypatch.setattr(service_module, "fetch_evidence", lambda queries: [])
    monkeypatch.setattr(service_module, "assess_evidence_stance", lambda claim, evidence: [])
    monkeypatch.setattr(
        service_module,
        "analyze_evidence",
        lambda claim, evidence: VerificationResult(
            verdict="INSUFFICIENT_EVIDENCE",
            confidence=0,
            explanation="No evidence available.",
        ),
    )

    def persist(report, user_id):
        calls.append((report.claim, user_id, report.verdict))

    report = VerificationService(persist=persist).verify(
        "A sufficiently long claim.", user_id=7
    )

    assert report.verdict is Verdict.INSUFFICIENT_EVIDENCE
    assert calls == [("A sufficiently long claim.", 7, Verdict.INSUFFICIENT_EVIDENCE)]


def test_fresh_verification_does_not_return_historical_match(monkeypatch):
    import verification_service as service_module

    class HistoricalMemory:
        def search(self, *args, **kwargs):
            return [{'verdict': 'SUPPORTED', 'confidence': 99, 'summary': 'Old result'}]

    monkeypatch.setattr(service_module, "extract_search_queries", lambda claim: [claim])
    monkeypatch.setattr(service_module, "fetch_evidence", lambda queries: [])

    report = VerificationService(memory=HistoricalMemory()).verify(
        "A sufficiently long claim."
    )

    assert report.from_cache is False
    assert report.verdict is Verdict.INSUFFICIENT_EVIDENCE


def test_persistence_failure_does_not_hide_report(monkeypatch):
    import verification_service as service_module

    monkeypatch.setattr(service_module, "extract_search_queries", lambda claim: [claim])
    monkeypatch.setattr(service_module, "fetch_evidence", lambda queries: [])

    def fail_persist(report, user_id):
        raise OSError("database unavailable")

    report = VerificationService(persist=fail_persist).verify(
        "A sufficiently long claim."
    )

    assert report.verdict is Verdict.INSUFFICIENT_EVIDENCE
    assert report.research_status is ResearchStatus.FAILED
