from models.schemas import ResearchStatus, VerificationReport, Verdict
from verification_service import VerificationService


def test_cached_legacy_supported_result_maps_to_true():
    report = VerificationService._cached_report(
        {'verdict': 'SUPPORTED', 'confidence': '80', 'summary': 'Cached summary'},
        'A sufficiently long claim.',
        0.0,
    )

    assert report.verdict is Verdict.TRUE
    assert report.confidence == 0.8
    assert report.research_status is ResearchStatus.CACHED


def test_cached_unknown_result_abstains():
    report = VerificationService._cached_report(
        {'verdict': 'UNVERIFIABLE', 'confidence': '0', 'summary': 'Failed'},
        'A sufficiently long claim.',
        0.0,
    )

    assert report.verdict is Verdict.UNCERTAIN
    assert report.confidence == 0.0


def test_pipeline_failure_returns_error_report(monkeypatch):
    import verification_service as service_module

    def fail(_claim):
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(service_module, "extract_search_queries", fail)
    report = VerificationService().verify("A sufficiently long claim.")

    assert report.verdict is Verdict.ERROR
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