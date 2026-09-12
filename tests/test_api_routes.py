from models.schemas import ResearchStatus, VerificationReport, Verdict


def test_versioned_verify_validates_and_returns_canonical_report(monkeypatch):
    import app as app_module

    class FakeService:
        def verify(self, claim):
            return VerificationReport(
                claim=claim,
                verdict=Verdict.INSUFFICIENT_EVIDENCE,
                confidence=0.0,
                summary="No usable evidence.",
                research_status=ResearchStatus.FAILED,
            )

    monkeypatch.setattr(app_module, "verification_service", FakeService())
    client = app_module.app.test_client()

    invalid = client.post("/api/v1/verify", json={"claim": "short"})
    assert invalid.status_code == 422

    valid = client.post("/api/v1/verify", json={"claim": "A sufficiently long claim."})
    assert valid.status_code == 200
    assert valid.get_json()["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert valid.get_json()["research_status"] == "FAILED"


def test_mission_verify_alias_returns_canonical_report(monkeypatch):
    import app as app_module

    class FakeService:
        def verify(self, claim):
            return VerificationReport(
                claim=claim,
                verdict=Verdict.SUPPORTED,
                confidence=0.8,
                summary="Evidence supports the claim.",
                research_status=ResearchStatus.COMPLETE,
            )

    monkeypatch.setattr(app_module, "verification_service", FakeService())
    response = app_module.app.test_client().post(
        "/api/verify", json={"claim": "A sufficiently long claim."}
    )

    assert response.status_code == 200
    assert response.get_json()["verdict"] == "SUPPORTED"


def test_stream_endpoint_emits_real_pipeline_events(monkeypatch):
    import app as app_module

    class FakeService:
        def verify(self, claim, progress=None):
            if progress:
                progress("queries_generated", {"count": 1})
                progress("evidence_retrieved", {"count": 1})
            return VerificationReport(
                claim=claim,
                verdict=Verdict.INSUFFICIENT_EVIDENCE,
                confidence=0.0,
                summary="No usable evidence.",
                research_status=ResearchStatus.FAILED,
            )

    monkeypatch.setattr(app_module, "verification_service", FakeService())
    response = app_module.app.test_client().post(
        "/api/v1/verify/stream",
        json={"claim": "A sufficiently long claim."},
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert "event: queries_generated" in body
    assert "event: evidence_retrieved" in body
    assert "event: completed" in body


def test_authentication_scopes_history_and_supports_logout():
    import app as app_module
    import uuid

    client = app_module.app.test_client()
    email = f'phase3-{uuid.uuid4().hex}@example.com'
    registered = client.post('/register', json={'email': email, 'password': 'strong-pass-123'})
    assert registered.status_code == 201
    assert client.get('/profile').status_code == 200
    assert client.get('/api/v1/history').status_code == 200
    assert client.get('/logout').status_code == 200
    assert client.get('/profile').status_code == 401
    assert client.get('/api/v1/history').status_code == 401

    logged_in = client.post('/login', json={'email': email, 'password': 'strong-pass-123'})
    assert logged_in.status_code == 200
    assert client.get('/profile').status_code == 200
